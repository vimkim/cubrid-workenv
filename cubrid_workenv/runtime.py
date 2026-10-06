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


def write_environment(state):
    from .loading import CLEAN_SHELL
    root = Path(state['worktree']) / '.cub-workenv'
    guard = shlex.quote(str(root / 'state.json'))
    # Bind the published artifact to its original ready selection. Check only a
    # small metadata file; full integrity and live-resource inspection is doctor.
    check = ('import json,os,sys; s=json.load(open(sys.argv[1])); '
             'sys.exit(not (s.get("status")=="ready" and s.get("worktree")==sys.argv[2] '
             'and s.get("install")==sys.argv[3] and s.get("preset")==sys.argv[4] '
             'and os.environ.get("PRESET_MODE",sys.argv[4])==sys.argv[4]))')
    text = '# Source with bash; only completed selected state is loaded.\n' + CLEAN_SHELL
    text += f"if ! python3 -c {shlex.quote(check)} {guard} {shlex.quote(state['worktree'])} {shlex.quote(state['install'])} {shlex.quote(state['preset'])}; then\n  echo 'cub-workenv: incomplete or mismatched environment; run doctor' >&2\n  return 1\nfi\n"
    for key, value in environment(state).items():
        if key == 'PATH':
            text += f'export PATH={shlex.quote(str(Path(state["install"]) / "bin"))}${{PATH:+:$PATH}}\n'
        elif key == 'LD_LIBRARY_PATH':
            text += f'export LD_LIBRARY_PATH={shlex.quote(value)}${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}\n'
        else:
            text += f'export {key}={shlex.quote(value)}\n'
    text += 'export CUBRID_RUNTIME_READY=1\n'
    (root / 'env.sh').write_text(text)


def reallocated_settings(state, allocation):
    """Replace only managed numeric settings; retain paths, comments and tuning."""
    import configparser
    import re
    root = Path(state['worktree']) / '.cub-workenv/conf'
    result = {}
    for filename, replacements in (
        ('cubrid.conf', {('common', 'cubrid_port_id'): str(allocation['master_port'])}),
        ('cubrid_broker.conf', {('broker', 'master_shm_id'): f"{allocation['broker_master_shm_id']:#x}",
                               ('%workenv', 'broker_port'): str(allocation['broker_port']),
                               ('%workenv', 'appl_server_shm_id'): f"{allocation['broker_appl_server_shm_id']:#x}"})):
        path = root / filename
        if path.is_symlink():
            raise ValueError(f'Symlinked configuration preserved: {path}')
        text = path.read_text()
        config = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=('#', ';'))
        try:
            config.read_string(text)
        except configparser.Error as error:
            raise ValueError(f'Invalid configuration: {path}: {error}') from error
        for section in config.sections():
            if filename == 'cubrid.conf' and section.startswith('@') and config.has_option(section, 'cubrid_port_id'):
                replacements[(section, 'cubrid_port_id')] = str(allocation['master_port'])
            if filename == 'cubrid_broker.conf' and section.startswith('%') and section != '%workenv':
                if config.get(section, 'service', fallback='on').lower() not in ('off', 'no', 'false', '0'):
                    raise ValueError(f'Additional enabled broker in {path}; review its resources manually')
        lines, found, section = [], set(), None
        for line in text.splitlines(keepends=True):
            match = re.match(r'\s*\[([^]]+)\]', line)
            if match:
                section = match[1]
            match = re.match(r'(\s*([^=:#\s]+)\s*[=:]\s*)([^#;\r\n]*)(.*)', line)
            key = (section, match[2].lower()) if match else None
            if key in replacements:
                suffix = match[3][len(match[3].rstrip()):] + match[4]
                line = match[1] + replacements[key] + suffix + ('\n' if line.endswith('\n') else '')
                found.add(key)
            lines.append(line)
        if found != set(replacements):
            raise ValueError(f'Missing managed numeric settings in {path}; inspect manually')
        result[path] = ''.join(lines)
    return result
