#!/usr/bin/env python3
"""Bounded manual recovery for an owned failed init before allocation/DB creation.

This fixture owns its initially empty paths. It is not a general repair utility.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--install', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output = a.output.resolve()
a.output.mkdir(parents=True, exist_ok=False)
root = Path(tempfile.mkdtemp(prefix='cwe-recovery09-', dir='/tmp'))
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
record = {'fixture': str(root), 'steps': [], 'states': []}
for name in ('owner', 'victim'):
    (root / name).mkdir()
    shutil.copytree(a.install, root / (name + '-install'), symlinks=True)

def run(label, command, expected=0):
    command = list(map(str, command))
    with (a.output / (label + '.txt')).open('w') as log:
        r = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
    record['steps'].append({'label': label, 'argv': command, 'returncode': r.returncode})
    assert r.returncode == expected, (label, (a.output / (label + '.txt')).read_text())

def init(label, name, end, expected=0):
    run(label, [cli, 'init', '--worktree', root / name, '--install', root / (name + '-install'),
                '--preset', 'debug_gcc', '--no-db', '--state-home', root / 'host',
                '--port-start', '49800', '--port-end', str(end)], expected)

try:
    init('owner-init', 'owner', 49801)
    record['states'].append(json.loads((root / 'owner/.cub-workenv/state.json').read_text()))
    init('pool-exhausted', 'victim', 49801, 1)
    run('incomplete-doctor', [cli, 'doctor', '--worktree', root / 'victim'], 1)
    init('wider-pool-still-incomplete', 'victim', 49809, 1)
    directory = root / 'victim/.cub-workenv'
    state = json.loads((directory / 'state.json').read_text())
    assert state['stage'] == 'allocation' and 'allocation' not in state
    assert {f.name for f in directory.iterdir()} == {'state.json', 'init.lock'}
    allocation_before = (root / 'host/allocations.json').read_bytes()
    assert str(root / 'victim') not in allocation_before.decode()
    # All initializers were synchronous and have exited; no native command ran.
    # Archive the two owned files rather than deleting state or altering registry.
    directory.rename(root / 'preserved-before-allocation')
    assert allocation_before == (root / 'host/allocations.json').read_bytes()
    init('explicit-retry-after-archive', 'victim', 49809)
    record['states'].append(json.loads((root / 'victim/.cub-workenv/state.json').read_text()))
    run('recovered-doctor', [cli, 'doctor', '--worktree', root / 'victim'])
    record['archived_state'] = state
    record['allocation_unchanged_by_archive'] = True
    record['verdict'] = 'pass'
finally:
    record['cleanup'] = 'retained for creator inspection; no CUBRID processes started'
    (a.output / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'fixture': str(root), 'verdict': record.get('verdict', 'failed')}))
