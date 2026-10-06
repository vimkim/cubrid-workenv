"""Real Git and allocator lifecycle in private PID/proc/IPC namespaces."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin/cub-workenv'


class PruneCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cwe-prune-')
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.home = self.root / 'host'
        self.tmps = []
        self.git('init', '-q')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--allow-empty', '-qm', 'fixture')

    def tearDown(self):
        for path in self.tmps:
            path.rmdir()
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def linked(self, name, initialized=False):
        tree = self.root / name
        self.git('worktree', 'add', '-qb', name.replace(' ', '-'), str(tree))
        if initialized:
            install = self.root / (name + '-install')
            (install / 'bin').mkdir(parents=True)
            for binary in ('cubrid', 'csql'):
                path = install / 'bin' / binary
                path.write_text('#!/bin/sh\nexit 0\n')
                path.chmod(0o755)
            p = subprocess.run([str(CLI), 'init', '--worktree', str(tree), '--install', str(install),
                                '--preset', 'debug', '--no-db', '--state-home', str(self.home)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            state = json.loads((tree / '.cub-workenv/state.json').read_text())
            self.tmps.append(Path(state['allocation']['tmp']))
        return tree

    def prune(self, apply=False, code=0):
        args = [str(CLI), 'prune', '--worktree', str(self.repo), '--state-home', str(self.home)]
        if apply:
            args.append('--apply')
        p = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return p

    def records(self):
        return json.loads((self.home / 'allocations.json').read_text())

    def test_preview_and_apply_missing_uninitialized_tree(self):
        tree = self.linked('gone with spaces')
        live = self.linked('live')
        (live / 'user-file').write_text('keep me')
        shutil.rmtree(tree)
        before = self.git('worktree', 'list', '--porcelain')
        self.assertIn('WOULD PRUNE', self.prune().stdout)
        self.assertEqual(self.git('worktree', 'list', '--porcelain'), before)
        self.assertFalse(self.home.exists())
        self.prune(apply=True)
        self.assertNotIn(str(tree), self.git('worktree', 'list', '--porcelain'))
        self.assertIn(str(live), self.git('worktree', 'list', '--porcelain'))
        self.assertEqual((live / 'user-file').read_text(), 'keep me')
        self.assertIn('gone-with-spaces', self.git('branch', '--list'))
        self.assertIn('No missing', self.prune(apply=True).stdout)

    def test_release_missing_idle_allocation_preserves_live_and_external_paths(self):
        gone = self.linked('gone', initialized=True)
        live = self.linked('live', initialized=True)
        original = self.records()
        outside = self.root / 'external-database'
        outside.write_bytes(b'valuable data')
        shutil.rmtree(gone)
        self.prune(apply=True)
        self.assertEqual(self.records(), [r for r in original if r['worktree'] == str(live)])
        self.assertTrue(self.tmps[0].is_dir())
        self.assertTrue((self.root / 'gone-install/bin/cubrid').is_file())
        self.assertEqual(outside.read_bytes(), b'valuable data')

    def test_busy_allocation_retained_while_other_stale_metadata_pruned(self):
        busy = self.linked('busy', initialized=True)
        safe = self.linked('safe')
        record = self.records()[0]
        shutil.rmtree(busy)
        shutil.rmtree(safe)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', record['master_port']))
            listener.listen()
            self.prune(apply=True, code=1)
            self.assertEqual(self.records(), [record])
            worktrees = self.git('worktree', 'list', '--porcelain')
            self.assertIn(str(busy), worktrees)
            self.assertNotIn(str(safe), worktrees)

    def test_locked_and_dangling_symlink_worktrees_retained(self):
        locked = self.linked('locked')
        symlink = self.linked('symlink')
        self.git('worktree', 'lock', str(locked))
        shutil.rmtree(locked)
        shutil.rmtree(symlink)
        symlink.symlink_to(self.root / 'absent')
        result = self.prune(apply=True, code=1)
        self.assertIn('locked', result.stdout)
        self.assertIn('symlink', result.stdout)
        self.assertIn(str(locked), self.git('worktree', 'list', '--porcelain'))
        self.assertTrue(symlink.is_symlink())

    def test_live_process_prevents_release_after_worktree_deletion(self):
        tree = self.linked('owner', initialized=True)
        record = self.records()[0]
        proc = subprocess.Popen(['sleep', '30'], env=dict(os.environ, CUBRID=record['install']))
        try:
            shutil.rmtree(tree)
            self.assertIn('live', self.prune(apply=True, code=1).stdout)
            self.assertEqual(self.records(), [record])
            self.assertIn(str(tree), self.git('worktree', 'list', '--porcelain'))
        finally:
            proc.terminate()
            proc.wait()

    def test_exited_unreaped_process_does_not_block_idle_allocation(self):
        tree = self.linked('zombie', initialized=True)
        shutil.rmtree(tree)
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        try:
            os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT)
            self.prune(apply=True)
            self.assertEqual(self.records(), [])
        finally:
            os.waitpid(pid, 0)

    def test_git_failure_restores_allocation_before_unlock(self):
        import argparse
        import sys
        from unittest.mock import patch
        sys.path.insert(0, str(CLI.parents[1]))
        from cubrid_workenv.prune import prune, git
        tree = self.linked('refused', initialized=True)
        before = self.records()
        shutil.rmtree(tree)
        def refuse_remove(root, *args):
            if args[:2] == ('worktree', 'remove'):
                raise ValueError('simulated Git refusal')
            return git(root, *args)
        with patch('cubrid_workenv.prune.git', side_effect=refuse_remove):
            with self.assertRaisesRegex(ValueError, 'retained'):
                prune(argparse.Namespace(worktree=self.repo, state_home=self.home, apply=True))
        self.assertEqual(self.records(), before)
        self.assertIn(str(tree), self.git('worktree', 'list', '--porcelain'))

    def test_reset_identity_can_be_pruned_after_deletion(self):
        tree = self.linked('reset', initialized=True)
        p = subprocess.run([str(CLI), 'reset', '--worktree', str(tree), '--apply'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        shutil.rmtree(tree)
        self.prune(apply=True)
        self.assertEqual(self.records(), [])
        self.assertTrue(self.tmps[0].is_dir())


if __name__ == '__main__':
    unittest.main()
