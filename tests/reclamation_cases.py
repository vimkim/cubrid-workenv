"""Finite pools exercised through the CLI and its published allocation records."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'


class ReclamationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cwe-reclaim-')
        self.root = Path(self.temp.name)
        self.tmps = set()
        # Discover a bounded two-port pool without assuming a fixed free range.
        for port in range(47000, 49000, 2):
            with socket.socket() as a, socket.socket() as b:
                try:
                    a.bind(('0.0.0.0', port))
                    b.bind(('0.0.0.0', port + 1))
                except OSError:
                    continue
                self.port = port
                break
        else:
            self.fail('No disposable two-port pool')

    def tearDown(self):
        for path in self.tmps:
            shutil.rmtree(path, ignore_errors=True)
        self.temp.cleanup()

    def records(self):
        return json.loads((self.root / 'host/allocations.json').read_text())

    def command(self, name, *options):
        worktree = self.root / name
        install = worktree / 'install'
        (install / 'bin').mkdir(parents=True)
        # Native-shaped output keeps this allocation fixture compatible with
        # createdb validation; it does not claim engine correctness.
        for tool in ('cubrid', 'csql'):
            binary = install / 'bin' / tool
            binary.write_text('#!/usr/bin/env python3\nimport os,sys,pathlib\na=sys.argv\n'
                'if len(a)>1 and a[1]=="createdb":\n'
                ' d=a[a.index("-F")+1]; l=a[a.index("-L")+1]; b=a[a.index("-B")+1]; n=a[-2]\n'
                ' pathlib.Path(os.environ["CUBRID_DATABASES"],"databases.txt").write_text(f"{n} {d} localhost {l} {b}\\n")\n'
                ' pathlib.Path(d,n).touch()\n')
            binary.chmod(0o755)
        return [str(CLI), 'init', '--worktree', str(worktree), '--install', str(install),
                '--preset', 'debug', '--state-home', str(self.root / 'host'),
                '--port-start', str(self.port), '--port-end', str(self.port + 1), *options]

    def init(self, name, *options):
        result = subprocess.run(self.command(name, *options), text=True, capture_output=True)
        if (self.root / 'host/allocations.json').exists():
            self.tmps.update(r['tmp'] for r in self.records())
        return result

    def test_deleted_inactive_allocation_is_reclaimed_only_at_exhaustion(self):
        self.assertEqual(self.init('one').returncode, 0)
        first = self.records()[0]
        shutil.rmtree(self.root / 'one')
        result = self.init('two', '--port-end', str(self.port + 3))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.records()), 2)
        self.assertFalse((self.root / 'host/allocations-reclamation.json').exists())
        result = self.init('three')
        self.assertEqual(result.returncode, 0, result.stderr)
        records = self.records()
        self.assertNotIn(first, records)
        self.assertEqual(records[-1]['master_port'], first['master_port'])
        self.assertTrue(Path(first['tmp']).exists(), 'reclamation must not remove files')

    def test_stopped_existing_worktree_and_full_pool_report_owner(self):
        self.assertEqual(self.init('one').returncode, 0)
        before = self.records()
        result = self.init('two')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('still exists', result.stderr)
        self.assertIn('--port-start/--port-end', result.stderr)
        self.assertEqual(self.records(), before)

    def test_deleted_worktree_with_ipv6_port_is_retained(self):
        self.assertEqual(self.init('one').returncode, 0)
        before = self.records()
        shutil.rmtree(self.root / 'one')
        with socket.socket(socket.AF_INET6) as occupied:
            occupied.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            occupied.bind(('::1', before[0]['broker_port']))
            result = self.init('two')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('TCP port', result.stderr)
            self.assertEqual(self.records(), before)

    def test_deleted_worktree_with_ipc_or_socket_is_retained(self):
        import ctypes
        self.assertEqual(self.init('one').returncode, 0)
        before = self.records()
        record = before[0]
        shutil.rmtree(self.root / 'one')
        libc = ctypes.CDLL(None, use_errno=True)
        segment = libc.shmget(record['broker_appl_server_shm_id'], 4096, 0o1000 | 0o2000 | 0o600)
        self.assertGreaterEqual(segment, 0)
        try:
            result = self.init('two')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('shared memory remains', result.stderr)
            self.assertEqual(self.records(), before)
            self.assertEqual(libc.shmget(record['broker_appl_server_shm_id'], 0, 0), segment)
        finally:
            self.assertEqual(libc.shmctl(segment, 0, None), 0)
        with socket.socket(socket.AF_UNIX) as sock:
            path = Path(record['tmp']) / 'sp_testdb.sock'
            sock.bind(str(path))
            result = self.init('three')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('socket/TMP', result.stderr)
            self.assertTrue(path.exists())
            path.unlink()
            result = self.init('four')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('live Unix socket', result.stderr)
        self.assertEqual(self.records(), before)

    def test_deleted_worktree_with_living_owner_is_retained(self):
        self.assertEqual(self.init('one').returncode, 0)
        before = self.records()
        env = dict(os.environ, CUBRID=before[0]['install'])
        process = subprocess.Popen(['sleep', '30'], env=env)
        try:
            shutil.rmtree(self.root / 'one')
            result = self.init('two')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('live owner PID', result.stderr)
            self.assertEqual(self.records(), before)
            self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_inaccessible_path_and_broken_symlink_are_uncertain(self):
        self.assertEqual(self.init('parent/one').returncode, 0)
        before = self.records()
        parent = self.root / 'parent'
        parent.chmod(0)
        try:
            result = self.init('two')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('path inspection uncertain', result.stderr)
            self.assertEqual(self.records(), before)
        finally:
            parent.chmod(0o700)
        shutil.rmtree(parent / 'one')
        (parent / 'one').symlink_to(parent / 'missing')
        result = self.init('three')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlink', result.stderr)
        self.assertEqual(self.records(), before)

    def test_inaccessible_process_environment_is_uncertain(self):
        import sys
        self.assertEqual(self.init('one').returncode, 0)
        before = self.records()
        process = subprocess.Popen([sys.executable, '-c',
            'import ctypes,time; ctypes.CDLL(None).prctl(4,0); print("ready",flush=True); time.sleep(30)'],
            stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            shutil.rmtree(self.root / 'one')
            result = self.init('two')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('process inspection uncertain', result.stderr)
            self.assertEqual(self.records(), before)
            self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait(timeout=5)
            process.stdout.close()

    def test_shared_memory_exhaustion_also_reclaims_deleted_records(self):
        options = ('--shm-start', '0x62710000', '--shm-end', '0x62710001',
                   '--port-end', str(self.port + 9))
        self.assertEqual(self.init('one', *options).returncode, 0)
        first = self.records()[0]
        shutil.rmtree(self.root / 'one')
        result = self.init('two', *options)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records()[0]['broker_master_shm_id'], first['broker_master_shm_id'])

    def test_concurrent_reclamation_allocates_slot_once(self):
        self.assertEqual(self.init('one').returncode, 0)
        shutil.rmtree(self.root / 'one')
        commands = [self.command(name) for name in ('two', 'three')]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for command in commands]
        results = [process.communicate(timeout=10) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1], results)
        self.assertEqual(len(self.records()), 1)
        self.tmps.update(r['tmp'] for r in self.records())


if __name__ == '__main__':
    unittest.main()
