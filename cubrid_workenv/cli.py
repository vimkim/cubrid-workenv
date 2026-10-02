"""Public command line boundary."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(prog='cub-workenv')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='explicitly prepare a selected installation and testdb')
    init.add_argument('--worktree', type=Path, default=Path.cwd())
    init.add_argument('--install', type=Path, required=True)
    init.add_argument('--preset', required=True)
    init.add_argument('--state-home', type=Path, default=Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'cub-workenv')
    init.add_argument('--port-start', type=int, default=41000)
    init.add_argument('--port-end', type=int, default=41999)
    args = parser.parse_args()
    try:
        if not all(os.access(args.install / 'bin' / name, os.X_OK) for name in ('cubrid', 'csql')):
            raise ValueError('Selected installation is missing cubrid/csql; build and install your preset, then run init explicitly.')
        from .state import initialize
        initialize(args)
        return 0
    except (ValueError, OSError) as error:
        print(f'cub-workenv: {error}', file=sys.stderr)
        return 1
