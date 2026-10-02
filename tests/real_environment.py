#!/usr/bin/env python3
"""Ticket07: shared just build, explicit init, direnv, and native A-to-B flow.

A tiny CMake project exercises the real shared build boundary; this does not
claim a CUBRID engine rebuild. Installed CUBRID binaries are separate copies.
"""
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
parser.add_argument('--tooling', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output = args.output.resolve()
args.tooling = args.tooling.resolve()
args.install = args.install.resolve()
args.output.mkdir(parents=True, exist_ok=False)
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
root = Path(tempfile.mkdtemp(prefix='cwe-env07-', dir='/tmp'))
record = {'root': str(root), 'source_install': str(args.install), 'tooling': str(args.tooling), 'steps': []}
base = {k: v for k, v in os.environ.items() if not k.startswith(('CUBRID', 'DIRENV'))}
base.update(HOME=str(root / 'home'), MY_CUBRID=str(args.tooling), CUB_WORKENV_CLI=str(cli),
            XDG_DATA_HOME=str(root / 'xdg-data'), XDG_CONFIG_HOME=str(root / 'xdg-config'),
            XDG_RUNTIME_DIR=str(root / 'locks'), PRESET_MODE='debug_gcc', BROWSER='none')
Path(base['HOME']).mkdir()
(root / 'home/my-cubrid').symlink_to(args.tooling)
(root / 'locks').mkdir()
installs = []
states = []

def run(label, command, cwd, env=base):
    started = time.monotonic()
    with (args.output / f'{label}.txt').open('w') as log:
        result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, text=True,
                                stdout=log, stderr=subprocess.STDOUT, timeout=120)
    output = (args.output / f'{label}.txt').read_text()
    record['steps'].append({'label': label, 'command': list(map(str, command)),
                            'returncode': result.returncode, 'seconds': time.monotonic() - started})
    assert result.returncode == 0, (label, output)
    return output

def owned():
    found = []
    for process in Path('/proc').glob('[0-9]*'):
        try:
            entries = (process / 'environ').read_bytes().split(b'\0')
            if any(f'CUBRID={p}'.encode() in entries for p in installs):
                found.append(int(process.name))
        except OSError:
            pass
    return found

