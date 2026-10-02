import os
from pathlib import Path
import subprocess
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'

class InitializeTest(unittest.TestCase):
    def test_missing_install_guides_build_without_initializing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run([str(CLI), 'init', '--worktree', tmp,
                '--install', str(root / 'absent'), '--preset', 'debug'], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('build', result.stderr.lower())
            self.assertFalse((root / '.cub-workenv/state.json').exists())


class AllocationAndPreservationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cwe-cli-')
        self.root = Path(self.temp.name)
        self.install = self.root / 'install'
        (self.install / 'bin').mkdir(parents=True)
        for name in ('cubrid', 'csql'):
            executable = self.install / 'bin' / name
            executable.write_text('#!/bin/sh\nexit 0\n')
            executable.chmod(0o755)

    def tearDown(self):
        import json
        import shutil
        registry = self.root / 'host/allocations.json'
        if registry.exists():
            for item in json.loads(registry.read_text()):
                shutil.rmtree(item['tmp'])
        self.temp.cleanup()

    def init(self, worktree, *extra):
        worktree.mkdir(parents=True, exist_ok=True)
        import shutil
        install = worktree / 'install'
        if not install.exists():
            shutil.copytree(self.install, install)
        return subprocess.run([str(CLI), 'init', '--worktree', str(worktree), '--install', str(install),
            '--preset', 'debug', '--state-home', str(self.root / 'host'), *extra], text=True, capture_output=True)

    def test_same_basename_avoids_active_and_recorded_ports(self):
        import json
        import socket
        with socket.socket() as occupied:
            occupied.bind(('0.0.0.0', 0))
            port = occupied.getsockname()[1]
            options = ('--port-start', str(port), '--port-end', str(min(port + 20, 65535)))
            first = self.root / 'a/source'
            second = self.root / 'b/source'
            self.assertEqual(self.init(first, *options).returncode, 0)
            self.assertEqual(self.init(second, *options).returncode, 0)
            records = json.loads((self.root / 'host/allocations.json').read_text())
            self.assertEqual(len({r['master_port'] for r in records}), 2)
            self.assertNotIn(port, [r['master_port'] for r in records])
            self.assertEqual(len({r['tmp'] for r in records}), 2)
            self.assertTrue(all(len(r['tmp'] + '/CUBRID65535') < 108 for r in records))

    def test_broker_and_pl_settings_are_isolated(self):
        import json
        targets = [self.root / 'a', self.root / 'b']
        for target in targets:
            result = self.init(target, '--port-start', '45000', '--port-end', '45999')
            self.assertEqual(result.returncode, 0, result.stderr)
        records = json.loads((self.root / 'host/allocations.json').read_text())
        ports = [r[key] for r in records for key in ('master_port', 'broker_port')]
        keys = [r[key] for r in records for key in ('broker_master_shm_id', 'broker_appl_server_shm_id')]
        self.assertEqual(len(set(ports)), 4)
        self.assertEqual(len(set(keys)), 4)
        for target in targets:
            conf = (target / '.cub-workenv/conf/cubrid.conf').read_text()
            self.assertIn('stored_procedure=yes', conf)
            self.assertIn('stored_procedure_uds=yes', conf)
            broker = (target / '.cub-workenv/conf/cubrid_broker.conf').read_text()
            self.assertEqual(broker.count('[%'), 1)
            self.assertIn('APPL_SERVER_SHM_ID=', broker)
            self.assertIn('CUBRID_BROKER_CONF_FILE', (target / '.cub-workenv/env.sh').read_text())

    def test_live_shared_memory_is_skipped(self):
        import ctypes
        import json
        libc = ctypes.CDLL(None, use_errno=True)
        key = 0x62100000
        while True:
            segment = libc.shmget(key, 4096, 0o1000 | 0o2000 | 0o600)
            if segment >= 0:
                break
            if ctypes.get_errno() != 17:
                self.fail('Cannot create disposable SysV shared memory')
            key += 1
        try:
            target = self.root / 'ipc'
            result = self.init(target, '--shm-start', hex(key), '--shm-end', hex(key + 20))
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((target / '.cub-workenv/state.json').read_text())
            self.assertNotIn(key, [state['allocation']['broker_master_shm_id'],
                                   state['allocation']['broker_appl_server_shm_id']])
        finally:
            self.assertEqual(libc.shmctl(segment, 0, None), 0)

    def test_shared_installation_is_rejected_for_pl_safety(self):
        first = self.root / 'one'
        self.assertEqual(self.init(first).returncode, 0)
        second = self.root / 'two'
        second.mkdir()
        result = subprocess.run([str(CLI), 'init', '--worktree', str(second),
            '--install', str(first / 'install'), '--preset', 'debug',
            '--state-home', str(self.root / 'host')], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('dedicated installation', result.stderr)

    def test_repeat_preserves_artifacts_and_unknown_settings_are_rejected(self):
        first = self.root / 'one'
        self.assertEqual(self.init(first).returncode, 0)
        before = {str(p): p.read_bytes() for p in first.rglob('*') if p.is_file()}
        result = self.init(first)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('already initialized', result.stdout)
        self.assertEqual(before, {str(p): p.read_bytes() for p in first.rglob('*') if p.is_file()})
        other = self.root / 'other/.cub-workenv'
        other.mkdir(parents=True)
        (other / 'databases.txt').write_text('valuable existing database registration\n')
        result = self.init(other.parent)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((other / 'databases.txt').read_text(), 'valuable existing database registration\n')

    def test_exhaustion_retains_incomplete_state_without_environment(self):
        import json
        import socket
        with socket.socket() as occupied:
            occupied.bind(('0.0.0.0', 0))
            port = occupied.getsockname()[1]
            target = self.root / 'source'
            result = self.init(target, '--port-start', str(port), '--port-end', str(port))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('exhausted', result.stderr)
            self.assertEqual(json.loads((target / '.cub-workenv/state.json').read_text())['status'], 'preparing')
            self.assertFalse((target / '.cub-workenv/env.sh').exists())
            self.assertIn('doctor', self.init(target).stderr)

    def test_existing_unregistered_default_db_is_not_ignored(self):
        target = self.root / 'source'
        (target / 'databases').mkdir(parents=True)
        existing = target / 'databases/databases.txt'
        existing.write_text('testdb /valuable/storage localhost /valuable/log\n')
        result = self.init(target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('existing', result.stderr.lower())
        self.assertEqual(existing.read_text(), 'testdb /valuable/storage localhost /valuable/log\n')

    def test_existing_short_digest_directory_is_preserved_and_extended(self):
        import hashlib
        import json
        import shutil
        target = self.root / 'source'
        target.mkdir()
        digest = hashlib.sha256(str(target.resolve()).encode()).hexdigest()
        conflict = Path('/tmp') / f'cwe-{os.getuid()}' / digest[:12]
        conflict.mkdir(parents=True)
        (conflict / 'owner-marker').write_text('other owner')
        try:
            result = self.init(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((target / '.cub-workenv/state.json').read_text())
            self.assertNotEqual(state['allocation']['tmp'], str(conflict))
            self.assertEqual((conflict / 'owner-marker').read_text(), 'other owner')
        finally:
            shutil.rmtree(conflict)

if __name__ == '__main__':
    unittest.main()
