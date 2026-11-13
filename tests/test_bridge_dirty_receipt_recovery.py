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
        self.assertEqual(json.loads((self.base/'receipt-recovery'/next(
            (self.base/'receipt-recovery').iterdir()).name).read_text()),complete)
        git(self.publisher,'pull','--ff-only')
        self.assertEqual(json.loads((self.publisher/'results'/'test-job.json').read_text()),complete)

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


if __name__=='__main__':
    unittest.main()
