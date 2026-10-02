#!/usr/bin/env python3
"""Verify explicit init and direct reentry on a newly built, prepared source tree.

Build first using the shared recipes; this probe refuses an initialized source.
It retains its owned source/build fixture for reviewed, non-force Git cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

p = argparse.ArgumentParser()
for name in ('source', 'install', 'tooling', 'java-home', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
for name in ('source', 'install', 'tooling', 'java_home', 'output'):
    setattr(a, name, getattr(a, name).resolve())
a.output.mkdir(parents=True, exist_ok=False)
assert not (a.source / '.cub-workenv').exists(), 'Use a newly built, uninitialized source worktree'
root = Path(tempfile.mkdtemp(prefix='cwe-flow09-'))
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
record = {'source': str(a.source), 'install': str(a.install), 'fixture': str(root), 'steps': []}
base = {k: v for k, v in os.environ.items() if not k.startswith(('CUBRID', 'DIRENV'))}
base.update(MY_CUBRID=str(a.tooling), CUB_WORKENV_CLI=str(cli), CUB_WORKENV_INSTALL=str(a.install),
            PRESET_MODE='debug_gcc', JAVA_HOME=str(a.java_home), BROWSER='none')
states = []

def run(label, command, cwd=a.source, env=base, expected=0):
    command = list(map(str, command))
    start = time.monotonic()
    with (a.output / (label + '.txt')).open('w') as log:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    output = (a.output / (label + '.txt')).read_text()
    record['steps'].append(dict(label=label, command=command, cwd=str(cwd), returncode=result.returncode,
                                seconds=round(time.monotonic() - start, 4)))
    assert result.returncode == expected, (label, result.returncode, output)
    return output

def init(label, source, install, extra=(), host=None, end='49999', expected=0):
    return run(label, [cli, 'init', '--worktree', source, '--install', install, '--preset', 'debug_gcc',
                      '--java-home', a.java_home, '--state-home', host or root / 'host',
                      '--port-start', '49000', '--port-end', end, *extra], expected=expected)

def hashes(paths):
    return {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for path in paths
            for f in path.rglob('*') if f.is_file() and not f.is_symlink()}

def owned():
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            values = (proc / 'environ').read_bytes().split(b'\0')
            if any(b'CUBRID=' + os.fsencode(i) in values for i in (a.install, root / 'install-b')):
                found.append(int(proc.name))
        except OSError:
            pass
    return found

try:
    record['source_commit'] = run('source-commit', ['git', 'rev-parse', 'HEAD']).strip()
    record['tooling_commit'] = run('tooling-commit', ['git', '-C', a.tooling, 'rev-parse', 'HEAD']).strip()
    record['links'] = {name: str((a.source / name).resolve()) for name in
                       ('justfile', '.just', '.envrc', 'CMakeUserPresets.json')}
    assert all(str(a.tooling) in value for value in record['links'].values())
    assert (a.source / 'build_preset_debug_gcc/CMakeCache.txt').is_file()
    record['binary_sha256'] = {name: hashlib.sha256((a.install / 'bin' / name).read_bytes()).hexdigest()
                               for name in ('cubrid', 'csql', 'cub_server')}
    output = run('build-only', ['direnv', 'exec', '.', 'bash', '-c',
        'test "$CUBRID_RUNTIME_READY" = 0 && test -z "${CUBRID_TMP:-}" && test -z "${CUBRID_DATABASES:-}" && printf "build-only %s\\n" "$CUBRID"'])
    assert str(a.install) in output
    assert not (a.source / '.cub-workenv').exists()
    init('explicit-init', a.source, a.install)
    states.append(json.loads((a.source / '.cub-workenv/state.json').read_text()))
    run('version', ['direnv', 'exec', '.', 'cubrid', '--version'])
    run('source-start', ['direnv', 'exec', '.', 'cubrid', 'server', 'start', 'testdb'])
    run('source-seed', ['direnv', 'exec', '.', 'csql', '-C', '-u', 'dba', '-c',
        'create table workflow_marker (id integer); insert into workflow_marker values (901); commit;', 'testdb'])
    protected = [a.source / '.cub-workenv/conf', a.source / '.cub-workenv/databases', root / 'host']
    before = hashes(protected)
    before_state = (a.source / '.cub-workenv/state.json').read_bytes()
    assert 'already initialized' in init('repeated-init', a.source, a.install, ['--no-db'])
    assert hashes(protected) == before and before_state == (a.source / '.cub-workenv/state.json').read_bytes()
    for n in range(3):
        output = run(f'reentry-{n}', ['direnv', 'exec', '.', 'csql', '-C', '-u', 'dba', '-c',
                                      'select id from workflow_marker;', 'testdb'])
        assert re.search(r'^\s*901\s*$', output, re.M)
    run('entry-trace', ['strace', '-f', '-e', 'trace=execve', '-o', a.output / 'entry-execve.txt',
                        'direnv', 'exec', '.', '/usr/bin/true'])
    assert not re.search(r'"(?:init|doctor|validate|createdb)"', (a.output / 'entry-execve.txt').read_text())
    run('doctor-source', [cli, 'doctor', '--worktree', a.source])
    run('doctor-mismatch', [cli, 'doctor', '--worktree', a.source, '--preset', 'release_gcc'], expected=1)
    run('doctor-correct-selection', [cli, 'doctor', '--worktree', a.source, '--preset', 'debug_gcc'])
    assert hashes(protected) == before and before_state == (a.source / '.cub-workenv/state.json').read_bytes()
    b = root / 'b'
    b.mkdir()
    ib = root / 'install-b'
    shutil.copytree(a.install, ib, symlinks=True)
    # Remove only this copy's transient PL metadata; A's live installation is unchanged.
    for f in (ib / 'var/pl').glob('*.info'):
        f.unlink()
    (b / '.envrc').write_text(f'export PRESET_MODE=debug_gcc\nexport CUB_WORKENV_INSTALL={ib}\nsource {a.tooling}/stow/cubrid/.envrc\n')
    run('b-allow', ['direnv', 'allow'], cwd=b)
    init('b-no-db', b, ib, ['--no-db'])
    assert not (b / '.cub-workenv/db').exists()
    assert not (b / '.cub-workenv/databases/databases.txt').read_text().strip()
    run('b-create-db', [cli, 'create-db', 'testdb', '--worktree', b])
    states.append(json.loads((b / '.cub-workenv/state.json').read_text()))
    run('b-start', ['direnv', 'exec', '.', 'cubrid', 'server', 'start', 'testdb'], cwd=b)
    run('b-seed', ['direnv', 'exec', '.', 'csql', '-C', '-u', 'dba', '-c',
        'create table workflow_marker (id integer); insert into workflow_marker values (902); commit;', 'testdb'], cwd=b)
    # Export A's actual direnv selection into B's fresh direnv entry.
    output = run('switch-a-to-b', ['direnv', 'exec', '.', 'bash', '-c',
        'csql -C -u dba -c "select id from workflow_marker;" testdb && cd "$1" && '
        'direnv exec . csql -C -u dba -c "select id from workflow_marker;" testdb', 'bash', b])
    assert all(re.search(rf'^\s*{v}\s*$', output, re.M) for v in (901, 902))
    for name, source in (('a', a.source), ('b', b)):
        run(name + '-stop', ['direnv', 'exec', '.', 'cubrid', 'server', 'stop', 'testdb'], cwd=source)
        run(name + '-master-stop', ['direnv', 'exec', '.', 'cubrid', 'service', 'stop'], cwd=source)
    assert not owned(), owned()
    record['verdict'] = 'pass'
finally:
    record['states'] = states
    record['remaining_owned_pids'] = owned()
    record['cleanup'] = 'retained for exact-file inventory and non-force source worktree removal'
    (a.output / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
    for f in a.output.glob('*.txt'):
        f.write_text('\n'.join(line.rstrip() for line in f.read_text().splitlines()) + '\n')
    print(json.dumps({'verdict': record.get('verdict', 'failed'), 'fixture': str(root),
                      'remaining_owned_pids': record['remaining_owned_pids']}))
