"""Database preparation; runtime exclusion remains with native CUBRID."""
import json
import re
import subprocess
import tempfile
import os
from pathlib import Path
from .allocation import locked
from .runtime import process_environment


def create_database(state, name='testdb', location=None):
    root = Path(state['worktree']) / '.cub-workenv'
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,62}', name):
        raise ValueError('DB name must start with a letter and contain at most 63 letters, digits or underscores')
    socket_path = Path(state['allocation']['tmp']) / f'sp_{name}.sock'
    if len(os.fsencode(socket_path)) >= 108:
        raise ValueError('DB name makes the PL Unix socket path too long; choose a shorter name')
    registry = root / 'databases/databases.txt'
    if name in registrations(registry.read_bytes()):
        raise ValueError(f'Database {name} is already registered; existing storage preserved')
    receipt_path = root / f'created-{name}.json'
    if receipt_path.exists() or receipt_path.is_symlink():
        raise ValueError(f'Creation provenance already exists for {name}; inspect retained storage before reuse')
    base = location.resolve() if location else root / 'db' / name
    if any(c.isspace() for c in str(base)):
        raise ValueError('Database storage path must not contain whitespace')
    if base.exists():
        raise ValueError(f'Existing storage preserved at {base}; select a new empty location')
    paths = [base / part for part in ('data', 'log', 'lob')]
    for path in paths:
        path.mkdir(parents=True, exist_ok=False)
    command = [str(Path(state['install']) / 'bin/cubrid'), 'createdb',
               '--db-volume-size=64M', '--log-volume-size=32M',
               '-F', str(paths[0]), '-L', str(paths[1]), '-B', str(paths[2]),
               '--server-name=localhost', name, 'en_US.utf8']
    # Native createdb rewrites its registry. Give it a private registration file,
    # then append only its newly created row to the user's exact original bytes.
    before = registry.read_bytes()
    log_path = root / f'createdb-{name}.log'
    with tempfile.TemporaryDirectory(prefix='create-', dir=root) as scratch:
        temporary = Path(scratch) / 'databases.txt'
        temporary.write_bytes(b'')
        env = process_environment(state)
        env['CUBRID_DATABASES'] = scratch
        with log_path.open('w') as log:
            result = subprocess.run(command, env=env, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError(f'createdb failed ({result.returncode}); see {log_path}; storage retained; run doctor')
        rows = [line for line in temporary.read_bytes().splitlines(keepends=True)
                if line.split() and line.split()[0] == name.encode()]
        if len(rows) != 1:
            raise ValueError(f'createdb did not register {name}; see {log_path}; storage retained')
        primary = paths[0] / name
        metadata = primary.stat()
        if registry.read_bytes() != before:
            raise ValueError(f'Registry changed during createdb; new storage retained at {base}; inspect manually')
        with registry.open('ab') as stream:
            stream.write((b'\n' if before and not before.endswith(b'\n') else b'') + rows[0])
            stream.flush()
            os.fsync(stream.fileno())
        # Provenance for optional personal lifecycle tooling. Existing/reused
        # DBs never acquire a receipt; location alone does not establish ownership.
        receipt = {'name': name, 'base': str(base),
                   'registration': rows[0].decode().split(),
                   'primary_device': metadata.st_dev, 'primary_inode': metadata.st_ino}
        with (root / f'created-{name}.json').open('x') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')


def create_in_environment(args):
    root = args.worktree.resolve(strict=True) / '.cub-workenv'
    if not (root / 'state.json').is_file():
        raise ValueError('Environment is not initialized; run init first')
    with locked(root / 'init.lock'):
        state = json.loads((root / 'state.json').read_text())
        if state.get('status') != 'ready':
            raise ValueError('Incomplete environment; run doctor before creating a database')
        create_database(state, args.name, args.path)
        print(f'Created database {args.name}.')


def registrations(content):
    rows = {}
    for line in content.decode().splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            continue
        name = fields[0]
        if name in rows:
            raise ValueError(f'Duplicate existing DB registration: {name}')
        rows[name] = fields
    return rows


def existing_registry(worktree, selected):
    if selected:
        return selected.resolve(strict=True).read_bytes()
    candidates = [p for p in (worktree / 'databases.txt', worktree / 'databases/databases.txt') if p.exists()]
    if len(candidates) > 1:
        raise ValueError('Multiple existing registries; select --database-registry explicitly')
    return candidates[0].read_bytes() if candidates else b''


def prepare_databases(state, content, no_db, location):
    root = Path(state['worktree']) / '.cub-workenv'
    registry = root / 'databases/databases.txt'
    registry.write_bytes(content)
    if no_db:
        return
    rows = registrations(content)
    if 'testdb' not in rows:
        create_database(state, location=location)
        return
    fields = rows['testdb']
    if location is not None:
        raise ValueError('Existing testdb registration determines storage; omit --db-path')
    if len(fields) != 5 or fields[2] != 'localhost' or not fields[4].startswith('file:'):
        raise ValueError('Existing testdb registration is not a supported local data/log/LOB registration')
    data, log, lob = Path(fields[1]), Path(fields[3]), Path(fields[4][5:])
    if not all(p.is_absolute() and p.is_dir() for p in (data, log, lob)):
        raise ValueError('Existing testdb storage must have accessible absolute data/log/LOB directories')
    if not (data / 'testdb').is_file() or not (log / 'testdb_lgat').is_file():
        raise ValueError('Existing testdb volume or active log is missing; storage preserved')
    print('Reusing existing testdb registration without opening storage; file-format compatibility remains the user responsibility.')
