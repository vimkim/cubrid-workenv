"""Continue a recorded owned fixture, preserving logs for manual failure cleanup.

Only use the initially empty source fixture made by real_source_workflow.py.
The preflight requires no remaining owned process except its build Gradle daemon.
Owned, unbound stale sockets are unlinked only after that daemon has exited.
Rejected standalone PL may exit after its parent utility; await actual B exit.
The retained fixture and separate evidence let the creator inspect failed runs.
"""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--prior', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--db-name', default='shareprobe')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
old = json.loads(args.prior.read_text())
root = Path(old['fixture'])
b = root / 'b'
a = Path(old['source'])
install = Path(old['install'])
out = args.output.resolve()
out.mkdir(exist_ok=False)
cli = repo / 'bin/cub-workenv'
rec = {'steps': [], 'source_workflow_prior': '../ticket09-flow/results.json'}
envs = {}
for n, w in [('a', a), ('b', b)]:
    r = subprocess.run(['bash', '-c', 'source "$1" && env -0', 'bash', str(w / '.cub-workenv/env.sh')], capture_output=True, check=True)
    envs[n] = dict((x.split('=', 1) for x in r.stdout.decode().split('\x00') if '=' in x))

def run(label, argv, env=None, rc=0):
    with (out / (label + '.txt')).open('w') as f:
        p = subprocess.run(list(map(str, argv)), stdout=f, stderr=subprocess.STDOUT, env=env, timeout=60, cwd=root)
    rec['steps'].append({'label': label, 'argv': list(map(str, argv)), 'returncode': p.returncode})
    assert p.returncode in ((0, 1) if rc is None else (rc,)), (label, (out / (label + '.txt')).read_text())
    return (out / (label + '.txt')).read_text()

def owned():
    d = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            e = (p / 'environ').read_bytes().split(b'\x00')
            if any((b'CUBRID=' + os.fsencode(x) in e for x in (install, root / 'install-b'))):
                d.append({'pid': int(p.name), 'cmd': (p / 'cmdline').read_bytes().replace(b'\x00', b' ').decode(), 'install': next((x[7:].decode() for x in e if x.startswith(b'CUBRID=')))})
        except OSError:
            pass
    return d
rec['build_daemons'] = owned()
for process in rec['build_daemons']:
    assert 'org.gradle.launcher.daemon.bootstrap.GradleDaemon' in process['cmd'], process
    os.kill(process['pid'], signal.SIGTERM)
for _ in range(100):
    if not owned():
        break
    time.sleep(0.1)
assert not owned()
rec['stopped_socket_remedies'] = []
for work in (a, b):
    state = json.loads((work / '.cub-workenv/state.json').read_text())
    for stale in Path(state['allocation']['tmp']).iterdir():
        assert stale.name.startswith('sp_') or stale.name == 'CUBRID' + str(state['allocation']['master_port'])
        assert stale.is_socket() and stale.lstat().st_uid == os.getuid()
        assert str(stale) not in Path('/proc/net/unix').read_text()
        rec['stopped_socket_remedies'].append({'path': str(stale), 'inode': stale.lstat().st_ino})
        stale.unlink()
run('post-jdbc-source-doctor', [cli, 'doctor', '--worktree', a])
run('post-jdbc-source-start', ['cubrid', 'server', 'start', 'testdb'], envs['a'])
assert '901' in run('post-jdbc-sentinel', ['csql', '-C', '-u', 'dba', '-c', 'select id from workflow_marker;', 'testdb'], envs['a'])
run('create-shared', [cli, 'create-db', args.db_name, '--worktree', a, '--path', root / args.db_name])
registry_a = a / '.cub-workenv/databases/databases.txt'
registry_b = b / '.cub-workenv/databases/databases.txt'
line = next((l for l in registry_a.read_text().splitlines() if l.split()[0] == args.db_name))
registry_b.write_text(registry_b.read_text() + line + '\n')
run('shared-a-start', ['cubrid', 'server', 'start', args.db_name], envs['a'])
run('shared-b-rejected', ['csql', '-S', '-u', 'dba', '-c', 'select 1;', args.db_name], envs['b'], 1)
run('b-stale-doctor', [cli, 'doctor', '--worktree', b, '--native-error-file', out / 'shared-b-rejected.txt'], rc=None)
for _ in range(150):
    if not any((q['install'] == str(root / 'install-b') for q in owned())):
        break
    time.sleep(0.2)
state_b = json.loads((b / '.cub-workenv/state.json').read_text())
sock = Path(state_b['allocation']['tmp']) / ('sp_' + args.db_name + '.sock')
assert sock.is_socket()
rec['stale_socket'] = {'path': str(sock), 'inode': sock.lstat().st_ino, 'uid': sock.lstat().st_uid}
assert sock.lstat().st_uid == os.getuid()
assert str(sock) not in Path('/proc/net/unix').read_text()
assert not [q for q in owned() if q['install'] == str(root / 'install-b')]
for proc in Path('/proc').glob('[0-9]*'):
    try:
        assert b'CUBRID=' + os.fsencode(root / 'install-b') not in (proc / 'environ').read_bytes().split(b'\x00')
    except OSError:
        pass
sock.unlink()
run('b-after-owned-socket-remedy', [cli, 'doctor', '--worktree', b])
for db in (args.db_name, 'testdb'):
    run('stop-' + db, ['cubrid', 'server', 'stop', db], envs['a'])
run('master-stop', ['cubrid', 'service', 'stop'], envs['a'])
assert not owned(), owned()
rec['binary_sha256'] = {n: hashlib.sha256((install / 'bin' / n).read_bytes()).hexdigest() for n in ('cubrid', 'csql', 'cub_server')}
rec['jdbc_sha256'] = hashlib.sha256((install / 'jdbc/cubrid_jdbc.jar').read_bytes()).hexdigest()
rec['source_unchanged_binaries'] = rec['binary_sha256'] == old['binary_sha256']
rec['remaining_owned_pids'] = owned()
rec['verdict'] = 'pass'
(out / 'results.json').write_text(json.dumps(rec, indent=2) + '\n')
print(rec['verdict'])
