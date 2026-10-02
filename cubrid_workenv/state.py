"""Initialization lifecycle; ready is published only after native creation."""
import os
from .allocation import allocate, atomic_json, locked
from .doctor import read_state, ready_problems
from .runtime import write_environment, write_settings
from .database import prepare_databases, existing_registry


def initialize(args):
    worktree = args.worktree.resolve(strict=True)
    root = worktree / '.cub-workenv'
    if not root.exists():
        validate_install(args.install)
    root.mkdir(exist_ok=True)
    if root.is_symlink():
        raise ValueError('Refusing a symlinked work environment directory')
    with locked(root / 'init.lock'):
        marker = root / 'state.json'
        if marker.exists():
            state = read_state(worktree)
            if state.get('status') == 'ready':
                problems = ready_problems(state, worktree)
                if problems:
                    raise ValueError('Existing environment needs attention: ' + '; '.join(problems) + '; run doctor')
                print('Warning: work environment already initialized; unchanged.')
                return
            raise ValueError('Incomplete initialization retained; run doctor and inspect before manual recovery')
        if any(p.name != 'init.lock' for p in root.iterdir()):
            raise ValueError('Unknown existing settings or database artifacts preserved; inspect before initialization')
        registry = existing_registry(worktree, args.database_registry)
        validate_install(args.install)
        state = {'schema': 1, 'status': 'preparing', 'worktree': str(worktree),
                 'install': str(args.install.resolve()), 'preset': args.preset,
                 'state_home': str(args.state_home.resolve())}
        if args.java_home:
            state['java_home'] = str(args.java_home.resolve(strict=True))
        state['stage'] = 'allocation'
        atomic_json(marker, state)
        try:
            state['allocation'] = allocate(worktree, args.state_home.resolve(), args.port_start, args.port_end,
                                           install=state['install'], shm_start=args.shm_start, shm_end=args.shm_end)
            state['stage'] = 'settings'
            atomic_json(marker, state)
            write_settings(state)
            state['stage'] = 'database'
            atomic_json(marker, state)
            prepare_databases(state, registry, args.no_db, args.db_path)
            state['stage'] = 'environment publication'
            atomic_json(marker, state)
            write_environment(state)
            state['status'] = 'ready'
            state['stage'] = 'complete'
            atomic_json(marker, state)
        except (OSError, ValueError) as error:
            state['status'] = 'preparing'
            state['error'] = str(error)
            atomic_json(marker, state)
            raise ValueError(f'Initialization incomplete at {state["stage"]}: {error}; run doctor before manual recovery') from error
        print(f'Initialized {worktree} with {state["install"]} (preset {state["preset"]}).')
        print(f'Source {root / "env.sh"} in bash; use ordinary cubrid and csql commands.')


def validate_install(install):
    if not all((install / 'bin' / name).is_file() and os.access(install / 'bin' / name, os.X_OK)
               for name in ('cubrid', 'csql')):
        raise ValueError('Selected installation is missing cubrid/csql; build and install your preset, then run init explicitly.')
