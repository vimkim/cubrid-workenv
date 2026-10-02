"""CUBRID settings, environment artifacts and native database utilities."""
import os
from pathlib import Path
import shlex
import subprocess


def environment(state):
    root = Path(state['worktree']) / '.cub-workenv'
    install = Path(state['install'])
    result = {'CUBRID': str(install), 'CUBRID_CONF_FILE': str(root / 'conf/cubrid.conf'),
            'CUBRID_BROKER_CONF_FILE': str(root / 'conf/cubrid_broker.conf'),
            'CUBRID_DATABASES': str(root / 'databases'), 'CUBRID_TMP': state['allocation']['tmp'],
            'CUBRID_CUBRID_PORT_ID': str(state['allocation']['master_port']),
            'PATH': str(install / 'bin') + ':/usr/local/bin:/usr/bin:/bin',
            'LD_LIBRARY_PATH': str(install / 'lib')}
    if state.get('java_home'):
        result['CUBRID_JAVA_HOME'] = state['java_home']
    return result


def process_environment(state):
    env = {k: v for k, v in os.environ.items() if not k.startswith('CUBRID') and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH')}
    env.update(environment(state))
    return env


def write_settings(state):
    root = Path(state['worktree']) / '.cub-workenv'
    (root / 'conf').mkdir()
    (root / 'databases').mkdir()
    (root / 'databases/databases.txt').write_text('')
    (root / 'conf/cubrid.conf').write_text(
        '[service]\nservice=server,broker\n\n[common]\n' + f"cubrid_port_id={state['allocation']['master_port']}\n" +
        'data_buffer_size=64M\nlog_buffer_size=16M\nmax_clients=20\nstored_procedure=yes\nstored_procedure_uds=yes\nha_mode=off\n')

    allocation = state['allocation']
    (root / 'conf/cubrid_broker.conf').write_text(
        '[broker]\n' + f"MASTER_SHM_ID={allocation['broker_master_shm_id']:#x}\n" +
        'ADMIN_LOG_FILE=log/broker/cubrid_broker.log\n\n[%workenv]\nSERVICE=ON\n' +
        f"BROKER_PORT={allocation['broker_port']}\n" +
        f"APPL_SERVER_SHM_ID={allocation['broker_appl_server_shm_id']:#x}\n" +
        'MIN_NUM_APPL_SERVER=1\nMAX_NUM_APPL_SERVER=5\n' +
        'LOG_DIR=log/broker/sql_log\nERROR_LOG_DIR=log/broker/error_log\n' +
        'SQL_LOG=ON\nKEEP_CONNECTION=AUTO\nCCI_DEFAULT_AUTOCOMMIT=ON\n')


def create_database(state, name='testdb'):
    root = Path(state['worktree']) / '.cub-workenv'
    paths = [root / 'db' / name / part for part in ('data', 'log', 'lob')]
    for path in paths:
        path.mkdir(parents=True, exist_ok=False)
    command = [str(Path(state['install']) / 'bin/cubrid'), 'createdb',
               '--db-volume-size=64M', '--log-volume-size=32M',
               '-F', str(paths[0]), '-L', str(paths[1]), '-B', str(paths[2]),
               '--server-name=localhost', name, 'en_US.utf8']
    with (root / 'createdb.log').open('w') as log:
        result = subprocess.run(command, env=process_environment(state), cwd=root, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError(f'createdb failed ({result.returncode}); see {root / "createdb.log"}; incomplete environment retained; run doctor')


def write_environment(state):
    root = Path(state['worktree']) / '.cub-workenv'
    # Bash is explicit: variable enumeration removes overrides unknown to this version.
    guard = shlex.quote(str(root / 'state.json'))
    text = '# Source with bash; ready state is required. No CUBRID command runs here.\n'
    text += f"if ! python3 -c 'import json,sys; sys.exit(json.load(open(sys.argv[1])).get(\"status\") != \"ready\")' {guard}; then\n  echo 'cub-workenv: incomplete environment; run doctor' >&2\n  return 1\nfi\n"
    text += 'for _cwe_name in ${!CUBRID@}; do unset "$_cwe_name"; done\nunset _cwe_name LD_PRELOAD LD_LIBRARY_PATH\n'
    for key, value in environment(state).items():
        text += f'export {key}={shlex.quote(value)}\n'
    (root / 'env.sh').write_text(text)
