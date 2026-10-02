"""Run real process evidence in a private PID namespace, without host ambiguity."""
from pathlib import Path
import shutil
import subprocess
import unittest


class ReclamationNamespaceTest(unittest.TestCase):
    def test_reclamation_public_cli_cases(self):
        if not shutil.which('unshare') or not shutil.which('setpriv'):
            self.skipTest('Linux unshare and setpriv required for isolated process evidence')
        prefix = ['unshare', '--user', '--map-root-user', '--pid', '--fork', '--mount-proc',
                  'setpriv', '--bounding-set=-all']
        probe = subprocess.run([*prefix, 'true'], capture_output=True, text=True)
        if probe.returncode:
            self.skipTest('Private PID/proc namespace unavailable: ' + probe.stderr.strip())
        result = subprocess.run([*prefix, 'python3', str(Path(__file__).with_name('reclamation_cases.py')), '-v'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
