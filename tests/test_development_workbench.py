"""A real temporary Git repository exercises AI drafts and immutable owner source."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from asterion_remote import development_workbench as dev

_GIT=shutil.which("git")


@unittest.skipUnless(_GIT,"Git CLI required for real repository integration")
class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="asterion-dev-unit-")
        self.root=Path(self.tmp.name)
        self.source=self.root/"owner-original"
        self.source.mkdir()
        self.git("init")
        self.sourcefile=self.source/"src"/"example.py"
        self.sourcefile.parent.mkdir(parents=True)
        self.original="def answer():\n    return 1\n"
        self.sourcefile.write_text(self.original)
        self.git("add","--","src/example.py")
        self.git("-c","user.name=Tester","-c","user.email=test@invalid",
                 "commit","-m","initial project")
        self.policy=dev.GitProject(
            name="AsterionControl",repository=self.source,
            base_ref="HEAD",allowed_prefixes=("src",))
        self.ident="controlcycle001"
        self.request=self.ident+"-turn-1"

    def tearDown(self):
        self.tmp.cleanup()

    def git(self,*args):
        out=subprocess.run(["git","-C",str(self.source),*args],
              stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        if out.returncode:
            raise AssertionError("Git failure: "+
                                 out.stderr.decode(errors="replace")[-500:])
        return out.stdout.decode(errors="replace").strip()

    def plan(self,new="2", expected=None, file="src/example.py",
             next_work="Run functional unit tests and inspect source quality"):
        old_sha=hashlib.sha256(self.original.encode()).hexdigest() \
            if expected is None else expected
        return json.dumps({
            "schema":1,"next_work":next_work,
            "edits":[{"path":file,"expected_sha256":old_sha,
                      "replace":{"old":"return 1","new":"return "+new}}]
        })

    def test_real_commit_readback_and_original_worktree_unchanged(self):
        original_commit=self.git("rev-parse","HEAD")
        context=dev.project_context(self.policy,self.ident,("src/example.py",))
        self.assertIn(hashlib.sha256(self.original.encode()).hexdigest(),context)
        self.assertIn("return 1",context)
        out=dev.apply_verified_draft(self.policy,self.plan(),
                                     self.ident,self.request)
        self.assertFalse(out["done"])
        self.assertTrue(out["static_checks"]["git_whitespace_integrity_checked"])
        self.assertFalse(out["static_checks"]["functional_tests_executed"])
        self.assertFalse(out["pushed_verified"])
        self.assertEqual(self.sourcefile.read_text(),self.original)
        self.assertEqual(self.git("rev-parse","HEAD"),original_commit)
        self.assertIn("return 2",self.git("show",
                             out["draft_commit"]+":src/example.py"))
        self.assertEqual(self.git("rev-parse",out["draft_branch"]),
                         out["draft_commit"])
        self.assertEqual(len(out["evidence_sha256"]),64)

    def test_multiple_real_substantive_turns_accumulate_git_changes(self):
        first=dev.apply_verified_draft(self.policy,self.plan(),
                                      self.ident,self.request)
        changed="def answer():\n    return 2\n"
        expected=hashlib.sha256(changed.encode()).hexdigest()
        second=json.dumps({
            "schema":1,
            "next_work":"Review tests and continue implementing the project",
            "edits":[{"path":"src/example.py",
                "expected_sha256":expected,
                "replace":{"old":"return 2","new":"return 3"}}]})
        context=dev.project_context(self.policy,self.ident,("src/example.py",))
        self.assertIn("return 2",context)
        out=dev.apply_verified_draft(self.policy,second,
                                  self.ident,self.ident+"-turn-2")
        self.assertNotEqual(first["draft_commit"],out["draft_commit"])
        self.assertIn("return 3",self.git("show",
                              out["draft_commit"]+":src/example.py"))
        self.assertEqual(self.sourcefile.read_text(),self.original)

    def test_refuses_unapproved_or_hidden_paths(self):
        for path in ("../README.md",".git/config","src/.env",
                     "src/../../private.py","outside/code.py"):
            with self.subTest(path=path):
                with self.assertRaises((PermissionError,ValueError)):
                    dev.apply_verified_draft(
                        self.policy,self.plan(file=path),
                        self.ident,self.request)
        self.assertEqual(self.sourcefile.read_text(),self.original)

    def test_rejects_stale_sha_without_modifying_original(self):
        with self.assertRaises(RuntimeError):
            dev.apply_verified_draft(self.policy,self.plan(expected="0"*64),
                                     self.ident,self.request)
        self.assertEqual(self.sourcefile.read_text(),self.original)

    def test_compilation_failure_blocks_commit_advancement(self):
        with self.assertRaises(SyntaxError):
            dev.apply_verified_draft(self.policy,self.plan(new="("),
                                     self.ident,self.request)
        self.assertEqual(self.sourcefile.read_text(),self.original)

    def test_existing_source_must_match_exactly_once(self):
        bad=json.dumps({
            "schema":1,"next_work":"Continue real development work",
            "edits":[{"path":"src/example.py",
                "expected_sha256":hashlib.sha256(self.original.encode()).hexdigest(),
                "replace":{"old":"not_here","new":"replacement"}}]})
        with self.assertRaises(ValueError):
            dev.apply_verified_draft(self.policy,bad,self.ident,self.request)

    def test_does_not_let_model_assert_project_finished(self):
        plan=json.loads(self.plan())
        plan["done"]=True
        with self.assertRaises(ValueError):
            dev.apply_verified_draft(self.policy,json.dumps(plan),
                                     self.ident,self.request)

    def test_add_new_source_file_under_owner_approved_directory(self):
        plan=json.dumps({"schema":1,
            "next_work":"Check new file in real test harness",
            "edits":[{"path":"src/new_module.py",
                      "expected_sha256":"",
                      "create":"def greet():\n    return 'hello'\n"}]})
        out=dev.apply_verified_draft(self.policy,plan,self.ident,self.request)
        self.assertIn("return 'hello'",self.git("show",
                       out["draft_commit"]+":src/new_module.py"))
        self.assertFalse((self.source/"src/new_module.py").exists())

    def test_noop_does_not_create_fake_commit(self):
        with self.assertRaises(ValueError):
            dev.apply_verified_draft(self.policy,self.plan(new="1"),
                                     self.ident,self.request)

    def test_invalid_json_and_duplicate_paths_fails_closed(self):
        with self.assertRaises(ValueError):
            dev.apply_verified_draft(self.policy,"not json",
                                     self.ident,self.request)
        plan=json.loads(self.plan())
        plan["edits"]*=2
        with self.assertRaises(ValueError):
            dev.apply_verified_draft(self.policy,json.dumps(plan),
                                     self.ident,self.request)

    def test_json_source_is_validated_before_commit(self):
        self.sourcefile=self.source/"src"/"data.json"
        self.sourcefile.write_text('{"ok":true}\n')
        self.git("add","--","src/data.json")
        self.git("-c","user.name=Tester","-c","user.email=test@invalid",
                 "commit","-m","add JSON input")
        plan=json.dumps({"schema":1,
          "next_work":"Continue JSON schema functional validation",
          "edits":[{"path":"src/data.json","expected_sha256":
                    hashlib.sha256(b'{"ok":true}\n').hexdigest(),
                    "replace":{"old":"true","new":"undefined"}}]})
        with self.assertRaises(json.JSONDecodeError):
            dev.apply_verified_draft(self.policy,plan,self.ident,self.request)

    def test_push_is_explicit_and_remote_commit_verified(self):
        remote=self.root/"owner-remote.git"
        subprocess.check_call(["git","init","--bare",str(remote)],
                     stdout=subprocess.DEVNULL)
        self.git("remote","add","origin",str(remote))
        enabled=replace(self.policy,push_to_origin=True)
        out=dev.apply_verified_draft(enabled,self.plan(),
                                     self.ident,self.request)
        remote_sha=subprocess.check_output([
            "git","--git-dir",str(remote),"rev-parse",
            "refs/heads/"+out["draft_branch"]]).decode().strip()
        self.assertTrue(out["pushed_verified"])
        self.assertEqual(remote_sha,out["draft_commit"])

    def test_second_turn_rejects_stale_patch(self):
        dev.apply_verified_draft(self.policy,self.plan(),
                                 self.ident,self.request)
        with self.assertRaises(RuntimeError):
            dev.apply_verified_draft(self.policy,self.plan(),
                    self.ident,self.ident+"-turn-2")

if __name__=="__main__":
    unittest.main()
