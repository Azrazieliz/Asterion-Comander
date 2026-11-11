"""Fast, offline acceptance checks for the optional PC Responses worker.
Never invokes the OpenAI API or touches the owner's real repositories.
"""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE=Path(__file__).with_name("opt_in_screen_off_worker.py")
spec=importlib.util.spec_from_file_location("asterion_worker",MODULE)
worker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

class ScreenOffWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"source"
        self.root.mkdir()
        def git(*args):
            subprocess.run(["git",*args],cwd=self.root,check=True,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        git("init","-b","work/test")
        (self.root/"README.md").write_text("owner project",encoding="utf-8")
        git("add","README.md")
        git("-c","user.name=test","-c","user.email=test@example.invalid",
            "commit","-m","initial")
    def test_stays_in_work_branch(self):
        ws=worker.Workspace(self.root,write=False,push=False)
        self.assertEqual(ws.branch,"work/test")
        self.assertIn("README.md",ws.call("repo_list",{"subdir":""})["paths"])
        self.assertEqual(ws.call("repo_read",{"path":"README.md"})["content"],"owner project")
    def test_no_path_escape_or_private_key(self):
        for path in ("../outside",".git/config","keys/private.pem","build/run.jar",".env"):
            with self.assertRaises(ValueError):
                worker.safe_path(self.root,path,new=True)
    def test_write_needs_explicit_flag(self):
        ws=worker.Workspace(self.root,write=False,push=False)
        self.assertFalse(ws.call("repo_write",{"path":"README.md","content":"changed"})["ok"])
        self.assertEqual((self.root/"README.md").read_text(),"owner project")
    def test_work_branch_write_commit_is_scoped(self):
        ws=worker.Workspace(self.root,write=True,push=False)
        written=ws.call("repo_write",{"path":"docs/test.md","content":"verified"})
        self.assertTrue(written["ok"])
        receipt=ws.call("repo_commit",{"message":"Test controlled worker commit"})
        self.assertTrue(receipt["ok"],receipt)
        self.assertEqual((self.root/"docs/test.md").read_text(),"verified")
        self.assertEqual(ws.call("repo_status",{})["branch"],"work/test")
        self.assertNotIn("repo_push",[x["name"] for x in worker.definitions(True,False)])
    def test_dirty_branch_refused(self):
        (self.root/"README.md").write_text("owner edits",encoding="utf-8")
        with self.assertRaises(ValueError):
            worker.Workspace(self.root,write=True,push=False)

if __name__=="__main__":
    unittest.main()
