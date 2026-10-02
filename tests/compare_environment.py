#!/usr/bin/env python3
"""Same-condition old/new direnv entry on an uninitialized CUBRID-shaped fixture.

This measures build-only entry, not legacy ready-state validation performance.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--tooling', type=Path, required=True)
parser.add_argument('--baseline', default='f2aa990')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output = args.output.resolve()
args.output.mkdir(parents=True, exist_ok=False)
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
with tempfile.TemporaryDirectory(prefix='cwe-entry07-', dir='/tmp') as tmp:
    root = Path(tmp)
    source = root / 'source'
    source.mkdir()
    for directory in ('src', 'broker', 'pl_engine'):
        (source / directory).mkdir()
    (source / 'CMakeLists.txt').write_text('# uninitialized build-only fixture\n')
    (source / 'VERSION').write_text('11.5.0\n')
    subprocess.run(['git', 'init', '-q', str(source)], check=True)
    old = root / 'old-envrc'
    old.write_bytes(subprocess.check_output(['git', '-C', str(args.tooling), 'show', f'{args.baseline}:stow/cubrid/.envrc']))
    environment = {k: v for k, v in os.environ.items() if not k.startswith(('CUBRID', 'DIRENV'))}
    environment.update(XDG_DATA_HOME=str(root / 'xdg-data'),
        XDG_CONFIG_HOME=str(root / 'xdg-config'), XDG_STATE_HOME=str(root / 'xdg-state'),
        MY_CUBRID=str(args.tooling), CUB_WORKENV_CLI=str(cli), PRESET_MODE='debug_gcc', BROWSER='none')
    rows = []
    for iteration in range(3):
        for name, loader in [('old', old), ('new', args.tooling / 'stow/cubrid/.envrc')]:
            (source / 'compile_commands.json').unlink(missing_ok=True)
            (source / '.envrc').write_text(f'export PRESET_MODE=debug_gcc\nsource {loader}\n')
            subprocess.run(['direnv', 'allow'], cwd=source, env=environment, check=True, capture_output=True)
            started = time.monotonic()
            result = subprocess.run(['direnv', 'exec', '.', 'bash', '-c',
                'test "$CUBRID_RUNTIME_READY" = 0 && test -z "${CUBRID_TMP:-}"'],
                cwd=source, env=environment, text=True, capture_output=True, timeout=30)
            seconds = time.monotonic() - started
            (args.output / f'{name}-{iteration}.txt').write_text(result.stdout + result.stderr)
            rows.append({'loader': name, 'iteration': iteration, 'returncode': result.returncode, 'seconds': seconds})
            assert result.returncode == 0, (name, result.stderr)
            assert not (source / '.cub-workenv').exists()
    (args.output / 'results.json').write_text(json.dumps({'scope': 'same uninitialized build-only CUBRID-shaped Git fixture',
        'baseline_tooling': args.baseline, 'repetitions': rows}, indent=2) + '\n')
