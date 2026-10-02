#!/usr/bin/env python3
"""CLI-created environments: native server, JDBC broker and PL coexistence."""
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
args.output.mkdir(parents=True, exist_ok=False)
root = Path(tempfile.mkdtemp(prefix='cwe-coexist-'))
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
record = {'root': str(root), 'install_source': str(args.install), 'steps': [], 'environments': {}}
environments = {}

def owned():
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            env = (proc / 'environ').read_bytes().split(b'\0')
            if any(f'CUBRID={root / name / "install"}'.encode() in env for name in ('a', 'b')):
                found.append(int(proc.name))
        except OSError:
            pass
    return found

def ipc_rows():
    keys = {state['allocation'][key] for state in record['environments'].values()
            for key in ('broker_master_shm_id', 'broker_appl_server_shm_id')}
    return [row for row in Path('/proc/sysvipc/shm').read_text().splitlines()[1:]
            if int(row.split()[0]) in keys]


def run(label, command, env=None, check=True):
    with (args.output / f'{label}.txt').open('w') as log:
        result = subprocess.run(list(map(str, command)), cwd=root, env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=120)
    output = (args.output / f'{label}.txt').read_text()
    record['steps'].append({'label': label, 'argv': list(map(str, command)), 'returncode': result.returncode})
    if check:
        assert result.returncode == 0, (label, output)
    return output

def sql(name, label, statement):
    output = run(label, ['csql', '-C', '-u', 'dba', '-c', statement, 'testdb'], environments[name])
    assert 'ERROR' not in output, (label, output)
    return output

def health(name, label, sentinel):
    output = sql(name, label, 'insert into marker select id from marker limit 1; commit; select distinct id from marker; select cwe_abs(-17);')
    assert re.search(rf'^\s*{sentinel}\s*$', output, re.M), output
    assert re.search(r'^\s*17\s*$', output, re.M), output
    state = record['environments'][name]
    output = run(label + '-jdbc', [args.java_home / 'bin/java', '-cp', str(root) + ':' + str(root / name / 'install/jdbc/cubrid_jdbc.jar'),
                'Probe', str(state['allocation']['broker_port'])], environments[name])
    assert f'SENTINEL={sentinel}' in output, output
    assert 'PL=17' in output, output

