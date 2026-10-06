"""Prune metadata/resources under controlled Linux process visibility."""
from pathlib import Path
import subprocess
import unittest


class PruneNamespaceTest(unittest.TestCase):
    def test_public_prune_lifecycle(self):
        prefix = ['unshare', '--user', '--map-root-user', '--pid', '--fork', '--mount-proc', '--ipc',
                  'setpriv', '--bounding-set=-all']
        probe = subprocess.run([*prefix, 'true'], capture_output=True, text=True)
        if probe.returncode:
            self.skipTest('Private PID/IPC namespace unavailable: ' + probe.stderr)
        result = subprocess.run([*prefix, 'python3', str(Path(__file__).with_name('prune_cases.py')), '-v'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
