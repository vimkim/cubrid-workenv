"""Run reset process/IPC evidence without host visibility ambiguity."""
from pathlib import Path
import subprocess
import unittest


class ResetNamespaceTest(unittest.TestCase):
    def test_public_reset_lifecycle(self):
        prefix = ['unshare', '--user', '--map-root-user', '--pid', '--fork', '--mount-proc', '--ipc',
                  'setpriv', '--bounding-set=-all']
        probe = subprocess.run([*prefix, 'true'], capture_output=True, text=True)
        if probe.returncode:
            self.skipTest('Private PID/IPC namespace unavailable: ' + probe.stderr)
        result = subprocess.run([*prefix, 'python3', str(Path(__file__).with_name('reset_cases.py')), '-v'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
