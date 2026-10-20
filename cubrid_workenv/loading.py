"""Cheap shell loading: state selection, never runtime diagnosis or allocation."""
import json
from pathlib import Path
import shlex
import sys


# Retain unrelated tools and libraries while removing the previous installation.
CLEAN_SHELL = '''_cwe_old_install=${CUBRID:-}
for _cwe_var in PATH LD_LIBRARY_PATH; do
    _cwe_value=${!_cwe_var:-}
    _cwe_result=
    IFS=: read -r -a _cwe_parts <<< "$_cwe_value"
    for _cwe_part in "${_cwe_parts[@]}"; do
        if [[ -n "$_cwe_old_install" && ( "$_cwe_part" == "$_cwe_old_install/bin" || "$_cwe_part" == "$_cwe_old_install/lib" || "$_cwe_part" == "$_cwe_old_install/cci/lib" ) ]]; then
            continue
        fi
        _cwe_result=${_cwe_result:+$_cwe_result:}$_cwe_part
    done
    export "$_cwe_var=$_cwe_result"
done
for _cwe_name in ${!CUBRID@}; do
    [[ "$_cwe_name" == CUBRID_BUILD_DIR ]] || unset "$_cwe_name"
done
unset _cwe_old_install _cwe_var _cwe_value _cwe_result _cwe_parts _cwe_part _cwe_name LD_PRELOAD
export CUBRID_RUNTIME_READY=0
'''


def selection(worktree, preset=None, install=None):
    root = worktree / '.cub-workenv'
    if not root.exists():
        return None
    try:
        state = json.loads((root / 'state.json').read_text())
        if state.get('schema') != 1 or state.get('status') != 'ready':
            raise ValueError('incomplete work environment')
        if state.get('worktree') != str(worktree):
            raise ValueError('worktree selection mismatch')
        if preset and state.get('preset') != preset:
            raise ValueError('preset selection mismatch')
        if install and state.get('install') != str(install.resolve()):
            raise ValueError('installation selection mismatch')
        if not (root / 'env.sh').is_file():
            raise ValueError('missing environment artifact')
    except (OSError, ValueError, AttributeError) as error:
        raise ValueError(f'{error}; run cub-workenv doctor --worktree {worktree}') from error
    return root / 'env.sh'


def emit(args):
    # Emit cleanup even on failure; callers must eval stdout before handling status.
    print(CLEAN_SHELL, end='')
    artifact = selection(args.worktree.resolve(), args.preset, args.install)
    if artifact is None:
        print('cub-workenv: host environment not initialized; after installation (just build-and-install), run cub-workenv init explicitly.', file=sys.stderr)
    else:
        print(f'source {shlex.quote(str(artifact))}')
