"""Public command line boundary."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(
        prog='cub-workenv',
        description='Prepare a built host worktree explicitly; use ordinary cubrid/csql after loading its environment.',
        epilog='Doctor is read-only. Native DB locking has bounded normal-path verification; init is not a sandbox. '
               'See docs/workflow.md for manual recovery, external DB lifetime and build-version compatibility.')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='explicitly prepare a selected installation and testdb')
    init.add_argument('--worktree', type=Path, default=Path.cwd())
    init.add_argument('--install', type=Path, required=True)
    init.add_argument('--preset', required=True)
    init.add_argument('--state-home', type=Path, default=Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'cub-workenv')
    init.add_argument('--port-start', type=int, default=41000)
    init.add_argument('--port-end', type=int, default=41999)
    doctor = commands.add_parser('doctor', help='inspect initialization without changing it')
    doctor.add_argument('--worktree', type=Path, default=Path.cwd())
    doctor.add_argument('--install', type=Path, help='expected selected installation')
    doctor.add_argument('--preset', help='expected selected preset')
    doctor.add_argument('--native-error-file', type=Path, help='preserve and explain an existing native error; never reproduce it')
    init.add_argument('--shm-start', type=lambda value: int(value, 0), default=0x62000000)
    init.add_argument('--shm-end', type=lambda value: int(value, 0), default=0x6200ffff)
    init.add_argument('--java-home', type=Path, default=Path(os.environ['JAVA_HOME']) if os.environ.get('JAVA_HOME') else None,
                      help='JDK for PL (defaults to JAVA_HOME; otherwise uses CUBRID build default)')
    init.add_argument('--database-registry', type=Path, help='copy existing local DB registrations; never copy another instance settings')
    init.add_argument('--no-db', action='store_true', help='prepare only; create a database later with create-db')
    init.add_argument('--db-path', type=Path)
    create = commands.add_parser('create-db', help='create an additional database without replacing existing storage')
    create.add_argument('name')
    create.add_argument('--worktree', type=Path, default=Path.cwd())
    create.add_argument('--path', type=Path)
    env = commands.add_parser('env', help='emit bash cleanup and load a completed environment without diagnosis')
    env.add_argument('--worktree', type=Path, default=Path.cwd())
    env.add_argument('--preset')
    env.add_argument('--install', type=Path)
    for command in ('reset', 'reset-all'):
        reset = commands.add_parser(command, help='release numeric resources; preserve paths, databases and logs (preview by default)')
        reset.add_argument('--state-home', type=Path, help='allocation namespace (reset defaults to recorded namespace; reset-all to the host default)')
        reset.add_argument('--apply', action='store_true', help='apply the reset after inactivity checks')
        if command == 'reset':
            reset.add_argument('--worktree', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.command in ('reset', 'reset-all'):
            from .reset import reset
            reset(args)
        elif args.command == 'env':
            from .loading import emit
            emit(args)
        elif args.command == 'doctor':
            from .doctor import diagnose
            diagnose(args)
        elif args.command == 'create-db':
            from .database import create_in_environment
            create_in_environment(args)
        else:
            from .state import initialize
            initialize(args)
        return 0
    except (ValueError, OSError) as error:
        print(f'cub-workenv: {error}', file=sys.stderr)
        return 1
