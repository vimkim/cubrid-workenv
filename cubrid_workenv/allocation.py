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


def allocate(worktree, home, start, end):
    if not 1024 <= start <= end <= 65535:
        raise ValueError('Port pool must satisfy 1024 <= start <= end <= 65535')
    home.mkdir(parents=True, exist_ok=True)
    with locked(home / 'allocations.lock'):
        path = home / 'allocations.json'
        records = json.loads(path.read_text()) if path.exists() else []
        if any(item['worktree'] == str(worktree) for item in records):
            raise ValueError('Worktree already has an allocation; inspect with doctor before manual recovery')
        used = {item['master_port'] for item in records}
        port = next((p for p in range(start, end + 1) if p not in used and available(p)), None)
        if port is None:
            raise ValueError(f'Port pool {start}-{end} exhausted; inspect owners in {path} or explicitly adjust the pool')
        base = Path('/tmp') / f'cwe-{os.getuid()}'
        base.mkdir(mode=0o700, exist_ok=True)
        if base.is_symlink() or base.stat().st_uid != os.getuid() or base.stat().st_mode & 0o077:
            raise ValueError(f'Unsafe TMP base: {base}')
        digest = hashlib.sha256(str(worktree).encode()).hexdigest()
        tmp = None
        for size in range(12, 65, 4):
            candidate = base / digest[:size]
            if len(str(candidate / 'CUBRID65535').encode()) >= 108:
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
        result = {'worktree': str(worktree), 'master_port': port, 'tmp': str(tmp)}
        records.append(result)
        atomic_json(path, records)
        return result
