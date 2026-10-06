"""Prune missing Git worktree registrations and their proven-idle allocations."""
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import subprocess

from .allocation import atomic_json, available, occupied_shm_keys
from .doctor import read_state
from .reclamation import deleted_path, inactive_reason
from .reset import owned_path


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip())
    return result.stdout


def registered(root):
    entries = []
    for block in git(root, 'worktree', 'list', '--porcelain', '-z').split(b'\0\0'):
        fields = block.split(b'\0')
        paths = [os.fsdecode(f[9:]) for f in fields if f.startswith(b'worktree ')]
        if paths:
            entries.append({'path': paths[0], 'locked': any(f == b'locked' or f.startswith(b'locked ') for f in fields)})
    return entries


def reason(entry, record):
    path = Path(entry['path'])
    if not path.is_absolute():
        return 'nonabsolute registered worktree path'
    deleted, why = deleted_path(path)
    if not deleted:
        return why
    if entry['locked']:
        return 'Git worktree is locked; unlock explicitly after inspection'
    if record is None:
        return None
    for key in ('worktree', 'tmp', 'install'):
        if not isinstance(record.get(key), str) or not Path(record[key]).is_absolute():
            return f'incomplete allocation field: {key}'
    try:
        return inactive_reason(record, available, occupied_shm_keys())
    except (OSError, ValueError, TypeError, KeyError) as error:
        return f'allocation inspection uncertain: {error}'


def prune(args):
    root = args.worktree.resolve(strict=True)
    entries = registered(root)
    # Git's first record is its main/bare worktree; never remove it.
    candidates = [e for e in entries[1:] if not Path(e['path']).is_dir()]
    selected_home = args.state_home
    marker = root / '.cub-workenv/state.json'
    if selected_home is None and marker.exists():
        state = read_state(root)
        if not isinstance(state.get('state_home'), str):
            raise ValueError('Missing recorded state-home; inspect before pruning')
        selected_home = Path(state['state_home'])
    if selected_home is None:
        selected_home = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'cub-workenv'
    home = selected_home.expanduser().absolute()
    registry = home / 'allocations.json'
    print(f'Allocation namespace: {home}')
    if not candidates:
        print('No missing linked worktrees to prune.')
        return
    with ExitStack() as stack:
        # Preview creates no files. Apply serializes even an initially empty
        # namespace against cooperating initializers.
        if args.apply:
            home.mkdir(parents=True, exist_ok=True)
        if home.exists():
            owned_path(home, directory=True)
        lock_path = home / 'allocations.lock'
        if lock_path.exists() or args.apply:
            if lock_path.exists():
                owned_path(lock_path)
            stream = stack.enter_context(lock_path.open('a' if args.apply else 'r+'))
            fcntl.flock(stream, fcntl.LOCK_EX)
        elif registry.exists():
            raise ValueError('Allocation registry has no lock file; inspect manually')
        if registry.exists():
            owned_path(registry)
            records = json.loads(registry.read_text())
        else:
            records = []
        if not isinstance(records, list) or not all(isinstance(r, dict) and isinstance(r.get('worktree'), str) for r in records):
            raise ValueError('Invalid allocation registry')
        if len({r['worktree'] for r in records}) != len(records):
            raise ValueError('Duplicate allocation records; inspect manually')
        kept = []
        count = 0
        for entry in candidates:
            path = entry['path']
            record = next((r for r in records if r['worktree'] == path), None)
            why = reason(entry, record)
            if why:
                print(f'KEEP {path}: {why}')
                kept.append(path)
                continue
            if not args.apply:
                print(f'WOULD PRUNE {path}: Git registration' + (' and idle allocation' if record else '; no allocation recorded'))
                count += 1
                continue
            # Recheck Git lock/path and resource evidence immediately before the
            # targeted, non-force Git operation. Never use a broad Git prune.
            current = next((e for e in registered(root) if e['path'] == path), None)
            if current is None:
                print(f'KEEP {path}: registration changed during prune; retry after inspection')
                kept.append(path)
                continue
            why = reason(current, record)
            if why:
                print(f'KEEP {path}: {why}')
                kept.append(path)
                continue
            remaining = [r for r in records if r is not record]
            # Publish release first while retaining the allocator lock. A crash
            # here leaves Git metadata for a subsequent prune to remove. A Git
            # failure restores the record before other allocators can use it.
            if record is not None:
                atomic_json(registry, remaining)
            try:
                git(root, 'worktree', 'remove', '--', path)
            except ValueError as error:
                if record is not None:
                    atomic_json(registry, records)
                print(f'KEEP {path}: Git refused removal: {error}')
                kept.append(path)
                continue
            records = remaining
            count += 1
            print(f'PRUNED {path}: Git registration' + (' and idle allocation' if record else '; no allocation recorded'))
        print(f'{"Pruned" if args.apply else "Would prune"} {count}; retained {len(kept)} missing/uncertain worktree(s).')
        if not args.apply:
            print('Preview only; use --apply to prune. Existing worktrees, branches and data paths are preserved.')
        if kept:
            raise ValueError('Some missing/uncertain worktrees were retained; inspect KEEP reasons. Other eligible entries were processed.')
