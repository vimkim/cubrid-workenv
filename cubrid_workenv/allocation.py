"""Short, serialized host allocation transactions (not OS reservations)."""
from contextlib import contextmanager
import fcntl
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import sys
from .reclamation import inactive_reason


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
        try:
            with socket.socket(socket.AF_INET6) as sock:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                sock.bind(('::', port))
        except OSError as error:
            if error.errno not in (errno.EAFNOSUPPORT, errno.EPROTONOSUPPORT):
                return False
        return True
    except OSError:
        return False


def occupied_shm_keys():
    """Linux SysV IPC inventory: inability to inspect fails closed."""
    rows = Path('/proc/sysvipc/shm').read_text().splitlines()
    return {int(row.split()[0]) for row in rows[1:]}


def allocate(worktree, home, start, end, *, install=None,
             shm_start=0x62000000, shm_end=0x6200ffff, reuse_identity=None):
    if not 1024 <= start <= end <= 65535:
        raise ValueError('Port pool must satisfy 1024 <= start <= end <= 65535')
    if not 1 <= shm_start <= shm_end <= 0x7fffffff:
        raise ValueError('Shared-memory pool must satisfy 1 <= start <= end <= 0x7fffffff')
    home.mkdir(parents=True, exist_ok=True)
    with locked(home / 'allocations.lock'):
        path = home / 'allocations.json'
        records = json.loads(path.read_text()) if path.exists() else []
        if reuse_identity is not None:
            if (reuse_identity not in records or reuse_identity.get('status') != 'reset'
                    or reuse_identity.get('worktree') != str(worktree)
                    or reuse_identity.get('install') != str(install)):
                raise ValueError('Reset identity is missing or changed; inspect before reinitialization')
            records = [item for item in records if item != reuse_identity]
        if any(item['worktree'] == str(worktree) for item in records):
            raise ValueError('Worktree already has an allocation; inspect with doctor before manual recovery')
        if install and any(item.get('install') == str(install) for item in records):
            raise ValueError('Selected installation is already allocated to another worktree; select a dedicated installation (PL info files are installation-local)')
        def select(records, occupied):
            used = {item[key] for item in records
                    for key in ('master_port', 'broker_port') if key in item}
            ports = []
            for port in range(start, end + 1):
                if port not in used and available(port):
                    ports.append(port)
                    if len(ports) == 2:
                        break
            used_keys = occupied | {item[key] for item in records
                for key in ('broker_master_shm_id', 'broker_appl_server_shm_id') if key in item}
            keys = []
            for key in range(shm_start, shm_end + 1):
                if key not in used_keys:
                    keys.append(key)
                    if len(keys) == 2:
                        break
            return ports, keys

        occupied = occupied_shm_keys()
        ports, keys = select(records, occupied)
        if len(ports) != 2 or len(keys) != 2:
            retained, report = [], []
            for record in records:
                reason = inactive_reason(record, available, occupied)
                report.append({'allocation': record, 'action': 'kept' if reason else 'reclaimed',
                               'reason': reason or 'deleted worktree; no process, port, socket or shared-memory activity found'})
                if reason:
                    retained.append(record)
            atomic_json(home / 'allocations-reclamation.json', report)
            for item in report:
                print(f"Allocation {item['allocation']['worktree']}: {item['action']}: {item['reason']}", file=sys.stderr)
            if len(retained) != len(records):
                records = retained
                atomic_json(path, records + ([reuse_identity] if reuse_identity is not None else []))
            ports, keys = select(records, occupied_shm_keys())
        if len(ports) != 2 or len(keys) != 2:
            raise ValueError(f'Pool exhausted: ports {start}-{end} ({len(ports)}/2 free), '
                             f'shared memory {shm_start:#x}-{shm_end:#x} ({len(keys)}/2 free); '
                             f'inspect owners in {path} and allocations-reclamation.json; '
                             'explicitly adjust --port-start/--port-end or --shm-start/--shm-end')
        base = Path('/tmp') / f'cwe-{os.getuid()}'
        base.mkdir(mode=0o700, exist_ok=True)
        if base.is_symlink() or base.stat().st_uid != os.getuid() or base.stat().st_mode & 0o077:
            raise ValueError(f'Unsafe TMP base: {base}')
        digest = hashlib.sha256(str(worktree).encode()).hexdigest()
        tmp = None
        if reuse_identity is not None:
            candidate = Path(reuse_identity['tmp'])
            if (candidate.parent != base or candidate.is_symlink() or not candidate.is_dir()
                    or candidate.stat().st_uid != os.getuid() or candidate.stat().st_mode & 0o077
                    or any(item.get('tmp') == str(candidate) for item in records)):
                raise ValueError(f'Reset TMP identity is missing, unsafe or in use: {candidate}')
            tmp = candidate
        for size in (() if tmp is not None else range(12, 65, 4)):
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
