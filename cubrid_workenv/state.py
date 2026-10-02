"""Initialization lifecycle; ready is published only after native creation."""
import json
from pathlib import Path
from .allocation import allocate, atomic_json, locked
from .runtime import create_database, write_environment, write_settings


def initialize(args):
    worktree = args.worktree.resolve(strict=True)
    root = worktree / '.cub-workenv'
    root.mkdir(exist_ok=True)
    if root.is_symlink():
        raise ValueError('Refusing a symlinked work environment directory')
    with locked(root / 'init.lock'):
        marker = root / 'state.json'
        if marker.exists():
            state = json.loads(marker.read_text())
            if state.get('status') == 'ready':
                print('Warning: work environment already initialized; unchanged.')
                return
            raise ValueError('Incomplete initialization retained; run doctor and inspect before manual recovery')
        if any(p.name != 'init.lock' for p in root.iterdir()):
            raise ValueError('Unknown existing settings or database artifacts preserved; inspect before initialization')
        for existing in (worktree / 'databases.txt', worktree / 'databases/databases.txt'):
            if existing.exists() and existing.read_text().strip():
                raise ValueError(f'Existing DB registry preserved at {existing}; reuse requires explicit compatibility checks')
        state = {'schema': 1, 'status': 'preparing', 'worktree': str(worktree),
                 'install': str(args.install.resolve()), 'preset': args.preset,
                 'state_home': str(args.state_home.resolve())}
        atomic_json(marker, state)
        state['allocation'] = allocate(worktree, args.state_home.resolve(), args.port_start, args.port_end)
        atomic_json(marker, state)
        write_settings(state)
        create_database(state)
        write_environment(state)
        state['status'] = 'ready'
        atomic_json(marker, state)
        print(f'Initialized {worktree} with {state["install"]} (preset {state["preset"]}).')
        print(f'Source {root / "env.sh"} in bash; use ordinary cubrid and csql commands.')