try:
    for name in ('a', 'b'):
        source = root / name
        source.mkdir()
        install = root / f'install-{name}'
        installs.append(install)
        (source / '.envrc').write_text(f'export PRESET_MODE=debug_gcc\nexport CUB_WORKENV_INSTALL={install}\nsource {args.tooling}/stow/cubrid/.envrc\n')
        (source / 'justfile').symlink_to(args.tooling / 'stow/cubrid/justfile')
        (source / '.just').symlink_to(args.tooling / 'stow/cubrid/.just')
        run(f'{name}-allow', ['direnv', 'allow'], source)
        output = run(f'{name}-before-init', ['direnv', 'exec', '.', 'bash', '-c',
            'test "$CUBRID_RUNTIME_READY" = 0 && test -z "${CUBRID_TMP:-}" && printf "build-only\\n"'], source)
        assert not (source / '.cub-workenv').exists()
        # Exercise the actual shared just/coordinator/CMake path once.
        if name == 'a':
            (source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\nproject(workenv_boundary C)\nadd_executable(probe probe.c)\ninstall(TARGETS probe DESTINATION bin)\n')
            (source / 'probe.c').write_text('int main(void) { return 0; }\n')
            (source / 'CMakePresets.json').write_text(json.dumps({'version': 3,
                'configurePresets': [{'name': 'debug_gcc', 'generator': 'Ninja', 'binaryDir': '${sourceDir}/build_preset_debug_gcc'}],
                'buildPresets': [{'name': 'debug_gcc', 'configurePreset': 'debug_gcc'}]}))
            run('shared-recipes', ['just', '--list'], source)
            run('build-recipe', ['just', '--show', 'core::build'], source)
            run('configure', ['direnv', 'exec', '.', 'just', 'configure'], source)
            run('build-before-init', ['direnv', 'exec', '.', 'just', 'build'], source)
            assert (install / 'bin/probe').is_file()
            assert not (source / '.cub-workenv').exists()
        install.mkdir(exist_ok=True)
        for part in ('bin', 'lib', 'conf', 'msg', 'locales', 'timezones', 'vm'):
            if (args.install / part).exists():
                subprocess.run(['cp', '-a', '--reflink=auto', str(args.install / part), str(install)], check=True)
        for part in ('log', 'var/pl', 'var/CUBRID_SOCK'):
            (install / part).mkdir(parents=True, exist_ok=True)
        run(f'{name}-init', [cli, 'init', '--worktree', source, '--install', install,
            '--preset', 'debug_gcc', '--state-home', root / 'host', '--port-start', '46000', '--port-end', '46999'], source)
        state = json.loads((source / '.cub-workenv/state.json').read_text())
        states.append(state)
        run(f'{name}-version', ['direnv', 'exec', '.', 'cubrid', '--version'], source)
        record.setdefault('binary_sha256', {})[name] = {binary: hashlib.sha256((install / 'bin' / binary).read_bytes()).hexdigest() for binary in ('cubrid', 'csql')}
        run(f'{name}-start', ['direnv', 'exec', '.', 'cubrid', 'server', 'start', 'testdb'], source)
        value = 701 if name == 'a' else 702
        run(f'{name}-seed', ['direnv', 'exec', '.', 'csql', '-C', '-u', 'dba', '-c',
            f'create table workenv_marker (id integer); insert into workenv_marker values ({value}); commit;', 'testdb'], source)
        for repetition in range(3):
            run(f'{name}-entry-{repetition}', ['direnv', 'exec', '.', 'bash', '-c',
                'test "$CUBRID_RUNTIME_READY" = 1; command -v cubrid; printf "%s\\n" "$CUBRID" "$CUBRID_TMP" "$CUBRID_DATABASES" "$CUBRID_CUBRID_PORT_ID"'], source)
        run(f'{name}-trace', ['strace', '-f', '-e', 'trace=execve', '-o', args.output / f'{name}-execve.txt',
            'direnv', 'exec', '.', '/usr/bin/true'], source)
        trace = (args.output / f'{name}-execve.txt').read_text()
        assert not re.search(r'"(?:init|validate|doctor|createdb)"', trace), trace
    switch = '\n'.join([
        'PATH_add() { export PATH="$1:$PATH"; }; has() { command -v "$1" >/dev/null 2>&1; }; log_status() { :; };',
        f'cd {root}/a; export CUB_WORKENV_INSTALL={installs[0]}; source {args.tooling}/stow/cubrid/.envrc >/dev/null || exit;',
        'csql -C -u dba -c "select id from workenv_marker" testdb || exit;',
        f'cd {root}/b; export CUB_WORKENV_INSTALL={installs[1]}; source {args.tooling}/stow/cubrid/.envrc >/dev/null || exit;',
        'csql -C -u dba -c "select id from workenv_marker" testdb || exit;',
        'printf "SELECTED=%s|%s|%s|%s\\n" "$CUBRID" "$CUBRID_TMP" "$CUBRID_DATABASES" "$CUBRID_CUBRID_PORT_ID"',
    ])
    output = run('switch-a-to-b', ['bash', '-c', switch], root)
    assert re.search(r'^\s*701\s*$', output, re.M) and re.search(r'^\s*702\s*$', output, re.M)
    b = states[1]
    assert f"SELECTED={b['install']}|{b['allocation']['tmp']}|{root}/b/.cub-workenv/databases|{b['allocation']['master_port']}" in output
    for name in ('a', 'b'):
        run(f'{name}-stop', ['direnv', 'exec', '.', 'cubrid', 'server', 'stop', 'testdb'], root / name)
    record['states'] = states
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
    if not record['cleanup_remaining']:
        for state in states:
            shutil.rmtree(state['allocation']['tmp'], ignore_errors=True)
        shutil.rmtree(root)
    assert not record['cleanup_remaining'], record
