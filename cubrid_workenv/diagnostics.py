"""Read-only Linux observations. No utility execution, DB opens or reservations."""
import configparser
import json
import os
from pathlib import Path

from .database import registrations


def settings_problems(state):
    root = Path(state['worktree']) / '.cub-workenv'
    allocation = state['allocation']
    problems = []
    if allocation.get('install') != state.get('install'):
        problems.append(f'Selected installation {state.get("install")} differs from allocation installation {allocation.get("install")}; inspect the intended preset manually')
    for filename, expected in (
        ('cubrid.conf', {('common', 'cubrid_port_id'): allocation['master_port']}),
        ('cubrid_broker.conf', {('broker', 'master_shm_id'): allocation['broker_master_shm_id'],
                               ('%workenv', 'broker_port'): allocation['broker_port'],
                               ('%workenv', 'appl_server_shm_id'): allocation['broker_appl_server_shm_id']})):
        config = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=('#', ';'))
        try:
            with (root / 'conf' / filename).open() as stream:
                config.read_file(stream)
            for (section, key), value in expected.items():
                raw = config.get(section, key, fallback='')
                try:
                    actual = int(raw, 16 if 'shm_id' in key else 10)
                except ValueError:
                    actual = None
                if actual != value:
                    problems.append(f'{filename} [{section}] {key}={raw!r} differs from allocation {value}')
            for section in config.sections():
                if filename == 'cubrid_broker.conf' and section.startswith('%') and section != '%workenv':
                    if config.get(section, 'service', fallback='on').lower() not in ('off', 'no', 'false', '0'):
                        problems.append(f'{filename} [{section}]: enabled broker uses unallocated resources; inspect its BROKER_PORT/APPL_SERVER_SHM_ID and record an explicit allocation manually')
                if filename == 'cubrid.conf' and section.startswith('@'):
                    raw = config.get(section, 'cubrid_port_id', fallback=str(allocation['master_port']))
                    if raw != str(allocation['master_port']):
                        problems.append(f'{filename} [{section}] cubrid_port_id={raw} differs from allocation {allocation["master_port"]}')
                for key, value in config.items(section):
                    if key == 'file_lock' and value.lower() in ('no', 'off', 'false', '0'):
                        problems.append(f'{filename} [{section}] file_lock={value}: native DB locking is disabled; restore file_lock=yes before shared storage use (docs/doctor.md)')
                    if filename == 'cubrid.conf' and key == 'stored_procedure_uds' and value.lower() in ('no', 'off', 'false', '0'):
                        problems.append(f'{filename} [{section}] stored_procedure_uds={value}: allocated PL socket isolation is disabled; inspect TCP configuration manually')
        except (OSError, configparser.Error) as error:
            problems.append(f'Cannot inspect {filename}: {error}')
    if os.environ.get('CUBRID_CONF_FILE') == str(root / 'conf/cubrid.conf'):
        value = os.environ.get('CUBRID_FILE_LOCK', '')
        if value.lower() in ('no', 'off', 'false', '0'):
            problems.append(f'Current selected environment CUBRID_FILE_LOCK={value}: native DB locking is disabled; correct the launch environment manually')
    return problems


def database_rows(worktree):
    return registrations((Path(worktree) / '.cub-workenv/databases/databases.txt').read_bytes())


def registry_problems(worktree):
    problems = []
    try:
        rows = database_rows(worktree)
    except (OSError, ValueError) as error:
        return {}, [f'Cannot inspect DB registry: {error}']
    for name, fields in rows.items():
        if len(fields) not in (4, 5):
            problems.append(f'DB {name}: malformed registry row; expected name/data/host/log with optional LOB')
            continue
        # Remote and non-file LOB registrations are valid CUBRID extensions;
        # report our inspection boundary, never declare their storage corrupt.
        if fields[2] != 'localhost' or (len(fields) == 5 and not fields[4].startswith('file:')):
            print(f'DB {name}: remote host or non-file LOB; physical storage not verified')
            continue
        paths = [Path(fields[1]), Path(fields[3])]
        if len(fields) == 5:
            paths.append(Path(fields[4][5:]))
        for path in paths:
            if not path.is_absolute() or not path.is_dir():
                problems.append(f'DB {name}: missing or inaccessible absolute storage directory {path}')
        for path in (paths[0] / name, paths[1] / (name + '_lgat')):
            if not path.is_file():
                problems.append(f'DB {name}: missing physical volume or active log {path}; preserve storage and inspect registration manually')
        print(f'DB {name}: data={paths[0]} log={paths[1]} LOB={paths[2] if len(paths) == 3 else "not registered"} (registration inspection only)')
    return rows, problems


