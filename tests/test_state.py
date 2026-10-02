"""Initialization lifecycle checks at the CLI/artifact boundary.

Disposable executable fixtures represent native utility success/failure, not
CUBRID engine correctness (covered by the separate real smoke suite).
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'


class StateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cwe-state-')
        self.root = Path(self.temp.name)
        self.install = self.root / 'install'
        (self.install / 'bin').mkdir(parents=True)
        for name in ('cubrid', 'csql'):
            path = self.install / 'bin' / name
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        self.worktree = self.root / 'source'
        self.worktree.mkdir()

    def tearDown(self):
        registry = self.root / 'host/allocations.json'
        if registry.exists():
            for record in json.loads(registry.read_text()):
                shutil.rmtree(record['tmp'])
        self.temp.cleanup()

    def command(self, worktree=None, *extra):
        return [str(CLI), 'init', '--worktree', str(worktree or self.worktree),
                '--install', str(self.install), '--preset', 'debug',
                '--state-home', str(self.root / 'host'), '--port-start', '43000',
                '--port-end', '43999', *extra]

    def run_init(self, *extra):
        return subprocess.run(self.command(None, *extra), text=True, capture_output=True)

    def snapshot(self):
        return {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def doctor(self):
        return subprocess.run([str(CLI), 'doctor', '--worktree', str(self.worktree)],
                              text=True, capture_output=True)

    def test_repeat_ignores_changed_options_but_detects_missing_artifacts(self):
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        before = self.snapshot()
        result = self.run_init('--install', str(self.root / 'absent'), '--preset', 'other',
                               '--state-home', str(self.root / 'other-host'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('already initialized', result.stdout)
        self.assertEqual(before, self.snapshot())
        (self.worktree / '.cub-workenv/conf/cubrid.conf').unlink()
        before = self.snapshot()
        result = self.run_init()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('doctor', result.stderr)
        self.assertEqual(before, self.snapshot())
        diagnosis = self.doctor()
        self.assertNotEqual(diagnosis.returncode, 0)
        self.assertIn('cubrid.conf', diagnosis.stdout + diagnosis.stderr)
        self.assertEqual(before, self.snapshot())

    def test_native_failure_retains_stage_and_doctor_explains_without_changes(self):
        (self.install / 'bin/cubrid').write_text('#!/bin/sh\necho native-failure-detail >&2\nexit 9\n')
        result = self.run_init()
        self.assertNotEqual(result.returncode, 0)
        state = json.loads((self.worktree / '.cub-workenv/state.json').read_text())
        self.assertEqual(state['status'], 'preparing')
        self.assertIn('database', state.get('stage', ''))
        self.assertIn('createdb failed', state.get('error', ''))
        self.assertFalse((self.worktree / '.cub-workenv/env.sh').exists())
        before = self.snapshot()
        self.assertIn('doctor', self.run_init().stderr)
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('database', result.stdout)
        self.assertIn('createdb.log', result.stdout)
        self.assertEqual(before, self.snapshot())

    def wait_for(self, path):
        deadline = time.monotonic() + 10
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(path.exists(), f'timed out waiting for {path}')

    def test_failure_after_allocation_preserves_work_clues(self):
        import fcntl
        host = self.root / 'host'
        host.mkdir()
        with (host / 'allocations.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen(self.command(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.wait_for(self.worktree / '.cub-workenv/state.json')
                (self.worktree / '.cub-workenv/conf').mkdir()
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
            stdout, stderr = process.communicate(timeout=10)
        self.assertNotEqual(process.returncode, 0, stdout + stderr)
        state = json.loads((self.worktree / '.cub-workenv/state.json').read_text())
        self.assertEqual(state['stage'], 'settings')
        self.assertIn('allocation', state)
        before = self.snapshot()
        self.assertNotEqual(self.run_init().returncode, 0)
        self.assertIn('settings', self.doctor().stdout)
        self.assertEqual(before, self.snapshot())

    def test_failure_after_database_does_not_publish_environment(self):
        (self.install / 'bin/cubrid').write_text('#!/bin/sh\nmkdir env.sh\nexit 0\n')
        result = self.run_init()
        self.assertNotEqual(result.returncode, 0)
        state = json.loads((self.worktree / '.cub-workenv/state.json').read_text())
        self.assertEqual(state['status'], 'preparing')
        self.assertEqual(state['stage'], 'environment publication')
        before = self.snapshot()
        self.assertNotEqual(self.run_init().returncode, 0)
        self.assertIn('environment publication', self.doctor().stdout)
        self.assertEqual(before, self.snapshot())

    def test_terminated_initializer_leaves_incomplete_state(self):
        (self.install / 'bin/cubrid').write_text('#!/bin/sh\nkill -KILL "$PPID"\nexit 0\n')
        result = self.run_init()
        self.assertNotEqual(result.returncode, 0)
        state = json.loads((self.worktree / '.cub-workenv/state.json').read_text())
        self.assertEqual(state['status'], 'preparing')
        self.assertFalse((self.worktree / '.cub-workenv/env.sh').exists())
        before = self.snapshot()
        self.assertIn('doctor', self.run_init().stderr)
        self.assertIn('database', self.doctor().stdout)
        self.assertEqual(before, self.snapshot())

    def test_same_worktree_serializes_but_other_worktree_can_finish(self):
        # A native process waits on an owned gate. B must finish before A is
        # released; another init of A must not invoke a second native process.
        native = self.install / 'bin/cubrid'
        native.write_text('#!/bin/sh\necho call >> calls\ntouch entered\nwhile [ -f hold ]; do sleep 0.02; done\nexit 0\n')
        # Wait on allocation so that the gate can be inserted after initialization
        # accepts the empty root, before the native command is reached.
        import fcntl
        host = self.root / 'host'
        host.mkdir()
        processes = []
        with (host / 'allocations.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            first = subprocess.Popen(self.command(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(first)
            try:
                self.wait_for(self.worktree / '.cub-workenv/state.json')
                gate = self.worktree / '.cub-workenv/hold'
                gate.touch()
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        try:
            self.wait_for(self.worktree / '.cub-workenv/entered')
            repeat = subprocess.Popen(self.command(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(repeat)
            other = self.root / 'other'
            other.mkdir()
            # Dedicated installation also keeps the test compatible with the
            # independent PL resource allocation work in ticket 05.
            other_install = self.root / 'other-install'
            shutil.copytree(self.install, other_install)
            result = subprocess.run(self.command(other, '--install', str(other_install)),
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsNone(first.poll())
            self.assertIsNone(repeat.poll())
            records = json.loads((host / 'allocations.json').read_text())
            self.assertEqual(len(records), 2)
            self.assertEqual(len({r['master_port'] for r in records}), 2)
            self.assertEqual(len({r['tmp'] for r in records}), 2)
        finally:
            gate.unlink(missing_ok=True)
            for process in processes:
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual((self.worktree / '.cub-workenv/calls').read_text(), 'call\n')
        self.assertIn('already initialized', stdout)

    def test_corrupt_state_diagnosis_and_uninitialized_diagnosis_are_read_only(self):
        before = self.snapshot()
        self.assertNotEqual(self.doctor().returncode, 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.run_init().returncode, 0)
        marker = self.worktree / '.cub-workenv/state.json'
        marker.write_text('{broken')
        before = self.snapshot()
        for result in (self.run_init(), self.doctor()):
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('state', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
