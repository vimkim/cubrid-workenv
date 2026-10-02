"""Environment loading through the public CLI and generated bash artifact."""
import json
import os
from pathlib import Path
import subprocess
import unittest
import test_cli

CLI = test_cli.CLI


class EnvironmentTest(unittest.TestCase):
    setUp = test_cli.AllocationAndPreservationTest.setUp
    tearDown = test_cli.AllocationAndPreservationTest.tearDown
    init = test_cli.AllocationAndPreservationTest.init
    def test_loading_preserves_tools_and_rejects_partial_inherited_runtime(self):
        worktree = self.root / 'source'
        result = self.init(worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        artifact = worktree / '.cub-workenv/env.sh'
        env = dict(os.environ, CUBRID='/old/install', CUBRID_TMP='/old/tmp',
                   CUBRID_CUBRID_PORT_ID='12345', PATH='/tools/bin:/old/install/bin:/usr/bin:/bin',
                   LD_LIBRARY_PATH='/tools/lib:/old/install/lib', PRESET_MODE='debug')
        script = 'source "$1"; source "$1"; status=$?; /usr/bin/python3 -c "import os,json; print(json.dumps(dict(os.environ)))"; exit "$status"'
        def load():
            return subprocess.run(['bash', '-c', script, 'bash', str(artifact)], env=env,
                                  text=True, capture_output=True, cwd=worktree)
        loaded = load()
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        values = json.loads(loaded.stdout)
        self.assertIn('/tools/bin', values['PATH'])
        self.assertNotIn('/old/install/bin', values['PATH'])
        self.assertIn('/tools/lib', values['LD_LIBRARY_PATH'])
        self.assertEqual(values['PATH'].split(':').count(str(self.install / 'bin')), 1)
        self.assertEqual(values['LD_LIBRARY_PATH'].split(':').count(str(self.install / 'lib')), 1)
        state_path = worktree / '.cub-workenv/state.json'
        state = json.loads(state_path.read_text())
        state['status'] = 'preparing'
        state_path.write_text(json.dumps(state))
        partial = load()
        self.assertNotEqual(partial.returncode, 0)
        values = json.loads(partial.stdout)
        self.assertNotIn('CUBRID_TMP', values)
        self.assertNotIn('CUBRID_CUBRID_PORT_ID', values)
        self.assertNotIn('/old/install/bin', values['PATH'])

    def test_public_loader_matches_preset_and_install_and_cleans_on_error(self):
        worktree = self.root / 'source'
        self.assertEqual(self.init(worktree).returncode, 0)
        for extra, expected in (([], 0), (['--preset', 'release'], 1),
                                (['--install', str(self.root / 'other-install')], 1)):
            result = subprocess.run([str(CLI), 'env', '--worktree', str(worktree), *extra],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, expected, result.stderr)
            loaded = subprocess.run(['bash', '-c', result.stdout + '\nprintf "ready=%s tmp=%s" "${CUBRID_RUNTIME_READY:-}" "${CUBRID_TMP:-}"'],
                                    env=dict(os.environ, PRESET_MODE='debug', CUBRID='/old', CUBRID_TMP='/old/tmp'),
                                    text=True, capture_output=True)
            if expected:
                self.assertIn('doctor', result.stderr)
                self.assertEqual(loaded.stdout, 'ready=0 tmp=')
            else:
                self.assertIn('ready=1 tmp=', loaded.stdout)

    def test_missing_environment_emits_build_only_cleanup_without_writes(self):
        worktree = self.root / 'empty'
        worktree.mkdir()
        result = subprocess.run([str(CLI), 'env', '--worktree', str(worktree)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('init explicitly', result.stderr)
        self.assertEqual(list(worktree.iterdir()), [])
