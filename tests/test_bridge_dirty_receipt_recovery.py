"""Regression tests for Asterion Control's dirty-receipt recovery guardrail."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion_remote import github_bridge_git as bridge


def git(root, *args):
    done=subprocess.run(['git',*args],cwd=root,text=True,capture_output=True,check=False,timeout=20)
    if done.returncode:
        raise AssertionError(f"git {args!r}: {done.stderr or done.stdout}")
    return done.stdout.strip()


class DirtyReceiptRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.bare=self.base/'origin.git'
        git(self.base,'init','--bare','--initial-branch=main',str(self.bare))
        self.publisher=self.base/'publisher'
        git(self.base,'clone',str(self.bare),str(self.publisher))
        git(self.publisher,'config','user.email','test@example.invalid')
        git(self.publisher,'config','user.name','Test publisher')
        (self.publisher/'results').mkdir()
        (self.publisher/'results'/'test-job.json').write_text(
            json.dumps({'id':'test-job','ok':True,'status':'accepted'}))
        (self.publisher/'notes.txt').write_text('unchanged')
        git(self.publisher,'add','.')
        git(self.publisher,'commit','-m','Initial accepted receipt')
        git(self.publisher,'push','-u','origin','main')
        self.worker=self.base/'worker'
        git(self.base,'clone',str(self.bare),str(self.worker))
        git(self.worker,'config','user.name','Control')
        git(self.worker,'config','user.email','control@example.invalid')

    def test_dirty_receipt_recovered_and_published_without_losing_new_commands(self):
        receipt=self.worker/'results'/'test-job.json'
        complete={'id':'test-job','ok':True,'status':'complete','result':{'exit_code':0}}
        receipt.write_text(json.dumps(complete))
        # Simulate another writer pushing work while the local result is dirty.
        (self.publisher/'commands'/'active').mkdir(parents=True)
        (self.publisher/'commands'/'active'/'new-job.json').write_text('{"id":"new-job","op":"pc_status","params":{}}')
        git(self.publisher,'add','.')
        git(self.publisher,'commit','-m','Other writer command')
        git(self.publisher,'push')
        with patch.object(bridge,'ROOT',self.worker):
            bridge.sync_remote()
        self.assertEqual(json.loads(receipt.read_text()),complete)
        self.assertEqual(git(self.worker,'status','--porcelain'),'')
        self.assertTrue((self.worker/'commands'/'active'/'new-job.json').exists())
        self.assertFalse((self.base/'receipt-recovery').exists())
        git(self.publisher,'pull','--ff-only')
        self.assertEqual(json.loads((self.publisher/'results'/'test-job.json').read_text()),complete)

    def test_recover_unpublished_single_tracked_modification_keeps_status_columns(self):
        """A lone ' M results/job.json' must not lose its first path character.

        Regresses the porcelain .strip() bug which stranded finished receipts
        when an otherwise healthy worker tried to publish after an outage.
        """
        receipt=self.worker/'results'/'test-job.json'
        complete={'id':'test-job','ok':True,'status':'complete',
                  'result':{'exit_code':0}}
        receipt.write_text(json.dumps(complete),encoding='utf8')
        captured=[]
        with patch.object(bridge,'ROOT',self.worker), \
             patch.object(bridge,'publish',side_effect=lambda paths: captured.extend(paths)):
            count=bridge.recover_unpublished()
        self.assertEqual(count,1)
        self.assertEqual(captured,[Path('results/test-job.json')])
        self.assertEqual(json.loads(receipt.read_text('utf8')),complete)

    def test_untracked_incomplete_journal_is_preserved(self):
        pending=self.worker/'results'/'test-job.pending'
        pending.write_text('partial durable journal')
        with patch.object(bridge,'ROOT',self.worker):
            bridge.sync_remote()
        self.assertEqual(pending.read_text(),'partial durable journal')

    def test_unrelated_tracked_changes_remain_untouched(self):
        note=self.worker/'notes.txt'
        note.write_text('owner change')
        with patch.object(bridge,'ROOT',self.worker):
            with self.assertRaisesRegex(RuntimeError,'Unsafe local bridge change'):
                bridge.sync_remote()
        self.assertEqual(note.read_text(),'owner change')

    def test_invalid_result_is_not_reset_or_published(self):
        receipt=self.worker/'results'/'test-job.json'
        receipt.write_text('invalid-json')
        with patch.object(bridge,'ROOT',self.worker):
            with self.assertRaisesRegex(RuntimeError,'Invalid local result'):
                bridge.sync_remote()
        self.assertEqual(receipt.read_text(),'invalid-json')
        self.assertFalse((self.base/'receipt-recovery').exists())


    def test_rebase_works_without_global_or_local_git_identity(self):
        """A Windows service has no configured Git user but can rebase receipts."""
        import os
        receipt=self.worker/'results'/'test-job.json'
        receipt.write_text(json.dumps({'id':'test-job','ok':True,
            'status':'complete'}),encoding='utf8')
        git(self.worker,'add','results')
        git(self.worker,'commit','-m','Committed local receipt')
        git(self.worker,'config','--unset','user.name')
        git(self.worker,'config','--unset','user.email')
        (self.publisher/'commands'/'active').mkdir(parents=True)
        (self.publisher/'commands'/'active'/'remote-job.json').write_text(
            json.dumps({'id':'remote-job','op':'pc_status','params':{}}),encoding='utf8')
        git(self.publisher,'add','commands')
        git(self.publisher,'commit','-m','Concurrent Control command')
        git(self.publisher,'push')
        clean_global=self.base/'empty-global-git-config'
        clean_global.write_text('',encoding='utf8')
        with (patch.dict(os.environ,{'GIT_CONFIG_GLOBAL':str(clean_global),
                                    'GIT_CONFIG_NOSYSTEM':'1'}),
              patch.object(bridge,'ROOT',self.worker)):
            bridge.sync_remote()
        self.assertEqual(git(self.worker,'status','--porcelain'),'')
        self.assertTrue((self.worker/'commands'/'active'/'remote-job.json').exists())
        self.assertEqual(git(self.worker,'rev-list','--count','origin/main..HEAD'),'0')

    def test_interrupted_conflicting_rebase_recovers_commits_without_replaying(self):
        """A crashed Git rebase must not starve all subsequent Control commands."""
        receipt=self.worker/'results'/'test-job.json'
        receipt.write_text(json.dumps({'id':'test-job','ok':True,
            'status':'complete','result':{'exit_code':0}}),encoding='utf8')
        (self.worker/'results'/'worker-only.json').write_text(
            json.dumps({'id':'worker-only','ok':True,'status':'complete'}),encoding='utf8')
        git(self.worker,'add','results')
        git(self.worker,'commit','-m','Local durable Control receipts')
        original=git(self.worker,'rev-parse','HEAD')
        receipt_remote=self.publisher/'results'/'test-job.json'
        receipt_remote.write_text(json.dumps({'id':'test-job','ok':False,
            'status':'error','error':'already published'}),encoding='utf8')
        git(self.publisher,'add','results')
        git(self.publisher,'commit','-m','Competing receipt publication')
        git(self.publisher,'push')
        git(self.worker,'fetch','origin','main')
        attempt=subprocess.run(['git','rebase','origin/main'],cwd=self.worker,
            text=True,capture_output=True,check=False,timeout=20)
        self.assertNotEqual(attempt.returncode,0)
        self.assertTrue((self.worker/'.git'/'rebase-merge').exists())
        with patch.object(bridge,'ROOT',self.worker):
            bridge.sync_remote()
            bridge.sync_remote()
        self.assertFalse((self.worker/'.git'/'rebase-merge').exists())
        self.assertEqual(git(self.worker,'status','--porcelain'),'')
        self.assertEqual(git(self.worker,'rev-parse',
            'refs/asterion-recovery/aborted-'+original[:16]),original)
        self.assertEqual(json.loads(receipt.read_text('utf8'))['status'],'error')
        self.assertTrue((self.worker/'results'/'worker-only.json').exists())
        git(self.publisher,'pull','--ff-only')
        self.assertTrue((self.publisher/'results'/'worker-only.json').exists())
        self.assertEqual(json.loads(receipt_remote.read_text('utf8'))['status'],'error')


    def test_publish_with_concurrent_command_uses_safe_convergence(self):
        """Publishing a receipt must never start git rebase-merge."""
        result=self.worker/'results'/'fresh-local-result.json'
        result.write_text(json.dumps({'id':'fresh-local-result',
            'status':'complete','ok':True}),encoding='utf8')
        (self.publisher/'commands'/'active').mkdir(parents=True)
        (self.publisher/'commands'/'active'/'another-project.json').write_text(
            json.dumps({'id':'another-project','op':'pc_status','params':{}}),encoding='utf8')
        git(self.publisher,'add','commands')
        git(self.publisher,'commit','-m','Concurrent project command')
        git(self.publisher,'push')
        with patch.object(bridge,'ROOT',self.worker):
            bridge.publish([Path('results/fresh-local-result.json')])
        self.assertFalse((self.worker/'.git'/'rebase-merge').exists())
        self.assertEqual(git(self.worker,'status','--porcelain'),'')
        git(self.publisher,'pull','--ff-only')
        self.assertTrue((self.publisher/'results'/'fresh-local-result.json').exists())
        self.assertTrue((self.publisher/'commands'/'active'/'another-project.json').exists())

    def test_publish_competing_terminal_receipt_preserves_original_without_replay(self):
        """Overlapping command receipts must not hang publishing or replay jobs."""
        local=self.worker/'results'/'test-job.json'
        local.write_text(json.dumps({'id':'test-job','status':'complete',
            'ok':True,'result':{'exit_code':0}}),encoding='utf8')
        original=local.read_bytes()
        remote=self.publisher/'results'/'test-job.json'
        remote.write_text(json.dumps({'id':'test-job','status':'error',
            'ok':False,'error':'previously published terminal state'}),encoding='utf8')
        git(self.publisher,'add','results')
        git(self.publisher,'commit','-m','Concurrent final receipt')
        git(self.publisher,'push')
        with patch.object(bridge,'ROOT',self.worker):
            bridge.publish([Path('results/test-job.json')])
        self.assertFalse((self.worker/'.git'/'rebase-merge').exists())
        self.assertEqual(json.loads(local.read_text())['status'],'error')
        refs=git(self.worker,'for-each-ref','--format=%(refname)','refs/asterion-recovery/unpublished-*').splitlines()
        self.assertTrue(any(subprocess.run(['git','show',ref+':results/test-job.json'],
            cwd=self.worker,check=True,capture_output=True).stdout==original for ref in refs))
        self.assertFalse((self.base/'receipt-recovery').exists())
        self.assertEqual(git(self.worker,'status','--porcelain'),'')

    def test_normal_publish_is_fast_forward_without_recovery_copy(self):
        result=self.worker/'results'/'ordinary-receipt.json'
        result.write_text(json.dumps({'id':'ordinary-receipt','status':'complete','ok':True}))
        with patch.object(bridge,'ROOT',self.worker), patch.object(
            bridge,'_compact_unpublished_receipts',side_effect=AssertionError('unexpected compaction')):
            bridge.publish([Path('results/ordinary-receipt.json')])
        self.assertFalse((self.base/'receipt-recovery').exists())
        git(self.publisher,'pull','--ff-only')
        self.assertTrue((self.publisher/'results'/'ordinary-receipt.json').is_file())

    def test_failed_tree_creation_leaves_original_receipts_and_head_intact(self):
        receipt=self.worker/'results'/'test-job.json'
        receipt.write_text(json.dumps({'id':'test-job','status':'complete','ok':True}))
        git(self.worker,'add','results')
        git(self.worker,'commit','-m','Local result')
        old=git(self.worker,'rev-parse','HEAD')
        (self.publisher/'notes.txt').write_text('remote update')
        git(self.publisher,'add','notes.txt')
        git(self.publisher,'commit','-m','Concurrent writer')
        git(self.publisher,'push')
        actual=bridge.git
        def fail_write(*args,**kwargs):
            if args[0]=='write-tree':raise RuntimeError('simulated interrupted tree creation')
            return actual(*args,**kwargs)
        with patch.object(bridge,'ROOT',self.worker):
            with patch.object(bridge,'git',side_effect=fail_write):
                with self.assertRaisesRegex(RuntimeError,'simulated interrupted'):
                    bridge.sync_remote()
            self.assertEqual(git(self.worker,'rev-parse','HEAD'),old)
            self.assertEqual(json.loads(receipt.read_text())['status'],'complete')
            bridge.sync_remote()
        self.assertFalse((self.worker/'.git'/'asterion-reconcile-index').exists())
        self.assertFalse((self.base/'receipt-recovery').exists())
        self.assertEqual(git(self.worker,'status','--porcelain'),'')


if __name__=='__main__':
    unittest.main()
