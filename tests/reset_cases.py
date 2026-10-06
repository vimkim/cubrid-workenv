"""Public reset lifecycle tests in a private PID/proc namespace."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'


class ResetCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cwe-reset-')
        self.root = Path(self.temp.name)
        self.home = self.root / 'host'
        self.trees = [self.root / 'a', self.root / 'b']
        for tree in self.trees:
            tree.mkdir()
            install = tree / 'install'
            (install / 'bin').mkdir(parents=True)
            for name in ('cubrid', 'csql'):
                path = install / 'bin' / name
                path.write_text('#!/bin/sh\nexit 0\n')
                path.chmod(0o755)
            self.init(tree)
        self.tmps = [Path(self.state(t)['allocation']['tmp']) for t in self.trees]

    def tearDown(self):
        for path in self.tmps:
            path.rmdir()
        self.temp.cleanup()

    def call(self, *args, code=0):
        result = subprocess.run([str(CLI), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def init(self, tree):
        return self.call('init', '--worktree', tree, '--install', tree / 'install',
                         '--preset', 'debug', '--state-home', self.home, '--no-db',
                         '--port-start', '46100', '--port-end', '46109')

    def state(self, tree):
        return json.loads((tree / '.cub-workenv/state.json').read_text())

    def files(self):
        return {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_preview_single_reset_and_reinit_preserve_unique_paths_and_data(self):
        tree = self.trees[0]
        state = self.state(tree)
        folder = tree / '.cub-workenv'
        (folder / 'db').mkdir()
        (folder / 'db/data').write_bytes(b'valuable database')
        (folder / 'createdb-testdb.log').write_text('native log retained')
        config = folder / 'conf/cubrid.conf'
        config.write_text(config.read_text() + '\n# tuning retained\nlock_timeout=42\n')
        before = self.files()
        self.call('reset', '--state-home', self.home, '--worktree', tree)
        self.assertEqual(before, self.files())
        self.call('reset', '--state-home', self.home, '--worktree', tree, '--apply')
        self.assertEqual(self.state(tree)['status'], 'reset')
        self.assertEqual(self.state(self.trees[1])['status'], 'ready')
        self.assertEqual(before[str(self.trees[1] / '.cub-workenv/state.json')],
                         (self.trees[1] / '.cub-workenv/state.json').read_bytes())
        self.assertEqual((folder / 'db/data').read_bytes(), b'valuable database')
        self.assertEqual((folder / 'createdb-testdb.log').read_text(), 'native log retained')
        self.call('env', '--worktree', tree, code=1)
        self.assertIn('Numeric resources reset', self.call('doctor', '--worktree', tree, code=1).stderr)
        loaded = subprocess.run(['bash', '-c', 'source "$1"', '_', str(folder / 'env.sh')], capture_output=True)
        self.assertNotEqual(loaded.returncode, 0)
        self.init(tree)
        self.assertEqual(self.state(tree)['allocation'], state['allocation'])
        self.assertIn('# tuning retained\nlock_timeout=42', config.read_text())

    def test_single_reset_defaults_to_recorded_namespace_and_retains_registry(self):
        tree = self.trees[0]
        folder = tree / '.cub-workenv'
        data = folder / 'db/testdb/data'
        log = folder / 'db/testdb/log'
        lob = folder / 'db/testdb/lob'
        for path in (data, log, lob):
            path.mkdir(parents=True)
        (data / 'testdb').write_bytes(b'preserved-primary')
        (log / 'testdb_lgat').write_bytes(b'preserved-active-log')
        registry = folder / 'databases/databases.txt'
        content = f'# keep comments\ntestdb {data} localhost {log} file:{lob}\n'
        registry.write_text(content)
        self.call('reset', '--worktree', tree, '--apply')
        self.call('init', '--worktree', tree, '--install', tree / 'install', '--preset', 'debug',
                  '--state-home', self.home, '--port-start', '46100', '--port-end', '46109')
        self.assertEqual(registry.read_text(), content)
        self.assertEqual((data / 'testdb').read_bytes(), b'preserved-primary')
        self.assertEqual((log / 'testdb_lgat').read_bytes(), b'preserved-active-log')

    def test_reset_all_reuses_first_numeric_slots_in_new_order(self):
        old = [self.state(t)['allocation'] for t in self.trees]
        self.call('reset-all', '--state-home', self.home, '--apply')
        for tree in reversed(self.trees):
            self.init(tree)
        new = [self.state(t)['allocation'] for t in self.trees]
        for key in ('master_port', 'broker_port', 'broker_master_shm_id', 'broker_appl_server_shm_id'):
            self.assertEqual(new[1][key], old[0][key])
            self.assertEqual(new[0][key], old[1][key])
        for i in range(2):
            self.assertEqual(new[i]['tmp'], old[i]['tmp'])
            self.assertEqual(new[i]['install'], old[i]['install'])

    def test_busy_port_refuses_whole_reset(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', self.state(self.trees[1])['allocation']['master_port']))
            listener.listen()
            before = self.files()
            result = self.call('reset-all', '--state-home', self.home, '--apply', code=1)
            self.assertIn('TCP', result.stderr)
            self.assertEqual(before, self.files())

    def test_live_owner_refuses_reset_without_listening_socket(self):
        state = self.state(self.trees[0])
        proc = subprocess.Popen(['sleep', '30'], env=dict(os.environ, CUBRID=state['install']))
        try:
            before = self.files()
            result = self.call('reset', '--state-home', self.home, '--worktree', self.trees[0], '--apply', code=1)
            self.assertIn('live', result.stderr)
            self.assertEqual(before, self.files())
        finally:
            proc.terminate()
            proc.wait()

    def test_kernel_shm_is_not_removed_or_reallocated(self):
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        key = self.state(self.trees[0])['allocation']['broker_master_shm_id']
        segment = libc.shmget(key, 4096, 0o1000 | 0o2000 | 0o600)
        self.assertGreaterEqual(segment, 0, ctypes.get_errno())
        try:
            before = self.files()
            result = self.call('reset-all', '--state-home', self.home, '--apply', code=1)
            self.assertIn('SHM', result.stderr)
            self.assertEqual(before, self.files())
            self.assertEqual(libc.shmget(key, 4096, 0o600), segment)
        finally:
            self.assertEqual(libc.shmctl(segment, 0, None), 0)

    def test_live_unix_socket_blocks_but_stale_path_is_preserved(self):
        tree = self.trees[0]
        path = Path(self.state(tree)['allocation']['tmp']) / 'sp_testdb.sock'
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(path))
            listener.listen()
            before = self.files()
            result = self.call('reset', '--worktree', tree, '--apply', code=1)
            self.assertIn('live Unix socket', result.stderr)
            self.assertEqual(before, self.files())
        try:
            self.call('reset', '--worktree', tree, '--apply')
            self.assertTrue(path.exists())
        finally:
            path.unlink()

    def test_active_initializer_refuses_without_deadlock(self):
        import fcntl
        with (self.trees[0] / '.cub-workenv/init.lock').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            before = self.files()
            result = self.call('reset-all', '--state-home', self.home, '--apply', code=1)
            self.assertIn('operation active', result.stderr)
            self.assertEqual(before, self.files())

    def test_interrupted_publication_can_be_completed_by_rerunning_reset(self):
        tree = self.trees[0]
        state = self.state(tree)
        previous = state['allocation']
        state.update(status='reset', previous_allocation=previous,
                     allocation={k: previous[k] for k in ('worktree', 'install', 'tmp')})
        state['allocation']['status'] = 'reset'
        (tree / '.cub-workenv/state.json').write_text(json.dumps(state))
        self.call('reset-all', '--state-home', self.home, '--apply')
        self.init(tree)
        self.assertEqual(self.state(tree)['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
