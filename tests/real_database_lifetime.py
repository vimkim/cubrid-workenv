#!/usr/bin/env python3
"""Disposable native proof of docs/database-lifetime.md; never a user cleanup CLI."""
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

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install', type=Path, required=True)
parser.add_argument('--java-home', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
source = args.install.resolve(strict=True)
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
root = Path(tempfile.mkdtemp(prefix='cwe-life-', dir='/tmp'))
cli = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'
repo, a, b = (root / name for name in ('repo', 'a-source', 'b-source'))
envs = {}
states = {}
results = {'runtime_root': str(root), 'install_source': str(source), 'steps': []}


def record():
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')


def run(label, argv, env=None, cwd=None, success=True):
    argv = list(map(str, argv))
    with (out / (label + '.txt')).open('w') as stream:
        proc = subprocess.run(argv, env=env, cwd=cwd or root, stdout=stream,
                              stderr=subprocess.STDOUT, timeout=90)
    results['steps'].append({'label': label, 'argv': argv, 'returncode': proc.returncode})
    record()
    text = (out / (label + '.txt')).read_text(errors='replace')
    print(label, proc.returncode, flush=True)
    if success:
        assert proc.returncode == 0, (label, text)
    return proc.returncode, text


def native(label, instance, *argv):
    return run(label, [root / instance / 'bin' / argv[0], *argv[1:]], envs[instance], root / instance)[1]


def owned_processes():
    found = []
    prefixes = {os.fsencode(root / x) for x in ('a', 'b')}
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            entries = (proc / 'environ').read_bytes().split(b'\0')
            if any(b'CUBRID=' + prefix in entries for prefix in prefixes):
                found.append({'pid': int(proc.name), 'command': (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')})
        except (OSError, ProcessLookupError):
            pass
    return found


def inventory(path):
    """No symlink traversal; hashes make modified owned files visible."""
    entries = {}
    for directory, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            item = Path(directory) / name
            relative = str(item.relative_to(path))
            if item.is_symlink():
                entries[relative] = {'type': 'symlink', 'target': os.readlink(item)}
            elif item.is_dir():
                entries[relative] = {'type': 'directory'}
            elif item.is_file():
                entries[relative] = {'type': 'file', 'sha256': hashlib.sha256(item.read_bytes()).hexdigest()}
            else:
                raise AssertionError(f'Unknown file type: {item}')
    return entries


def classify(worktree, paths):
    """Location evidence only; not deletion authorization or volume discovery."""
    resolved = [p.resolve(strict=True) for p in paths]
    internal = [p.is_relative_to(worktree.resolve()) for p in resolved]
    return {'paths': list(map(str, paths)), 'resolved': list(map(str, resolved)),
            'classification': 'internal' if all(internal) else 'external' if not any(internal) else 'mixed: preserve and review'}


def cleanup_owned(worktree, approved):
    """Only this fixture's post-shutdown manifest is authorized; no general remover."""
    actual = inventory(worktree / '.cub-workenv')
    if actual != approved:
        return 'blocked: unknown or changed artifact'
    status = subprocess.run(['git', '-C', str(worktree), 'status', '--porcelain', '--untracked-files=all', '--ignored'],
                            capture_output=True, text=True, check=True).stdout
    if any(not line.startswith(('?? .cub-workenv/', '!! .cub-workenv/')) for line in status.splitlines()):
        return 'blocked: user change outside generated artifacts'
    # No recursive delete: unlink exact entries, then rmdir only empty directories.
    for relative, entry in sorted(approved.items(), key=lambda pair: len(Path(pair[0]).parts), reverse=True):
        item = worktree / '.cub-workenv' / relative
        if entry['type'] == 'directory':
            item.rmdir()
        else:
            item.unlink()
    (worktree / '.cub-workenv').rmdir()
    return 'cleaned exact owned manifest'


try:
    run('git-init', ['git', 'init', repo])
    (repo / 'source.txt').write_text('fixture source\n')
    (repo / '.gitignore').write_text('*.private\n')
    run('git-add', ['git', '-C', repo, 'add', 'source.txt', '.gitignore'])
    run('git-commit', ['git', '-C', repo, '-c', 'user.name=Lifetime fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Disposable fixture'])
    for instance, worktree in (('a', a), ('b', b)):
        run(instance + '-worktree-add', ['git', '-C', repo, 'worktree', 'add', '--detach', worktree])
        prefix = root / instance
        prefix.mkdir()
        for part in ('bin', 'lib', 'msg', 'locales', 'timezones', 'conf', 'vm'):
            if (source / part).exists():
                subprocess.run(['cp', '-a', '--reflink=auto', str(source / part), str(prefix / part)], check=True)
        for part in ('log', 'var/pl', 'var/CUBRID_SOCK'):
            (prefix / part).mkdir(parents=True, exist_ok=True)
        extra = [] if instance == 'a' else ['--no-db', '--database-registry', str(root / 'external-registry.txt')]
        run(instance + '-init', [cli, 'init', '--worktree', worktree, '--install', prefix,
            '--preset', 'debug_gcc', '--java-home', args.java_home, '--state-home', root / 'host',
            '--port-start', '48000', '--port-end', '48999', *extra])
        loaded = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c', 'source "$1" && env -0',
            'bash', str(worktree / '.cub-workenv/env.sh')], capture_output=True, check=True)
        envs[instance] = dict(entry.decode().split('=', 1) for entry in loaded.stdout.split(b'\0') if b'=' in entry)
        states[instance] = json.loads((worktree / '.cub-workenv/state.json').read_text())
        shutil.copyfile(worktree / '.cub-workenv/state.json', out / (instance + '-state.json'))
        if instance == 'a':
            run('external-create', [cli, 'create-db', 'externaldb', '--worktree', a, '--path', root / 'external-db'])
            registry = a / '.cub-workenv/databases/databases.txt'
            external_row = next(line for line in registry.read_text().splitlines() if line.split() and line.split()[0] == 'externaldb')
            (root / 'external-registry.txt').write_text(external_row + '\n')

    native('version', 'a', 'cubrid', '--version')
    results['binary_sha256'] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in ('bin/cubrid', 'bin/csql', 'bin/cub_server', 'lib/libcubridsa.so', 'lib/libcubrid.so')}
    for db in ('testdb', 'externaldb'):
        native(db + '-start', 'a', 'cubrid', 'server', 'start', db)
        native(db + '-seed', 'a', 'csql', '-C', '-u', 'dba', '-c',
               "create table sentinel (id integer, payload blob); insert into sentinel values (8042, bit_to_blob(X'080042')); commit;", db)
        native(db + '-stop', 'a', 'cubrid', 'server', 'stop', db)
    native('a-master-stop', 'a', 'cubrid', 'service', 'stop')
    assert not owned_processes(), owned_processes()
    external_before = inventory(root / 'external-db')
    assert any(x.startswith('lob/') and v['type'] == 'file' for x, v in external_before.items())
    (out / 'external-before.json').write_text(json.dumps(external_before, indent=2) + '\n')
    managed = a / '.cub-workenv/db/testdb'
    results['managed'] = classify(a, [managed / x for x in ('data', 'log', 'lob')])
    assert results['managed']['classification'] == 'internal'
    assert all(any(p.is_file() for p in (managed / part).rglob('*')) for part in ('data', 'log', 'lob'))
    # Internal references to external data are intentionally created, then unlinked only.
    alias = a / '.cub-workenv/external-link'
    alias.symlink_to(root / 'external-db', target_is_directory=True)
    results['symlink'] = classify(a, [alias / x for x in ('data', 'log', 'lob')])
    assert results['symlink']['classification'] == 'external'
    results['mixed_fixture'] = classify(a, [managed / 'data', alias / 'log', managed / 'lob'])
    assert results['mixed_fixture']['classification'] == 'mixed: preserve and review'
    # A synthetic mixed registration is evidence of a stop/review case, not a runnable DB.
    mixed_row = f'mixedprobe {managed}/data localhost {alias}/log file:{managed}/lob\n'
    (out / 'mixed-registration.txt').write_text(mixed_row)
    registry = a / '.cub-workenv/databases/databases.txt'
    registry.write_text(registry.read_text().replace(str(root / 'external-db'), str(alias)))
    shutil.copyfile(registry, out / 'a-registry-through-symlink.txt')
    approved = inventory(a / '.cub-workenv')
    (out / 'approved-owned-manifest.json').write_text(json.dumps(approved, indent=2) + '\n')
    # A same-name arbitrary file is not disposable, including if Git ignores it.
    unknown = a / '.cub-workenv/notes.private'
    unknown.write_text('user-owned ignored sentinel\n')
    results['unknown_gate'] = cleanup_owned(a, approved)
    assert results['unknown_gate'].startswith('blocked') and unknown.read_text() == 'user-owned ignored sentinel\n'
    run('ignored-user-file', ['git', '-C', a, 'status', '--short', '--ignored'])
    unknown.unlink()  # Only the deliberately injected fixture, never a discovered user file.
    outside = a / 'valuable.private'
    outside.write_text('ignored user file outside generated directory\n')
    results['outside_ignored_gate'] = cleanup_owned(a, approved)
    assert results['outside_ignored_gate'].startswith('blocked') and outside.exists()
    outside.unlink()  # Undo only the fixture's own addition.
    settings = a / '.cub-workenv/conf/cubrid.conf'
    original = settings.read_bytes()
    settings.write_bytes(original + b'# user edit\n')
    results['modified_generated_gate'] = cleanup_owned(a, approved)
    assert results['modified_generated_gate'].startswith('blocked') and settings.read_bytes().endswith(b'# user edit\n')
    settings.write_bytes(original)  # Undo this test's own injection.
    (a / 'source.txt').write_text('user edited source sentinel\n')
    results['source_gate'] = cleanup_owned(a, approved)
    assert results['source_gate'].startswith('blocked')
    code, _ = run('git-refuses-user-change', ['git', '-C', repo, 'worktree', 'remove', a], success=False)
    assert code != 0 and (a / 'source.txt').read_text() == 'user edited source sentinel\n'
    # Preserve the change in an ordinary commit. Do not hide or discard it for removal.
    run('save-user-change-add', ['git', '-C', a, 'add', 'source.txt'])
    run('save-user-change-commit', ['git', '-C', a, '-c', 'user.name=Lifetime fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Preserved fixture user edit'])
    run('save-user-change-branch', ['git', '-C', a, 'branch', 'preserved-user-edit'])
    run('preserved-user-edit', ['git', '-C', repo, 'show', 'preserved-user-edit:source.txt'])
    host_before = inventory(root / 'host')
    results['cleanup'] = cleanup_owned(a, approved)
    assert results['cleanup'] == 'cleaned exact owned manifest'
    run('a-worktree-remove', ['git', '-C', repo, 'worktree', 'remove', a])
    assert not a.exists()
    assert inventory(root / 'external-db') == external_before
    assert inventory(root / 'host') == host_before, 'Worktree cleanup altered allocation registry'
    results['external_unchanged_before_reopen'] = True
    results['host_allocation_retained'] = True
    native('external-reopen', 'b', 'cubrid', 'server', 'start', 'externaldb')
    read = native('external-sentinel-after-removal', 'b', 'csql', '-C', '-u', 'dba', '-c',
                  'select id, blob_to_bit(payload) from sentinel;', 'externaldb')
    assert re.search(r'\b8042\b', read) and '080042' in read, read
    native('external-stop-b', 'b', 'cubrid', 'server', 'stop', 'externaldb')
    native('b-master-stop', 'b', 'cubrid', 'service', 'stop')
    assert not owned_processes(), owned_processes()
    results['verdict'] = 'pass'
except BaseException as error:
    results['verdict'] = 'fail'
    results['error'] = repr(error)
    raise
finally:
    # Failure leaves all files for inspection; only exact fixture-prefix processes stop.
    results['cleanup_processes'] = owned_processes()
    for item in results['cleanup_processes']:
        try:
            os.kill(item['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while owned_processes() and time.monotonic() < deadline:
        time.sleep(0.2)
    results['cleanup_remaining'] = owned_processes()
    results['runtime_retained'] = True
    record()
    print('Evidence:', out, 'Disposable runtime retained:', root, flush=True)
