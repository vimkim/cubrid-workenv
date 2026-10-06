"""Explicit release of numeric allocations; unique paths and storage stay put."""
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import stat

from .allocation import atomic_json, available, occupied_shm_keys
from .doctor import read_state
from .reclamation import process_reason

NUMERIC = ('master_port', 'broker_port', 'broker_master_shm_id', 'broker_appl_server_shm_id')


def identity(record):
    return {**{key: record[key] for key in ('worktree', 'install', 'tmp')}, 'status': 'reset'}


def owned_path(path, directory=False):
    """Check canonical, user-owned control artifacts; never follow control symlinks."""
    if path.resolve() != path or path.is_symlink():
        raise ValueError(f'Symlinked control path: {path}')
    info = path.stat()
    if info.st_uid != os.getuid() or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError(f'Unexpected control path ownership/type: {path}')


def activity_problem(record):
    for key in ('master_port', 'broker_port'):
        if not available(record[key]):
            return f'occupied or inaccessible TCP port {record[key]}'
    keys = occupied_shm_keys()
    for key in ('broker_master_shm_id', 'broker_appl_server_shm_id'):
        if record[key] in keys:
            return f'SysV SHM key {record[key]:#x} still exists; stop its owning broker or inspect ownership manually'
    tmp = Path(record['tmp'])
    if tmp.exists():
        owned_path(tmp, directory=True)
    for line in Path('/proc/net/unix').read_text().splitlines()[1:]:
        fields = line.split(maxsplit=7)
        if len(fields) == 8 and (fields[7] == str(tmp) or fields[7].startswith(str(tmp) + '/')):
            return f'live Unix socket: {fields[7]}'
    # Stale files in TMP are preserved: releasing numeric slots does not remove paths.
    ancestors = set()
    pid = os.getppid()
    while pid > 1 and pid not in ancestors:
        ancestors.add(pid)
        text = Path(f'/proc/{pid}/stat').read_text()
        pid = int(text.rsplit(')', 1)[1].split()[1])
    return process_reason(record, ancestors)


def reset(args):
    selected_home = args.state_home
    if selected_home is None and args.command == 'reset':
        marker = args.worktree.resolve() / '.cub-workenv/state.json'
        if marker.exists():
            state = read_state(args.worktree.resolve())
            if not isinstance(state.get('state_home'), str):
                raise ValueError('Missing recorded allocation namespace; specify --state-home after inspection')
            selected_home = Path(state['state_home'])
    if selected_home is None:
        selected_home = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'cub-workenv'
    home = selected_home.expanduser().absolute()
    registry = home / 'allocations.json'
    if not registry.exists():
        print(f'No allocations in {home}; nothing to reset.')
        return
    owned_path(home, directory=True)
    owned_path(registry)
    owned_path(home / 'allocations.lock')
    with ExitStack() as stack:
        lock = stack.enter_context((home / 'allocations.lock').open('r+'))
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = json.loads(registry.read_text())
        if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
            raise ValueError('Invalid allocation registry')
        selected = records if args.command == 'reset-all' else [r for r in records if r.get('worktree') == str(args.worktree.resolve())]
        if len({r.get('worktree') for r in records}) != len(records):
            raise ValueError('Duplicate worktree records; inspect manually')
        if not selected:
            print('No matching allocation; nothing to reset.')
            return
        changes = []
        problems = []
        for record in selected:
            worktree = Path(record['worktree'])
            if not worktree.is_absolute() or worktree.resolve() != worktree:
                raise ValueError(f'Noncanonical worktree: {worktree}')
            for key in ('install', 'tmp'):
                if not isinstance(record.get(key), str) or not Path(record[key]).is_absolute():
                    raise ValueError(f'Invalid allocation {key}: {worktree}')
            if record.get('status') == 'reset':
                print(f'{worktree}: already reset; unique paths retained')
                continue
            if not all(type(record.get(key)) is int for key in NUMERIC):
                raise ValueError(f'Incomplete numeric allocation: {worktree}; inspect manually')
            state = None
            marker = worktree / '.cub-workenv/state.json'
            if worktree.exists():
                root = marker.parent
                owned_path(root, directory=True)
                owned_path(marker)
                owned_path(root / 'init.lock')
                worktree_lock = stack.enter_context((root / 'init.lock').open('r+'))
                try:
                    fcntl.flock(worktree_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise ValueError(f'Initializer/database operation active in {worktree}; retry later') from error
                state = read_state(worktree)
                if state.get('worktree') != str(worktree) or state.get('state_home') != str(home):
                    raise ValueError(f'State identity/namespace mismatch: {worktree}')
                if state.get('allocation') != record and not (state.get('status') == 'reset' and state.get('previous_allocation') == record):
                    raise ValueError(f'State/allocation mismatch: {worktree}')
            reason = activity_problem(record)
            if reason:
                problems.append(f'{worktree}: {reason}')
            print(f"{worktree}: release TCP {record['master_port']}/{record['broker_port']}, "
                  f"SHM {record['broker_master_shm_id']:#x}/{record['broker_appl_server_shm_id']:#x}; preserve {record['tmp']}")
            changes.append((record, state, marker))
        if problems:
            raise ValueError('Reset blocked; no allocations released:\n' + '\n'.join(problems))
        if not args.apply:
            print('Preview only. Stop affected instances first; use --apply to release numeric allocations. Paths, DBs and logs remain.')
            return
        # Recheck after acquiring every per-worktree lock and before publication.
        for record, _, _ in changes:
            reason = activity_problem(record)
            if reason:
                raise ValueError(f'Reset blocked; no allocations released: {record["worktree"]}: {reason}')
        for record, state, marker in changes:
            if state is not None:
                updated = dict(state, status='reset', stage='numeric resources released; explicit init required',
                               allocation=identity(record), previous_allocation=record)
                atomic_json(marker, updated)
        replacements = {record['worktree']: identity(record) for record, _, _ in changes}
        # Last publication is the commit point. On interruption, numeric records
        # stay reserved and rerunning reset completes the marked environments.
        atomic_json(registry, [replacements.get(r['worktree'], r) for r in records])
        print(f'Reset {len(changes)} allocation(s). Reload/leave old shells; explicitly init each worktree before reuse. Unique paths, DBs and logs preserved.')
