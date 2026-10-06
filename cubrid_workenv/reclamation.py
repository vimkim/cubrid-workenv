"""Read-only evidence for releasing records, never operating-system resources."""
import os
from pathlib import Path
import stat


def deleted_path(path):
    """Do not confuse inaccessible or dangling-symlink ancestors with deletion."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return True, 'worktree deleted'
        except OSError as error:
            return False, f'path inspection uncertain: {current}: {error}'
        if stat.S_ISLNK(info.st_mode):
            return False, f'path inspection uncertain: symlink {current}'
        if not stat.S_ISDIR(info.st_mode):
            return False, f'path inspection uncertain: not a directory {current}'
    return False, 'worktree still exists (stopped allocations are retained)'


def process_reason(record, ignored_ancestors=()):
    roots = [record['worktree'], record['tmp']]
    if record.get('install'):
        roots.append(record['install'])

    def matches(value):
        value = value.removesuffix(' (deleted)')
        return any(value == root or value.startswith(root + '/') for root in roots)

    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal() or int(entry.name) == os.getpid():
            continue
        words = []
        try:
            info = entry.stat()
            # An unreaped zombie has no running code or open descriptors. Its
            # environ may return EACCES instead of disappearing from /proc.
            if (entry / 'stat').read_text().rsplit(')', 1)[1].split()[0] in ('Z', 'X'):
                continue
            command = (entry / 'cmdline').read_bytes().split(b'\0')
            words = [word.decode(errors='replace') for word in command if word]
            # Foreign ordinary daemons cannot be inspected through environ;
            # CUBRID and Java candidates still require proof and fail closed.
            candidate = any(Path(word).name.startswith(('cub_', 'cubrid', 'csql', 'java'))
                            for word in words[:1])
            if int(entry.name) in ignored_ancestors and not candidate:
                continue
            if any(matches(word) for word in words):
                return f'live process PID {entry.name} references allocation paths'
            if info.st_uid != os.getuid() and not candidate:
                continue
            environment = (entry / 'environ').read_bytes().split(b'\0')
            for item in environment:
                key, _, value = item.partition(b'=')
                if key.startswith(b'CUBRID') and (matches(value.decode(errors='replace')) or
                        (key == b'CUBRID_CUBRID_PORT_ID' and value == str(record.get('master_port')).encode())):
                    return f'live owner PID {entry.name} has allocation environment'
            for link in ('cwd', 'exe'):
                if matches(os.readlink(entry / link)):
                    return f'live process PID {entry.name} uses allocation {link}'
        except (FileNotFoundError, ProcessLookupError):
            continue  # Exited process (including an already dead zombie).
        except OSError as error:
            return f'process inspection uncertain at PID {entry.name}: {error}'
    return None


def inactive_reason(record, available, occupied_keys):
    deleted, reason = deleted_path(Path(record['worktree']))
    if not deleted:
        return reason
    for field in ('master_port', 'broker_port'):
        if field not in record:
            if record.get('status') == 'reset':
                continue
            return f'incomplete allocation: missing {field}'
        if not available(record[field]):
            return f'occupied or inaccessible TCP port {record[field]} ({field})'
    for field in ('broker_master_shm_id', 'broker_appl_server_shm_id'):
        if field not in record:
            if record.get('status') == 'reset':
                continue
            return f'incomplete allocation: missing {field}'
        if record[field] in occupied_keys:
            return f'SysV shared memory remains at key {record[field]:#x} ({field}); ownership uncertain'
    try:
        # The short recorded TMP directory is the only filesystem enumeration.
        # Any remaining entry is conservative evidence; never unlink stale IPC.
        tmp = Path(record['tmp'])
        if tmp.is_symlink():
            return f'socket inspection uncertain: symlink {tmp}'
        try:
            entries = list(tmp.iterdir())
        except FileNotFoundError:
            entries = []
        if entries:
            return f'socket/TMP entries remain at {tmp}; ownership uncertain'
        # Also detect a bound socket whose pathname was unlinked.
        for line in Path('/proc/net/unix').read_text().splitlines()[1:]:
            fields = line.split(maxsplit=7)
            if len(fields) == 8 and (fields[7] == str(tmp) or fields[7].startswith(str(tmp) + '/')):
                return f'live Unix socket remains at {fields[7]}'
        return process_reason(record)
    except OSError as error:
        return f'activity inspection uncertain: {error}'
