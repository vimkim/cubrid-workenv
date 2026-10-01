#!/usr/bin/env python3
"""Probe native DB exclusion using copied binaries and disposable storage only."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--install', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
source = args.install.resolve()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
root = Path(tempfile.mkdtemp(prefix='cwe-lock-', dir='/tmp'))
db = 'lockprobe'
results = {'runtime_root': str(root), 'install_source': str(source), 'steps': []}
envs = {}


def owned_processes():
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            entries = (proc / 'environ').read_bytes().split(b'\0')
            owner = next((x[7:].decode() for x in entries if x.startswith(b'CUBRID=')), '')
            if owner in {str(root / 'a'), str(root / 'b')}:
                found.append({'pid': int(proc.name), 'instance': Path(owner).name,
                              'cmdline': (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')})
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return found


def command(label, instance, argv, timeout=45):
    start = time.monotonic()
    log = out / (label + '.txt')
    full = [str(root / instance / 'bin' / argv[0]), *argv[1:]]
    with log.open('w') as stream:
        try:
            proc = subprocess.run(full, env=envs[instance], cwd=root / instance,
                                  stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 'timeout'
    entry = {'label': label, 'instance': instance, 'argv': argv, 'returncode': code,
             'seconds': round(time.monotonic() - start, 3)}
    results['steps'].append(entry)
    print(json.dumps(entry), flush=True)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return code, log.read_text(errors='replace')


def require_success(label, instance, argv):
    code, output = command(label, instance, argv)
    assert code == 0, (label, code, output)
    return output


def sql(label, instance, query, standalone=False):
    return require_success(label, instance, ['csql', '-S' if standalone else '-C', '-u', 'dba', '-c', query, db])


def snapshot(label):
    processes = owned_processes()
    (out / (label + '-processes.json')).write_text(json.dumps(processes, indent=2) + '\n')
    pids = {str(x['pid']) for x in processes}
    lines = [line for line in Path('/proc/locks').read_text().splitlines()
             if len(line.split()) > 4 and line.split()[4] in pids]
    (out / (label + '-locks.txt')).write_text('\n'.join(lines) + '\n')
    return processes


try:
    reservations = []
    ports = []
    for instance in ('a', 'b'):
        sock = socket.socket()
        sock.bind(('0.0.0.0', 0))
        reservations.append(sock)
        ports.append(sock.getsockname()[1])
        prefix = root / instance
        prefix.mkdir()
        for component in ('bin', 'lib', 'msg', 'locales', 'timezones', 'conf', 'vm'):
            if (source / component).exists():
                subprocess.run(['cp', '-a', '--reflink=auto', str(source / component), str(prefix / component)], check=True)
        for directory in ('tmp', 'databases', 'log', 'var', 'var/pl', 'var/CUBRID_SOCK'):
            (prefix / directory).mkdir(parents=True, exist_ok=True)
        (prefix / 'databases/databases.txt').write_text('')
        config = ('[common]\n' + f'cubrid_port_id={ports[-1]}\n' +
                  'data_buffer_size=64M\nlog_buffer_size=16M\nmax_clients=20\n'
                  'stored_procedure=no\nha_mode=off\n')
        (prefix / 'conf/cubrid.conf').write_text(config)
        (out / f'{instance}-cubrid.conf').write_text(config)
        env = {k: v for k, v in os.environ.items() if not k.startswith('CUBRID') and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH')}
        env.update(CUBRID=str(prefix), CUBRID_DATABASES=str(prefix / 'databases'),
                   CUBRID_TMP=str(prefix / 'tmp'), CUBRID_CONF_FILE=str(prefix / 'conf/cubrid.conf'),
                   PATH=str(prefix / 'bin') + ':/usr/bin:/bin', LD_LIBRARY_PATH=str(prefix / 'lib'), LC_ALL='C')
        envs[instance] = env
    results['ports'] = dict(zip(('a', 'b'), ports))
    results['binary_sha256'] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                                for name in ('bin/cubrid', 'bin/csql', 'bin/cub_server', 'lib/libcubridsa.so', 'lib/libcubrid.so')}
    require_success('version', 'a', ['cubrid', '--version'])
    for component in ('data', 'logs', 'lob'):
        (root / 'shared' / component).mkdir(parents=True, exist_ok=True)
    require_success('create', 'a', ['cubrid', 'createdb', '--db-volume-size=64M', '--log-volume-size=32M',
                                  '-F', str(root / 'shared/data'), '-L', str(root / 'shared/logs'),
                                  '-B', str(root / 'shared/lob'), '--server-name=localhost', db, 'en_US.utf8'])
    registry = (root / 'a/databases/databases.txt').read_text()
    (root / 'b/databases/databases.txt').write_text(registry)
    (out / 'shared-databases.txt').write_text(registry)
    for sock in reservations:
        sock.close()
    require_success('a-start', 'a', ['cubrid', 'server', 'start', db])
    sql('seed', 'a', 'create table marker (id integer primary key); insert into marker values (1); commit;')
    initial = snapshot('owner-before')
    owner = next(x['pid'] for x in initial if x['instance'] == 'a' and 'cub_server' in x['cmdline'])
    results['owner_pid'] = owner
    active_log = root / 'shared/logs' / (db + '_lgat')
    st = active_log.stat()
    results['active_log_identity'] = {'device': st.st_dev, 'inode': st.st_ino}
    assert str(st.st_ino) in (out / 'owner-before-locks.txt').read_text(), 'No owner lock on the active log'
    code, text = command('b-server-rejected', 'b', ['cubrid', 'server', 'start', db])
    assert isinstance(code, int) and code != 0, ('second server not rejected', code, text)
    assert str(root / 'shared/logs') in text and ('lock' in text.lower() or 'used' in text.lower()), text
    assert str(owner) in text, 'Error did not identify the owner PID'
    assert Path(f'/proc/{owner}').exists(), 'Owner died after competing server start'
    output = sql('a-health-after-server', 'a', 'insert into marker values (2); commit; select count(*) as marker_count from marker;')
    assert re.search(r'^\s*2\s*$', output, re.MULTILINE), output
    status = require_success('b-status-after-rejection', 'b', ['cubrid', 'server', 'status'])
    assert db not in status, 'Rejected server registered in B'
    code, text = command('b-standalone-rejected', 'b', ['csql', '-S', '-u', 'dba', '-c', 'select count(*) from marker;', db])
    assert isinstance(code, int) and code != 0, ('standalone not rejected', code, text)
    assert str(root / 'shared/logs') in text and ('lock' in text.lower() or 'used' in text.lower()), text
    assert str(owner) in text, 'Error did not identify the owner PID'
    assert Path(f'/proc/{owner}').exists(), 'Owner died after standalone attempt'
    output = sql('a-health-after-standalone', 'a', 'insert into marker values (3); commit; select count(*) as marker_count from marker;')
    assert re.search(r'^\s*3\s*$', output, re.MULTILINE), output
    after = snapshot('owner-after')
    assert [x['pid'] for x in after if 'cub_server' in x['cmdline']] == [owner], 'Unexpected second server'
    require_success('a-stop', 'a', ['cubrid', 'server', 'stop', db])
    require_success('b-start-after-release', 'b', ['cubrid', 'server', 'start', db])
    output = sql('b-read-after-handoff', 'b', 'select count(*) as marker_count from marker;')
    assert re.search(r'^\s*3\s*$', output, re.MULTILINE), output
    require_success('b-stop', 'b', ['cubrid', 'server', 'stop', db])
    output = sql('b-standalone-after-release', 'b', 'select count(*) as marker_count from marker;', standalone=True)
    assert re.search(r'^\s*3\s*$', output, re.MULTILINE), output
    results['verdict'] = 'pass'
except BaseException as error:
    results['verdict'] = 'fail'
    results['error'] = repr(error)
    raise
finally:
    # Terminate only processes with this unique experiment's exact CUBRID prefix.
    before = owned_processes()
    results['cleanup_processes'] = before
    for item in before:
        try:
            os.kill(item['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while owned_processes() and time.monotonic() < deadline:
        time.sleep(0.2)
    remaining = owned_processes()
    for item in remaining:
        try:
            os.kill(item['pid'], signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(0.2)
    results['cleanup_remaining'] = owned_processes()
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('verdict:', results.get('verdict'), 'remaining:', results['cleanup_remaining'], flush=True)
    # Retain disposable files for inspection; never remove storage while processes remain.
    print('disposable runtime retained at', root, flush=True)