def process_snapshot():
    processes = {}
    inaccessible = 0
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            env = dict(item.split(b'=', 1) for item in (directory / 'environ').read_bytes().split(b'\0') if b'=' in item)
            sockets = set()
            for fd in (directory / 'fd').iterdir():
                try:
                    target = os.readlink(fd)
                    if target.startswith('socket:['):
                        sockets.add(target[8:-1])
                except FileNotFoundError:
                    pass
            processes[int(directory.name)] = (env, sockets)
        except (FileNotFoundError, ProcessLookupError):
            pass
        except PermissionError:
            inaccessible += 1
    return processes, inaccessible


def owner_worktree(pid, processes, records, active_log=None):
    """Require exact instance environment, and DB inode when attributing a DB."""
    if pid not in processes:
        return None
    env = processes[pid][0]
    matches = []
    for record in records:
        try:
            root = Path(record['worktree']) / '.cub-workenv'
            expected = {'CUBRID': record['install'], 'CUBRID_CONF_FILE': str(root / 'conf/cubrid.conf'),
                        'CUBRID_DATABASES': str(root / 'databases'), 'CUBRID_TMP': record['tmp'],
                        'CUBRID_CUBRID_PORT_ID': str(record['master_port'])}
            if not all(env.get(key.encode()) == str(value).encode() for key, value in expected.items()):
                continue
            if active_log is not None:
                rows = database_rows(record['worktree'])
                if not any(len(fields) in (4, 5) and fields[2] == 'localhost' and (Path(fields[3]) / (name + '_lgat')).samefile(active_log)
                           for name, fields in rows.items()):
                    continue
            matches.append(record['worktree'])
        except (OSError, ValueError, KeyError):
            continue
    return matches[0] if len(matches) == 1 else None


def lock_owners(lines, stat):
    """Yield holders for one inode; blocked lock requests are not owners."""
    identity = (os.major(stat.st_dev), os.minor(stat.st_dev), stat.st_ino)
    for line in lines:
        parts = line.split()
        if len(parts) < 6 or parts[1] == '->':
            continue
        device = parts[5].split(':')
        if len(device) == 3 and (int(device[0], 16), int(device[1], 16), int(device[2])) == identity:
            yield int(parts[4])


