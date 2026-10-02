#!/usr/bin/env python3
"""Probe native DB exclusion using copied binaries and disposable storage only."""
import argparse
import hashlib
import json
import os
import re
import pwd
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
db = 'testdb'
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
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
    for instance in ('a', 'b'):
        prefix = root / instance
        prefix.mkdir()
        for component in ('bin', 'lib', 'msg', 'locales', 'timezones', 'conf', 'vm'):
            if (source / component).exists():
                subprocess.run(['cp', '-a', '--reflink=auto', str(source / component), str(prefix / component)], check=True)
        for directory in ('log', 'var/pl', 'var/CUBRID_SOCK'):
            (prefix / directory).mkdir(parents=True, exist_ok=True)
        (root / (instance + '-source')).mkdir()

    def prepare(instance, extra):
        worktree = root / (instance + '-source')
        argv = [str(cli), 'init', '--worktree', str(worktree), '--install', str(root / instance),
                '--preset', 'debug_gcc', '--state-home', str(root / 'host'),
                '--port-start', '44000', '--port-end', '44999', *extra]
        result = subprocess.run(argv, capture_output=True, text=True)
        (out / (instance + '-init.txt')).write_text(result.stdout + result.stderr)
        results['steps'].append({'label': instance + '-init', 'argv': argv, 'returncode': result.returncode})
        assert result.returncode == 0, result.stderr
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c',
            'source "$1" && env -0', 'bash', str(worktree / '.cub-workenv/env.sh')],
            capture_output=True, text=True, check=True)
        envs[instance] = dict(x.split('=', 1) for x in result.stdout.split('\0') if '=' in x)
        for filename in ('conf/cubrid.conf', 'state.json', 'databases/databases.txt'):
            shutil.copyfile(worktree / '.cub-workenv' / filename, out / (instance + '-' + Path(filename).name))
        return worktree / '.cub-workenv/databases/databases.txt'

    registry_path = prepare('a', ['--no-db'])
    assert registry_path.read_bytes() == b''
    assert not (root / 'shared').exists()
    result = subprocess.run([str(cli), 'create-db', db, '--worktree', str(root / 'a-source'),
                            '--path', str(root / 'shared')], capture_output=True, text=True)
    (out / 'create.txt').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    results['steps'].append({'label': 'create-db', 'argv': result.args, 'returncode': result.returncode})
    results['binary_sha256'] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                                for name in ('bin/cubrid', 'bin/csql', 'bin/cub_server', 'lib/libcubridsa.so', 'lib/libcubrid.so')}
    require_success('version', 'a', ['cubrid', '--version'])
    require_success('a-start', 'a', ['cubrid', 'server', 'start', db])
    sql('seed', 'a', 'create table marker (id integer primary key); insert into marker values (1); commit;')
    registry = registry_path.read_bytes()
    # Reuse while the owning server is running: initialization must never probe standalone.
    extra = b'# retained extra registration\nextra /unrelated localhost /unrelated/log file:/unrelated/lob\n'
    registry_path.write_bytes(registry + extra)
    reused = prepare('b', ['--database-registry', str(registry_path)])
    assert reused.read_bytes() == registry + extra
    initial = snapshot('owner-before')
    owner = next(x['pid'] for x in initial if x['instance'] == 'a' and 'cub_server' in x['cmdline'])
    results['owner_pid'] = owner
    active_log = root / 'shared/log' / (db + '_lgat')
    st = active_log.stat()
    results['active_log_identity'] = {'device': st.st_dev, 'inode': st.st_ino}
    assert str(st.st_ino) in (out / 'owner-before-locks.txt').read_text(), 'No owner lock on the active log'
    code, text = command('b-server-rejected', 'b', ['cubrid', 'server', 'start', db])
    assert isinstance(code, int) and code != 0, ('second server not rejected', code, text)
    assert str(root / 'shared/log') in text and ('lock' in text.lower() or 'used' in text.lower()), text
    assert str(owner) in text, 'Error did not identify the owner PID'
    assert pwd.getpwuid(os.getuid()).pw_name in text and socket.gethostname() in text, text
    assert Path(f'/proc/{owner}').exists(), 'Owner died after competing server start'
    output = sql('a-health-after-server', 'a', 'insert into marker values (2); commit; select count(*) as marker_count from marker;')
    assert re.search(r'^\s*2\s*$', output, re.MULTILINE), output
    status = require_success('b-status-after-rejection', 'b', ['cubrid', 'server', 'status'])
    assert db not in status, 'Rejected server registered in B'
    code, text = command('b-standalone-rejected', 'b', ['csql', '-S', '-u', 'dba', '-c', 'select count(*) from marker;', db])
    assert isinstance(code, int) and code != 0, ('standalone not rejected', code, text)
    assert str(root / 'shared/log') in text and ('lock' in text.lower() or 'used' in text.lower()), text
    assert str(owner) in text, 'Error did not identify the owner PID'
    assert pwd.getpwuid(os.getuid()).pw_name in text and socket.gethostname() in text, text
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
    duplicate = subprocess.run([str(cli), 'create-db', db, '--worktree', str(root / 'b-source'),
                                '--path', str(root / 'must-not-exist')], capture_output=True, text=True)
    (out / 'duplicate.txt').write_text(duplicate.stdout + duplicate.stderr)
    results['steps'].append({'label': 'duplicate', 'argv': duplicate.args, 'returncode': duplicate.returncode})
    assert duplicate.returncode != 0 and not (root / 'must-not-exist').exists()
    assert reused.read_bytes() == registry + extra
    settings = root / 'b-source/.cub-workenv/conf/cubrid.conf'
    settings.write_text(settings.read_text() + '# user setting preserved\n')
    settings_before = settings.read_bytes()
    added = subprocess.run([str(cli), 'create-db', 'additional', '--worktree', str(root / 'b-source')],
                           capture_output=True, text=True)
    (out / 'additional.txt').write_text(added.stdout + added.stderr)
    results['steps'].append({'label': 'additional', 'argv': added.args, 'returncode': added.returncode})
    assert added.returncode == 0, added.stderr
    assert reused.read_bytes().startswith(registry + extra), 'Existing registry bytes changed during create-db'
    assert settings.read_bytes() == settings_before
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
    if not results['cleanup_remaining']:
        for marker in root.glob('*-source/.cub-workenv/state.json'):
            state = json.loads(marker.read_text())
            shutil.rmtree(state['allocation']['tmp'], ignore_errors=True)
        shutil.rmtree(root)
    results['runtime_removed'] = not root.exists()
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
