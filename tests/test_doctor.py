"""Diagnosis at the CLI boundary, using disposable native utility fixtures."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cwe-doctor-')
        self.root = Path(self.temp.name)
        self.work = self.root / 'source'
        self.work.mkdir()
        install = self.root / 'install/bin'
        install.mkdir(parents=True)
        for name in ('cubrid', 'csql'):
            binary = install / name
            binary.write_text('#!/bin/sh\necho unexpected-native-command >&2\nexit 98\n')
            binary.chmod(0o755)
        result = subprocess.run([str(CLI), 'init', '--worktree', str(self.work),
            '--install', str(install.parent), '--preset', 'debug', '--no-db',
            '--state-home', str(self.root / 'host'), '--port-start', '47000', '--port-end', '47999'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.runtime = self.work / '.cub-workenv'
        self.state = json.loads((self.runtime / 'state.json').read_text())

    def tearDown(self):
        shutil.rmtree(self.state['allocation']['tmp'])
        self.temp.cleanup()

    def snapshot(self):
        return {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def doctor(self, *extra):
        before = self.snapshot()
        result = subprocess.run([str(CLI), 'doctor', '--worktree', str(self.work), *extra],
                                capture_output=True, text=True)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn('Traceback', result.stderr)
        return result

    def test_config_drift_has_manual_guidance_and_preserves_everything(self):
        conf = self.runtime / 'conf/cubrid.conf'
        conf.write_text(conf.read_text().replace(f"cubrid_port_id={self.state['allocation']['master_port']}", 'cubrid_port_id=9999'))
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cubrid_port_id', result.stderr)
        self.assertIn('manually', result.stderr)

    def test_selection_and_native_error_preserved_with_unknown_owner(self):
        error = self.root / 'native.txt'
        text = 'ERROR: Unable to mount database volume "/missing/testdb_lgat". The volume is in use by user tester on host remote with process 99999999.\n'
        error.write_text(text)
        result = self.doctor('--preset', 'release', '--native-error-file', str(error))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(text, result.stdout)
        self.assertIn('release', result.stderr)
        self.assertIn('unconfirmed', result.stdout)

    def test_external_and_additional_databases_are_valid_but_missing_volume_is_not(self):
        storage = self.root / 'external'
        storage.mkdir()
        for name in ('testdb', 'extra'):
            (storage / name).touch()
            (storage / (name + '_lgat')).touch()
        registry = self.runtime / 'databases/databases.txt'
        registry.write_text(''.join(f'{name} {storage} localhost {storage} file:{storage}\n' for name in ('testdb', 'extra')))
        result = self.doctor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (storage / 'extra').unlink()
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('extra', result.stderr)

    def test_conflicting_record_and_real_socket_report_pid_without_inventing_owner(self):
        allocation = self.state['allocation']
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', allocation['master_port']))
            listener.listen()
            result = self.doctor()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f'PID {os.getpid()} worktree=unconfirmed', result.stdout)
            self.assertEqual(listener.getsockname()[1], allocation['master_port'])
        other = dict(allocation, worktree=str(self.root / 'other'))
        (self.root / 'host/allocations.json').write_text(json.dumps([allocation, other]))
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Allocation conflict', result.stderr)
        self.assertIn(str(self.root / 'other'), result.stderr)

    def test_database_section_lock_disable_is_diagnosed_without_running_native_command(self):
        conf = self.runtime / 'conf/cubrid.conf'
        conf.write_text(conf.read_text() + '\n[@extra]\nfile_lock=no\n')
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('file_lock=no', result.stderr)
        self.assertIn('native DB locking is disabled', result.stderr)

    def test_live_process_lock_override_is_reported(self):
        allocation = self.state['allocation']
        env = dict(os.environ, CUBRID=str(self.root / 'install'),
            CUBRID_CONF_FILE=str(self.runtime / 'conf/cubrid.conf'),
            CUBRID_DATABASES=str(self.runtime / 'databases'), CUBRID_TMP=allocation['tmp'],
            CUBRID_CUBRID_PORT_ID=str(allocation['master_port']), CUBRID_FILE_LOCK='no')
        proc = subprocess.Popen(['/bin/sleep', '30'], env=env)
        try:
            result = self.doctor()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('CUBRID_FILE_LOCK=no', result.stderr)
            self.assertIsNone(proc.poll())
        finally:
            proc.terminate()
            proc.wait()

    def test_extra_broker_resources_cannot_be_reported_as_fully_checked(self):
        conf = self.runtime / 'conf/cubrid_broker.conf'
        conf.write_text(conf.read_text() + '\n[%manual]\nSERVICE=ON\nBROKER_PORT=49999\nAPPL_SERVER_SHM_ID=12345\n')
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unallocated', result.stderr)
        self.assertIn('%manual', result.stderr)

    def test_stale_socket_path_reports_uncertainty_without_removing_it(self):
        allocation = self.state['allocation']
        path = Path(allocation['tmp']) / f"CUBRID{allocation['master_port']}"
        with socket.socket(socket.AF_UNIX) as sock:
            sock.bind(str(path))
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stale', result.stderr)
        self.assertTrue(path.exists())

    def test_selected_installation_drift_from_allocation_is_reported(self):
        other = self.root / 'other-install'
        shutil.copytree(self.root / 'install', other)
        state = dict(self.state, install=str(other))
        (self.runtime / 'state.json').write_text(json.dumps(state))
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('installation', result.stderr)

    def test_legacy_additional_registration_without_lob_is_valid(self):
        storage = self.root / 'legacy-storage'
        storage.mkdir()
        (storage / 'extra').touch()
        (storage / 'extra_lgat').touch()
        registry = self.runtime / 'databases/databases.txt'
        registry.write_text(f'extra {storage} localhost {storage}\n')
        result = self.doctor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('LOB=not registered', result.stdout)
        (storage / 'extra_lgat').unlink()
        result = self.doctor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing physical volume or active log', result.stderr)
        for row in (f'extra {storage} localhost', f'extra {storage} localhost {storage} file:{storage} unexpected'):
            with self.subTest(row=row):
                registry.write_text(row + '\n')
                result = self.doctor()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('malformed registry row', result.stderr)

    def test_legacy_registration_lock_owner_matches_existing_error(self):
        # Exercise both public reports against a real kernel advisory lock on a
        # synthetic volume. This fixture does not launch CUBRID or open a real DB.
        import pwd
        import sys
        storage = self.root / 'lock-fixture'
        storage.mkdir()
        (storage / 'extra').touch()
        active = storage / 'extra_lgat'
        active.touch()
        (self.runtime / 'databases/databases.txt').write_text(f'extra {storage} localhost {storage}\n')
        allocation = self.state['allocation']
        env = dict(os.environ, CUBRID=str(self.root / 'install'),
            CUBRID_CONF_FILE=str(self.runtime / 'conf/cubrid.conf'),
            CUBRID_DATABASES=str(self.runtime / 'databases'), CUBRID_TMP=allocation['tmp'],
            CUBRID_CUBRID_PORT_ID=str(allocation['master_port']))
        child = subprocess.Popen([sys.executable, '-u', '-c',
            'import fcntl,sys; f=open(sys.argv[1], "r+"); fcntl.lockf(f, fcntl.LOCK_EX); print("locked"); input()',
            str(active)], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'locked')
            error = self.root / 'captured-error.txt'
            error.write_text(f'Unable to mount disk volume "{active}". The database is in use by user '
                f'{pwd.getpwuid(os.getuid()).pw_name} on process {child.pid} of host {socket.gethostname()} since fixture.\n')
            result = self.doctor('--native-error-file', str(error))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f'DB extra: native active-log lock PID {child.pid}, worktree={self.work}', result.stdout)
            self.assertIn(f'Native owner confirmed now: PID {child.pid}, worktree={self.work}', result.stdout)
            self.assertIsNone(child.poll())
        finally:
            child.communicate(input='\n', timeout=5)
