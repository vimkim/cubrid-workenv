"""Read-only state diagnosis; full runtime/owner inspection extends this seam."""
import json
import os
from pathlib import Path


def read_state(worktree):
    marker = worktree / '.cub-workenv/state.json'
    try:
        state = json.loads(marker.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f'Cannot read initialization state {marker}: {error}; run doctor and inspect manually') from error
    if not isinstance(state, dict) or state.get('schema') != 1:
        raise ValueError(f'Invalid initialization state {marker}; run doctor and inspect manually')
    return state


def ready_problems(state, worktree):
    """Cheap artifact checks only: no DB opens, hashes or host process scan."""
    problems = []
    root = worktree / '.cub-workenv'
    if state.get('worktree') != str(worktree):
        problems.append('Recorded worktree differs from current path; moving worktrees is unsupported')
    for key in ('install', 'preset', 'state_home'):
        if not isinstance(state.get(key), str) or not state[key]:
            problems.append(f'Missing or invalid state field: {key}')
    for relative in ('conf/cubrid.conf', 'databases/databases.txt', 'env.sh'):
        path = root / relative
        if not path.is_file() or not os.access(path, os.R_OK):
            problems.append(f'Missing or unreadable artifact: {path}')
        elif relative != 'databases/databases.txt' and path.stat().st_size == 0:
            problems.append(f'Empty artifact: {path}')
    install = state.get('install')
    if isinstance(install, str):
        for name in ('cubrid', 'csql'):
            path = Path(install) / 'bin' / name
            if not path.is_file() or not os.access(path, os.X_OK):
                problems.append(f'Selected installation missing executable: {path}; build/install the recorded preset')
    allocation = state.get('allocation')
    if not isinstance(allocation, dict):
        problems.append('Missing allocation in initialization state')
    else:
        tmp = allocation.get('tmp')
        if not isinstance(tmp, str) or not Path(tmp).is_dir():
            problems.append(f'Missing allocation TMP directory: {tmp}')
        home = state.get('state_home')
        if isinstance(home, str):
            path = Path(home) / 'allocations.json'
            try:
                records = json.loads(path.read_text())
                if not isinstance(records, list) or allocation not in records:
                    problems.append(f'Allocation missing or inconsistent in {path}')
            except (ValueError, OSError) as error:
                problems.append(f'Cannot read allocation record {path}: {error}')
    return problems


def diagnose(args):
    worktree = args.worktree.resolve(strict=True)
    root = worktree / '.cub-workenv'
    if not root.exists():
        raise ValueError('Work environment is uninitialized; build/install then run init explicitly')
    if root.is_symlink():
        raise ValueError(f'Symlinked work environment directory {root}; inspect manually')
    state = read_state(worktree)
    print(f'Worktree: {worktree}\nState: {state.get("status", "unknown")}')
    if state.get('status') != 'ready':
        print(f'Last stage: {state.get("stage", "unknown")}')
        if state.get('error'):
            print(f'Last error: {state["error"]}')
        print(f'Inspect {root / "state.json"}, {root / "createdb.log"}, and recorded allocation before manual recovery.')
        print('Preserve DB files and settings; confirm the initializing process has stopped. No retry, deletion or rollback performed.')
        raise ValueError('Incomplete initialization; manual recovery required')
    problems = ready_problems(state, worktree)
    if problems:
        raise ValueError('\n'.join(problems) + '\nInspect and correct manually; no changes performed.')
    print('Ready: initialization artifacts and recorded installation are present. No changes performed.')
