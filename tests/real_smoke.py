#!/usr/bin/env python3
"""Disposable real-CUBRID CLI acceptance. Retains JSON evidence, removes runtime."""
import argparse
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
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
root = Path(tempfile.mkdtemp(prefix='cwe-first-'))
install = root / 'install'
worktree = root / 'source'
worktree.mkdir()
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
record = {'root': str(root), 'install_source': str(args.install), 'steps': []}
env = os.environ.copy()

def owned():
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if f'CUBRID={install}'.encode() in (proc / 'environ').read_bytes().split(b'\0'):
                found.append(int(proc.name))
        except (OSError, PermissionError):
            pass
    return found

def run(label, argv):
    if label == 'environment':
        result = subprocess.run(argv, cwd=worktree, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        output = result.stdout
    else:
        with (args.output / f'{label}.txt').open('w') as log:
            result = subprocess.run(argv, cwd=worktree, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90)
        output = (args.output / f'{label}.txt').read_text()
    record['steps'].append({'label': label, 'argv': list(map(str, argv)), 'returncode': result.returncode})
    assert result.returncode == 0, (label, output)
    return output

try:
    install.mkdir()
    for part in ('bin', 'lib', 'conf', 'msg', 'locales', 'timezones', 'vm'):
        if (args.install / part).exists():
            subprocess.run(['cp', '-a', '--reflink=auto', str(args.install / part), str(install / part)], check=True)
    for part in ('log', 'var/pl', 'var/CUBRID_SOCK'):
        (install / part).mkdir(parents=True, exist_ok=True)
    run('init', [str(cli), 'init', '--worktree', str(worktree), '--install', str(install), '--preset', 'debug_gcc', '--state-home', str(root / 'host')])
    state = json.loads((worktree / '.cub-workenv/state.json').read_text())
    assert state['status'] == 'ready'
    record['state'] = state
    # Source the public artifact in a deliberately contaminated shell.
    env.update(CUBRID='wrong', CUBRID_CUBRID_PORT_ID='1', CUBRID_HA_MODE='replica')
    output = run('environment', ['/bin/bash', '--noprofile', '--norc', '-c', 'source "$1" && env -0', 'bash', str(worktree / '.cub-workenv/env.sh')])
    env = dict(x.split('=', 1) for x in output.split('\0') if '=' in x)
    (args.output / 'environment.json').write_text(json.dumps({k: v for k, v in env.items() if k.startswith('CUBRID') or k in ('PATH', 'LD_LIBRARY_PATH')}, indent=2) + '\n')
    assert env['CUBRID'] == str(install)
    assert 'CUBRID_HA_MODE' not in env
    run('version', ['cubrid', '--version'])
    run('start', ['cubrid', 'server', 'start', 'testdb'])
    sql = run('sql', ['csql', '-C', '-u', 'dba', '-c', 'create table marker (id integer); insert into marker values (42); commit; select id from marker;', 'testdb'])
    assert re.search(r'^\s*42\s*$', sql, re.MULTILINE), sql
    run('stop', ['cubrid', 'server', 'stop', 'testdb'])
    registry = (worktree / '.cub-workenv/databases/databases.txt').read_text()
    (args.output / 'databases.txt').write_text(registry)
    for part in ('data', 'log', 'lob'):
        assert str(worktree / '.cub-workenv/db/testdb' / part) in registry
    record['verdict'] = 'pass'
finally:
    for pid in owned():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while owned() and time.monotonic() < deadline:
        time.sleep(0.1)
    record['cleanup_remaining'] = owned()
    (args.output / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
    if not owned():
        if 'state' in record:
            shutil.rmtree(record['state']['allocation']['tmp'], ignore_errors=True)
        shutil.rmtree(root)
    assert not record['cleanup_remaining'], record
