import json
import unittest
import subprocess
from pathlib import Path
import test_cli as fixtures
CLI = fixtures.CLI


class DatabaseTest(unittest.TestCase):
    setUp = fixtures.AllocationAndPreservationTest.setUp
    tearDown = fixtures.AllocationAndPreservationTest.tearDown
    init = fixtures.AllocationAndPreservationTest.init
    def test_no_db_then_create_at_explicit_location(self):
        target = self.root / 'source'
        result = self.init(target, '--no-db', '--port-start', '44000', '--port-end', '44999')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((target / '.cub-workenv/db').exists())
        self.assertEqual((target / '.cub-workenv/databases/databases.txt').read_text(), '')
        result = subprocess.run([str(CLI), 'create-db', 'later', '--worktree', str(target),
            '--path', str(self.root / 'external')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'external/data').is_dir())
        receipt = json.loads((target / '.cub-workenv/created-later.json').read_text())
        self.assertEqual(receipt['base'], str(self.root / 'external'))
        self.assertEqual(receipt['primary_inode'], (self.root / 'external/data/later').stat().st_ino)

    def test_existing_registry_and_storage_are_preserved_and_duplicate_refused(self):
        target = self.root / 'reuse'
        storage = self.root / 'old'
        for part in ('data', 'log', 'lob'):
            (storage / part).mkdir(parents=True)
        (storage / 'data/testdb').write_text('sentinel')
        (storage / 'log/testdb_lgat').write_text('sentinel-log')
        registry = self.root / 'existing.txt'
        original = (f'# keep comment\ntestdb {storage}/data localhost {storage}/log file:{storage}/lob\n'
                    'extra /unrelated localhost /unrelated/log file:/unrelated/lob\n').encode()
        registry.write_bytes(original)
        result = self.init(target, '--database-registry', str(registry))
        self.assertEqual(result.returncode, 0, result.stderr)
        prepared = target / '.cub-workenv/databases/databases.txt'
        self.assertEqual(prepared.read_bytes(), original)
        result = subprocess.run([str(CLI), 'create-db', 'testdb', '--worktree', str(target),
                                 '--path', str(self.root / 'new')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already registered', result.stderr)
        self.assertFalse((self.root / 'new').exists())
        self.assertEqual(prepared.read_bytes(), original)
        self.assertEqual((storage / 'data/testdb').read_text(), 'sentinel')
        self.assertFalse((target / '.cub-workenv/created-testdb.json').exists())

    def test_retained_provenance_blocks_name_reuse_before_creating_storage(self):
        target = self.root / 'provenance'
        self.assertEqual(self.init(target).returncode, 0)
        receipt = target / '.cub-workenv/created-testdb.json'
        before = receipt.read_bytes()
        registry = target / '.cub-workenv/databases/databases.txt'
        registry.write_bytes(b'')  # Model a manual registration removal.
        new_location = self.root / 'replacement'
        result = subprocess.run([str(CLI), 'create-db', 'testdb', '--worktree', str(target),
                                 '--path', str(new_location)], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('provenance', result.stderr)
        self.assertEqual(receipt.read_bytes(), before)
        self.assertFalse(new_location.exists())

    def test_no_db_preserves_registry_bytes_even_without_storage(self):
        target = self.root / 'only-environment'
        registry = self.root / 'registry'
        content = b'# comments\r\ntestdb /missing localhost /missing file:/missing\r\n'
        registry.write_bytes(content)
        result = self.init(target, '--no-db', '--database-registry', str(registry))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((target / '.cub-workenv/databases/databases.txt').read_bytes(), content)
        self.assertFalse((target / '.cub-workenv/db').exists())

    def test_invalid_existing_registration_fails_without_ready_environment(self):
        target = self.root / 'bad'
        target.mkdir()
        content = 'testdb /missing remote-host /missing file:/missing\n'
        (target / 'databases.txt').write_text(content)
        result = self.init(target)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((target / '.cub-workenv/env.sh').exists())
        self.assertEqual((target / 'databases.txt').read_text(), content)
        self.assertEqual(json.loads((target / '.cub-workenv/state.json').read_text())['status'], 'preparing')

    def test_long_pl_socket_path_refuses_creation_before_touching_storage(self):
        target = self.root / 'socket-limit'
        self.assertEqual(self.init(target, '--no-db').returncode, 0)
        marker = target / '.cub-workenv/state.json'
        state = json.loads(marker.read_text())
        # Exercise the generated-artifact seam with a valid but long TMP path.
        original_tmp = state['allocation']['tmp']
        state['allocation']['tmp'] = original_tmp + '/long-socket-directory'
        marker.write_text(json.dumps(state))
        result = subprocess.run([str(CLI), 'create-db', 'a' * 63, '--worktree', str(target),
                                 '--path', str(self.root / 'untouched')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'untouched').exists())
