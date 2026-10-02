#!/usr/bin/env python3
"""Disposable live doctor probe with syscall and artifact evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--install', type=Path, required=True)
parser.add_argument('--java-home', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
root = Path(tempfile.mkdtemp(prefix='cwe-doctor-native-', dir='/tmp'))
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
results = {'root': str(root), 'source': str(args.install), 'steps': [], 'binary_hashes': {}}
envs = {}


def run(label, argv, env=None):
    log = out / (label + '.txt')
    with log.open('w') as stream:
        result = subprocess.run(list(map(str, argv)), env=env, cwd=root, stdout=stream, stderr=subprocess.STDOUT, text=True, timeout=60)
    result.stdout = log.read_text(errors='replace')
    result.stderr = ''
    results['steps'].append({'label': label, 'argv': list(map(str, argv)), 'returncode': result.returncode})
    return result


def owned():
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            env = (proc / 'environ').read_bytes().split(b'\0')
            if any(b'CUBRID=' + os.fsencode(root / x) in env for x in ('a', 'b')):
                found.append(int(proc.name))
        except (OSError, ProcessLookupError):
            pass
    return sorted(found)


def snapshot():
    paths = [root / 'host', root / 'a-source/.cub-workenv', root / 'b-source/.cub-workenv', root / 'shared']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for base in paths for p in base.rglob('*') if p.is_file()}


try:
    for instance in ('a', 'b'):
        install = root / instance
        install.mkdir()
        for part in ('bin', 'lib', 'msg', 'locales', 'timezones', 'conf', 'vm'):
            if (args.install / part).exists():
                subprocess.run(['cp', '-a', '--reflink=auto', str(args.install / part), str(install / part)], check=True)
        for part in ('log', 'var/pl', 'var/CUBRID_SOCK'):
            (install / part).mkdir(parents=True, exist_ok=True)
        results['binary_hashes'][instance] = {str(p.relative_to(install)): hashlib.sha256(p.read_bytes()).hexdigest() for component in ('bin', 'lib') for p in (install / component).rglob('*') if p.is_file()}
        work = root / (instance + '-source')
        work.mkdir()
        result = run(instance + '-init', [cli, 'init', '--worktree', work, '--install', install,
            '--preset', 'debug_gcc', '--java-home', args.java_home, '--no-db',
            '--state-home', root / 'host', '--port-start', '47000', '--port-end', '47999'])
        assert result.returncode == 0, result.stderr
        result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c', 'source "$1" && env -0', 'bash',
            str(work / '.cub-workenv/env.sh')], capture_output=True, text=True, check=True)
        envs[instance] = dict(x.split('=', 1) for x in result.stdout.split('\0') if '=' in x)
    assert results['binary_hashes']['a'] == results['binary_hashes']['b'], 'Source installation changed between copies'
    assert run('create', [cli, 'create-db', 'testdb', '--worktree', root / 'a-source', '--path', root / 'shared']).returncode == 0
    shutil.copyfile(root / 'a-source/.cub-workenv/databases/databases.txt', root / 'b-source/.cub-workenv/databases/databases.txt')
    def native(label, instance, *argv):
        return run(label, [root / instance / 'bin' / argv[0], *argv[1:]], envs[instance])
    assert native('version', 'a', 'cubrid', '--version').returncode == 0
    assert native('b-version', 'b', 'cubrid', '--version').returncode == 0
    assert native('start', 'a', 'cubrid', 'server', 'start', 'testdb').returncode == 0
    assert native('broker-start', 'a', 'cubrid', 'broker', 'start').returncode == 0
    assert native('seed', 'a', 'csql', '-C', '-u', 'dba', '-c', 'create table probe (id int); insert into probe values (1); commit;', 'testdb').returncode == 0
    busy = native('native-busy', 'b', 'csql', '-S', '-u', 'dba', '-c', 'select 1;', 'testdb')
    assert busy.returncode != 0
    before = snapshot()
    processes = owned()
    def socket_snapshot():
        return {str(p): (p.lstat().st_ino, p.lstat().st_mode) for work in ('a-source', 'b-source') for p in Path(json.loads((root / work / '.cub-workenv/state.json').read_text())['allocation']['tmp']).iterdir()}
    sockets_before = socket_snapshot()
    (out / 'before.json').write_text(json.dumps({'hashes': before, 'pids': processes}, indent=2) + '\n')
    for instance in ('a', 'b'):
        trace = out / (instance + '-syscalls.txt')
        result = run(instance + '-doctor', ['strace', '-f', '-e', 'trace=openat,execve,kill,unlink,rename,bind', '-o', trace,
            cli, 'doctor', '--worktree', root / (instance + '-source'), '--native-error-file', out / 'native-busy.txt'])
        if instance == 'b' and 'stale or unconfirmed filesystem entry' in result.stdout:
            assert result.returncode == 1, result.stdout
            results['expected_stale_socket_diagnosis'] = True
        else:
            assert result.returncode == 0, result.stdout + result.stderr
        assert 'Native owner confirmed now:' in result.stdout and str(root / 'a-source') in result.stdout
        for line in trace.read_text().splitlines():
            assert not ('openat(' in line and str(root / 'shared') in line), line
            assert not any(call in line for call in ('kill(', 'unlink(', 'rename(', 'bind(')), line
            assert not ('execve(' in line and str(root / 'a/bin') in line), line
    after = snapshot()
    (out / 'after.json').write_text(json.dumps({'hashes': after, 'pids': owned()}, indent=2) + '\n')
    assert before == after, 'Doctor changed protected configuration/registry/allocation/database bytes'
    assert processes == owned(), 'Owned process set changed during diagnosis'
    assert sockets_before == socket_snapshot(), 'Socket paths changed during diagnosis'
    results['socket_paths_unchanged'] = sockets_before
    health = native('health', 'a', 'csql', '-C', '-u', 'dba', '-c', 'insert into probe values (2); commit; select count(*) from probe;', 'testdb')
    assert health.returncode == 0 and re.search(r'^\s*2\s*$', health.stdout, re.M)
    results['verdict'] = 'pass'
    results['unchanged_artifacts'] = len(before)
    results['same_live_pids'] = processes
except BaseException as error:
    results['verdict'] = 'fail'
    results['error'] = repr(error)
    raise
finally:
    for instance in envs:
        for argv in (('cubrid', 'broker', 'stop'), ('cubrid', 'server', 'stop', 'testdb')):
            try:
                run(instance + '-cleanup-' + argv[1], [root / instance / 'bin' / argv[0], *argv[1:]], envs[instance])
            except subprocess.TimeoutExpired:
                pass
    for pid in owned():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while owned() and time.monotonic() < deadline:
        time.sleep(.2)
    results['cleanup_remaining'] = owned()
    if not results['cleanup_remaining']:
        for marker in root.glob('*-source/.cub-workenv/state.json'):
            shutil.rmtree(json.loads(marker.read_text())['allocation']['tmp'])
        shutil.rmtree(root)
    results['runtime_removed'] = not root.exists()
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