try:
    (root / 'Probe.java').write_text('''import java.sql.*;
public class Probe {
  public static void main(String[] args) throws Exception {
    Class.forName("cubrid.jdbc.driver.CUBRIDDriver");
    try (Connection c = DriverManager.getConnection("jdbc:cubrid:localhost:" + args[0] + ":testdb:dba::", "dba", "");
         Statement s = c.createStatement()) {
      try (ResultSet r = s.executeQuery("select distinct id from marker")) {
        while(r.next()) System.out.println("SENTINEL=" + r.getInt(1));
      }
      try (ResultSet r = s.executeQuery("select cwe_abs(-17)")) {
        r.next(); System.out.println("PL=" + r.getInt(1));
      }
    }
  }
}
''')
    run('java-version', [args.java_home / 'bin/java', '-version'])
    run('javac', [args.java_home / 'bin/javac', root / 'Probe.java'])
    for name, sentinel in (('a', 111), ('b', 222)):
        worktree = root / name / 'source'
        worktree.mkdir(parents=True)
        install = root / name / 'install'
        install.mkdir()
        for part in ('bin', 'lib', 'conf', 'msg', 'locales', 'timezones', 'vm', 'jdbc'):
            if (args.install / part).exists():
                subprocess.run(['cp', '-a', '--reflink=auto', str(args.install / part), str(install / part)], check=True)
        for part in ('log', 'var/pl', 'var/CUBRID_SOCK'):
            (install / part).mkdir(parents=True, exist_ok=True)
        run(name + '-init', [cli, 'init', '--worktree', worktree, '--install', install,
            '--preset', 'debug_gcc', '--state-home', root / 'host', '--port-start', '45000', '--port-end', '45999',
            '--java-home', args.java_home])
        state = json.loads((worktree / '.cub-workenv/state.json').read_text())
        record['environments'][name] = state
        output = run(name + '-environment', ['/bin/bash', '--noprofile', '--norc', '-c', 'source "$1" && env -0', 'bash', worktree / '.cub-workenv/env.sh'])
        environments[name] = dict(x.split('=', 1) for x in output.split('\0') if '=' in x)
        # Keep only relevant environment evidence; never retain unrelated host secrets.
        (args.output / f'{name}-environment.txt').write_text(json.dumps({k:v for k,v in environments[name].items() if k.startswith('CUBRID') or k in ('PATH', 'LD_LIBRARY_PATH')}, indent=2))
        for file in ('cubrid.conf', 'cubrid_broker.conf'):
            shutil.copyfile(worktree / '.cub-workenv/conf' / file, args.output / f'{name}-{file}')
        run(name + '-version', ['cubrid', '--version'], environments[name])
        run(name + '-server-start', ['cubrid', 'server', 'start', 'testdb'], environments[name])
        sql(name, name + '-setup', f'create table marker (id integer); insert into marker values ({sentinel}); create function cwe_abs(i integer) return integer as language java name \'java.lang.Math.abs(int) return int\'; commit;')
        run(name + '-broker-start', ['cubrid', 'broker', 'start'], environments[name])
        health(name, name + '-health', sentinel)
    for name in ('a', 'b'):
        output = run(name + '-server-status', ['cubrid', 'server', 'status'], environments[name])
        assert output.count('Server testdb') == 1, output
        state = record['environments'][name]
        allocation = state['allocation']
        state['sockets'] = []
        for socket in (f"CUBRID{allocation['master_port']}", 'sp_testdb.sock'):
            path = Path(allocation['tmp']) / socket
            assert path.is_socket(), socket
            assert len(str(path).encode()) < 108
            state['sockets'].append(str(path))
        record['environments'][name]['pl_info'] = (root / name / 'install/var/pl/pl_testdb.info').read_text()
    rows = ipc_rows()
    assert len(rows) == 4, rows
    (args.output / 'ipc-before-stop.txt').write_text('key shmid perms size cpid lpid nattch uid gid cuid cgid atime dtime ctime rss swap\n' + '\n'.join(rows) + '\n')
    record['owned_pids_before_stop'] = owned()
    run('a-server-stop', ['cubrid', 'server', 'stop', 'testdb'], environments['a'])
    health('b', 'b-after-a-server-stop', 222)
    # A status is empty while B still owns testdb: proves status goes to the intended master.
    output = run('a-status-after-stop', ['cubrid', 'server', 'status'], environments['a'])
    assert 'Server testdb' not in output, output
    run('a-broker-stop', ['cubrid', 'broker', 'stop'], environments['a'])
    health('b', 'b-after-a-broker-stop', 222)
    record['verdict'] = 'pass'
finally:
    for name, env in environments.items():
        for label, command in (('broker', ['cubrid', 'broker', 'stop']),
                               ('server', ['cubrid', 'server', 'stop', 'testdb'])):
            try:
                run(name + '-cleanup-' + label, command, env, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                record.setdefault('cleanup_errors', []).append(str(error))
    for pid in owned():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 15
    while owned() and time.monotonic() < deadline:
        time.sleep(0.1)
    record['cleanup_remaining'] = owned()
    record['cleanup_ipc_remaining'] = ipc_rows()
    record['binary_sha256'] = hashlib.sha256((args.install / 'bin/cub_server').read_bytes()).hexdigest()
    (args.output / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
    if not record['cleanup_remaining'] and not record['cleanup_ipc_remaining']:
        for state in record['environments'].values():
            shutil.rmtree(state['allocation']['tmp'])
        shutil.rmtree(root)
    assert not record['cleanup_remaining'], record['cleanup_remaining']
    assert not record['cleanup_ipc_remaining'], record['cleanup_ipc_remaining']
