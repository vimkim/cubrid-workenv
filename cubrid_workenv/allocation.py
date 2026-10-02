"""Short, serialized host allocation transactions (not OS reservations)."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile


@contextmanager
def locked(path):
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def available(port):
    try:
        with socket.socket() as sock:
            sock.bind(('0.0.0.0', port))
        return True
    except OSError:
        return False


def occupied_shm_keys():
    """Linux SysV IPC inventory: inability to inspect fails closed."""
    rows = Path('/proc/sysvipc/shm').read_text().splitlines()
    return {int(row.split()[0]) for row in rows[1:]}


def allocate(worktree, home, start, end, *, install=None,
             shm_start=0x62000000, shm_end=0x6200ffff):
    if not 1024 <= start <= end <= 65535:
        raise ValueError('Port pool must satisfy 1024 <= start <= end <= 65535')
    if not 1 <= shm_start <= shm_end <= 0x7fffffff:
        raise ValueError('Shared-memory pool must satisfy 1 <= start <= end <= 0x7fffffff')
    home.mkdir(parents=True, exist_ok=True)
    with locked(home / 'allocations.lock'):
        path = home / 'allocations.json'
        records = json.loads(path.read_text()) if path.exists() else []
        if any(item['worktree'] == str(worktree) for item in records):
            raise ValueError('Worktree already has an allocation; inspect with doctor before manual recovery')
        if install and any(item.get('install') == str(install) for item in records):
            raise ValueError('Selected installation is already allocated to another worktree; select a dedicated installation (PL info files are installation-local)')
        used = {item[key] for item in records for key in ('master_port', 'broker_port') if key in item}
        ports = []
        for port in range(start, end + 1):
            if port not in used and available(port):
                ports.append(port)
                if len(ports) == 2:
                    break
        if len(ports) != 2:
            raise ValueError(f'Port pool {start}-{end} exhausted; two ports required; inspect owners in {path} or explicitly adjust the pool')
        used_keys = occupied_shm_keys() | {item[key] for item in records
            for key in ('broker_master_shm_id', 'broker_appl_server_shm_id') if key in item}
        keys = []
        for key in range(shm_start, shm_end + 1):
            if key not in used_keys:
                keys.append(key)
                if len(keys) == 2:
                    break
        if len(keys) != 2:
            raise ValueError(f'Shared-memory pool {shm_start:#x}-{shm_end:#x} exhausted; inspect owners in {path} or explicitly adjust the pool')
        base = Path('/tmp') / f'cwe-{os.getuid()}'
        base.mkdir(mode=0o700, exist_ok=True)
        if base.is_symlink() or base.stat().st_uid != os.getuid() or base.stat().st_mode & 0o077:
            raise ValueError(f'Unsafe TMP base: {base}')
        digest = hashlib.sha256(str(worktree).encode()).hexdigest()
        tmp = None
        for size in range(12, 65, 4):
            candidate = base / digest[:size]
            if len(str(candidate / 'sp_testdb.sock').encode()) >= 108:
                break
            if any(item['tmp'] == str(candidate) for item in records) or candidate.exists():
                continue
            try:
                candidate.mkdir(mode=0o700)
                tmp = candidate
                break
            except FileExistsError:
                continue
        if tmp is None:
            raise ValueError('No safe short TMP identity available; inspect existing socket directories')
        result = {'worktree': str(worktree), 'master_port': ports[0], 'broker_port': ports[1],
                  'broker_master_shm_id': keys[0], 'broker_appl_server_shm_id': keys[1],
                  'install': str(install) if install else None, 'tmp': str(tmp)}
        records.append(result)
        atomic_json(path, records)
        return result
