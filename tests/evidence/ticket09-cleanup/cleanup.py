"""Recorded one-off cleanup of these exact creator-owned disposable fixtures.

Not a general cleanup utility; completed fixture paths no longer exist.
"""
import hashlib, json, os, stat, subprocess, time
from pathlib import Path
repo = Path('/home/vimkim/gh/cubrid-workenv-09')
out = repo / 'tests/evidence/ticket09-cleanup'
out.mkdir()
source = Path('/home/vimkim/gh/cb/workenv09-source')
install = Path('/tmp/cwe-workflow09-install')
flow = json.loads((repo / 'tests/evidence/ticket09-flow/results.json').read_text())
root = Path(flow['fixture'])
recovery = json.loads((repo / 'tests/evidence/ticket09-recovery/results.json').read_text())
life = json.loads((repo / 'tests/evidence/ticket09-lifetime/results.json').read_text())
roots = [source, install, root, Path(recovery['fixture']), Path(life['runtime_root']), Path('/tmp/cwe-workflow09-tools')]
installs = [str(install), str(root / 'install-b')]
states = []
for r in roots:
    for p in r.glob('**/.cub-workenv/state.json'):
        states.append(json.loads(p.read_text()))
        installs.append(states[-1]['install'])
for p in (repo / 'tests/evidence/ticket09-lifetime').glob('*-state.json'):
    states.append(json.loads(p.read_text()))
remaining = []
for p in Path('/proc').glob('[0-9]*'):
    try:
        env = (p / 'environ').read_bytes().split(b'\x00')
        if any((b'CUBRID=' + os.fsencode(x) in env for x in installs)):
            remaining.append(int(p.name))
    except OSError:
        pass
assert not remaining, remaining
socket_dirs = {s['allocation']['tmp'] for s in states if 'allocation' in s}
assert not any((t in Path('/proc/net/unix').read_text() for t in socket_dirs))
keys = {s['allocation'][k] for s in states if 'allocation' in s for k in ('broker_master_shm_id', 'broker_appl_server_shm_id')}
ipc = [line for line in Path('/proc/sysvipc/shm').read_text().splitlines()[1:] if int(line.split()[0]) in keys]
assert not ipc, ipc
removed = []

def exact_tree(p):
    if not p.exists() and (not p.is_symlink()):
        return
    if p.is_symlink() or not p.is_dir():
        info = p.lstat()
        removed.append({'path': str(p), 'bytes': info.st_size, 'mode': stat.S_IFMT(info.st_mode)})
        p.unlink()
        return
    for c in list(p.iterdir()):
        exact_tree(c)
    p.rmdir()
(out / 'states.json').write_text(json.dumps(states, indent=2) + '\n')
for n, w in [('source', source), ('b', root / 'b')]:
    (out / (n + '-registry.txt')).write_bytes((w / '.cub-workenv/databases/databases.txt').read_bytes())
cci = source / 'cubrid-cci'
diff = subprocess.check_output(['git', '-C', str(cci), 'diff', '--', 'win/cci_version.h'])
(out / 'cci-generated-header.patch').write_bytes(diff)
(cci / 'win/cci_version.h').write_bytes(subprocess.check_output(['git', '-C', str(cci), 'show', 'HEAD:win/cci_version.h']))
for entry in ['.cub-workenv', 'build_preset_debug_gcc', 'pl_engine/.gradle', '.env', 'csql.err']:
    exact_tree(source / entry)
for entry in ['.clangd', '.envrc', '.just', '.nvim.lua', '.vscode', 'AGENTS.override.md', 'CMakeUserPresets.json', 'cub_server.gdb', 'i.gdb', 'justfile', 'lefthook.yml', 'local.just']:
    p = source / entry
    assert p.is_symlink(), (entry, 'unexpected non-link')
    exact_tree(p)
for sub in ('cubrid-cci', 'cubrid-jdbc'):
    raw = subprocess.check_output(['git', '-C', str(source / sub), 'ls-files', '--others', '--ignored', '--exclude-standard', '-z'])
    for item in raw.split(b'\x00'):
        if item:
            exact_tree(source / sub / os.fsdecode(item))
pre = subprocess.check_output(['git', '-C', str(source), 'status', '--short', '--ignored'], text=True)
(out / 'source-before-remove.txt').write_text(pre)
p = subprocess.run(['git', '-C', '/home/vimkim/gh/cb/develop', 'worktree', 'remove', str(source)], text=True, capture_output=True)
(out / 'source-remove.txt').write_text(p.stdout + p.stderr)
lr = Path(life['runtime_root'])
worktrees = subprocess.check_output(['git', '-C', str(lr / 'repo'), 'worktree', 'list', '--porcelain'], text=True)
for line in worktrees.splitlines():
    if line.startswith('worktree '):
        w = Path(line[9:])
        if w != lr / 'repo':
            raw = subprocess.check_output(['git', '-C', str(w), 'ls-files', '--others', '--exclude-standard', '-z']) + subprocess.check_output(['git', '-C', str(w), 'ls-files', '--others', '--ignored', '--exclude-standard', '-z'])
            for item in raw.split(b'\x00'):
                if item:
                    exact_tree(w / os.fsdecode(item))
            subprocess.run(['git', '-C', str(lr / 'repo'), 'worktree', 'remove', str(w)], check=True)
for t in socket_dirs:
    exact_tree(Path(t))
for r in roots[1:]:
    exact_tree(r)
(out / 'removed-inventory.json').write_text(json.dumps(removed, indent=2) + '\n')
result = {'remaining_owned_pids': remaining, 'remaining_ipc': ipc, 'source_worktree_removal_rc': p.returncode, 'source_worktree_retained': source.exists(), 'source_branch': 'verify/workenv09-source', 'fixture_roots_removed': {str(r): not r.exists() for r in roots[1:]}, 'removed_file_count': len(removed), 'socket_dirs_removed': sorted(socket_dirs)}
(out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