def resource_observations(state, rows):
    problems = []
    allocation = state['allocation']
    path = Path(state['state_home']) / 'allocations.json'
    try:
        records = json.loads(path.read_text())
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise ValueError('expected allocation objects')
    except (OSError, ValueError) as error:
        return [], {}, [f'Cannot inspect allocation records: {error}']
    for record in records:
        if record == allocation:
            continue
        for keys in (('master_port', 'broker_port'), ('broker_master_shm_id', 'broker_appl_server_shm_id'), ('tmp',), ('install',)):
            for key in keys:
                if allocation.get(key) is not None and allocation[key] in [record.get(k) for k in keys]:
                    problems.append(f'Allocation conflict: {key}={allocation[key]} also recorded for {record.get("worktree", "unknown worktree")}')
    processes, inaccessible = process_snapshot()
    print(f'Process inspection: {inaccessible} inaccessible PIDs; absent owner evidence is not proof of inactivity')
    for pid, (env, _) in processes.items():
        if owner_worktree(pid, processes, records) == state['worktree']:
            value = env.get(b'CUBRID_FILE_LOCK', b'').decode(errors='replace')
            if value.lower() in ('no', 'off', 'false', '0'):
                problems.append(f'PID {pid} CUBRID_FILE_LOCK={value}: native DB locking is disabled by process environment; correct the launch environment manually before shared storage use')

    def occupied(label, pids):
        owners = [(pid, owner_worktree(pid, processes, records)) for pid in sorted(pids)]
        text = ', '.join(f'PID {pid} worktree={owner or "unconfirmed"}' for pid, owner in owners) or 'PID/worktree unconfirmed'
        print(f'{label}: occupied; {text}')
        if not owners or any(owner != state['worktree'] for _, owner in owners):
            problems.append(f'{label}: occupancy conflicts with allocation or owner is unconfirmed; inspect PID and resource manually')

    try:
        for table in ('tcp', 'tcp6'):
            for line in (Path('/proc/net') / table).read_text().splitlines()[1:]:
                fields = line.split()
                port = int(fields[1].split(':')[1], 16)
                if port in (allocation['master_port'], allocation['broker_port']) and fields[3] != '06':
                    occupied(f'TCP {port}', {pid for pid, (_, sockets) in processes.items() if fields[9] in sockets})
        live_paths = set()
        for line in Path('/proc/net/unix').read_text().splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 8 and fields[7].startswith(allocation['tmp'] + '/'):
                live_paths.add(fields[7])
                occupied(f'Unix socket {fields[7]}', {pid for pid, (_, sockets) in processes.items() if fields[6] in sockets})
        expected_paths = [Path(allocation['tmp']) / f"CUBRID{allocation['master_port']}"]
        expected_paths.extend(Path(allocation['tmp']) / f'sp_{name}.sock' for name in rows)
        for socket_path in expected_paths:
            if (socket_path.exists() or socket_path.is_symlink()) and str(socket_path) not in live_paths:
                problems.append(f'Unix socket path {socket_path}: stale or unconfirmed filesystem entry; inspect its owner manually before any removal')
        for line in Path('/proc/sysvipc/shm').read_text().splitlines()[1:]:
            fields = line.split()
            if int(fields[0]) in (allocation['broker_master_shm_id'], allocation['broker_appl_server_shm_id']):
                # Creator PID is historical. Attribute only if still alive and
                # actually mapped to the segment, not merely a reused PID.
                key = int(fields[0])
                pids = set()
                for pid in processes:
                    try:
                        if f'/SYSV{key:08x}' in Path(f'/proc/{pid}/maps').read_text():
                            pids.add(pid)
                    except (OSError, ValueError):
                        pass
                occupied(f'SysV shared memory {key:#x}', pids)
        locks = Path('/proc/locks').read_text().splitlines()
        for name, fields in rows.items():
            if len(fields) not in (4, 5) or fields[2] != 'localhost':
                continue
            active = Path(fields[3]) / (name + '_lgat')
            try:
                stat = active.stat()
            except OSError:
                continue
            for pid in lock_owners(locks, stat):
                owner = owner_worktree(pid, processes, records, active)
                print(f'DB {name}: native active-log lock PID {pid}, worktree={owner or "unconfirmed"}, path={active}; another independent opener must wait for normal release')
    except (OSError, ValueError, IndexError) as error:
        problems.append(f'Cannot completely inspect live resources: {error}; inspect manually')
    return records, processes, problems


def explain_native_error(path, records, processes):
    """Echo native output verbatim; historical errors alone cannot prove ownership."""
    import re
    import socket
    import pwd
    text = path.read_text(errors='replace')
    print(f'Native error from {path} (preserved):')
    print(text, end='' if text.endswith('\n') else '\n')
    confirmed = False
    for match in re.finditer(r'in use by user (\S+) on process (\d+) of host (\S+)', text):
        user, pid, host = match.groups()
        pid = int(pid)
        if host != socket.gethostname():
            continue
        try:
            if pwd.getpwuid(Path(f'/proc/{pid}').stat().st_uid).pw_name != user:
                continue
            for volume in re.findall(r'"([^"\n]+_lgat)"', text):
                active = Path(volume)
                stat = active.stat()
                if pid in lock_owners(Path('/proc/locks').read_text().splitlines(), stat):
                    owner = owner_worktree(pid, processes, records, active)
                    if owner:
                        print(f'Native owner confirmed now: PID {pid}, worktree={owner}, active log={active}')
                        confirmed = True
        except (OSError, KeyError, ValueError):
            pass
    if not confirmed:
        print('Native owner worktree unconfirmed: historical PID/host information is not sufficient; inspect on the named host. No takeover performed.')
