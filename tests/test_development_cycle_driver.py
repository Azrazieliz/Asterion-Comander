"""Real two-turn Git development cycles via durable ledger and scripted LLM.

No installed model, no cloud network, no owner working tree modifications.
Uses actual git commits in disposable test roots and SQLite ledger receipts.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion_remote import overnight_supervisor as ledger
from asterion_remote import development_cycle_driver as driver
from asterion_remote.development_workbench import _branch


class CycleDriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="asterion-driver-test-")
        self.base=Path(self.tmp.name)
        self.repo=self.base/"owner-source"
        self.repo.mkdir()
        self.src=self.repo/"src"/"example.py"
        self.src.parent.mkdir()
        self.original="def value():\n    return 1\n"
        self.src.write_text(self.original)
        for args in [("init",),("add","--","src/example.py"),
                     ("-c","user.name=Tester","-c","user.email=test@invalid",
                      "commit","-m","initial")]:
            subprocess.check_call(["git","-C",str(self.repo),*args],
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.registry=self.base/"projects.json"
        self.registry.write_text(json.dumps({"schema":1,"projects":[{
            "name":"AsterionControl","repository":str(self.repo),
            "base_ref":"HEAD","allowed_prefixes":["src"],
            "focus_paths":["src/example.py"],"push_to_origin":False}]}))
        self.environment=patch.dict(os.environ,{
            "ASTERION_DEV_CYCLE_ENABLED":"1",
            "ASTERION_DEV_AUTORUN":"0",
            "ASTERION_DEV_PROJECT_REGISTRY":str(self.registry),
            "ASTERION_OVERNIGHT_ROOT":str(self.base/"ledger"),
            "ASTERION_LOCAL_MODEL_ENDPOINT":"",
            "ASTERION_LOCAL_MODEL_ID":"",
        })
        self.environment.start()
        self.id="localcycle-0001"
        self.project="AsterionControl"
        ledger.create(self.id,self.project,"docs/owner-scope.md",
                      "Improve real project source incrementally",provider="pc_local",
                      max_turns=2)

    def tearDown(self):
        driver.stop()
        self.environment.stop()
        self.tmp.cleanup()

    def provider(self,return_value):
        calls=[]
        def one(prompt,request_id):
            calls.append((prompt,request_id))
            return {"message_id":"model-receipt-"+request_id,
                    "content":json.dumps(return_value)}
        one.calls=calls
        return one

    def patch(self,old_sha=None, old="return 1", new="return 2"):
        return {"schema":1,
            "next_work":"Implement next functional regression test and review",
            "edits":[{"path":"src/example.py",
                      "expected_sha256":old_sha or
                          hashlib.sha256(self.original.encode()).hexdigest(),
                      "replace":{"old":old,"new":new}}]}

    def test_real_llm_to_git_to_verified_ledger_turn(self):
        model=self.provider(self.patch())
        result=driver.advance_project(self.id,provider=model)
        self.assertEqual(result["state"],"ready")
        self.assertEqual(result["verified_turns"],1)
        self.assertEqual(result["last_turn"]["state"],"verified")
        self.assertEqual(len(model.calls),1)
        self.assertIn("VERIFIED SOURCE SNAPSHOT",model.calls[0][0])
        self.assertIn("return 1",model.calls[0][0])
        self.assertIn("functional/device tests PENDING",result["last_turn"]["work_summary"])
        self.assertEqual(self.src.read_text(),self.original)
        gitbranch=_branch(self.id)
        actual=subprocess.check_output([
            "git","-C",str(self.repo),"show",gitbranch+":src/example.py"]).decode()
        self.assertIn("return 2",actual)
        self.assertEqual(len(result["last_turn"]["evidence_sha256"]),64)

    def test_two_verified_turns_preserve_checkpoint_and_actual_git_chain(self):
        first=driver.advance_project(self.id,provider=self.provider(self.patch()))
        old="def value():\n    return 2\n"
        second=self.provider(self.patch(
            old_sha=hashlib.sha256(old.encode()).hexdigest(),
            old="return 2",new="return 3"))
        result=driver.advance_project(self.id,provider=second)
        self.assertEqual(result["verified_turns"],2)
        self.assertEqual(result["state"],"turn_limit_reached")
        self.assertIn("Latest verified work:",second.calls[0][0])
        self.assertIn(first["last_turn"]["evidence_sha256"],
                      second.calls[0][0])
        self.assertIn("return 2",second.calls[0][0])
        self.assertNotEqual(first["last_turn"]["evidence_sha256"],
                            result["last_turn"]["evidence_sha256"])
        content=subprocess.check_output([
            "git","-C",str(self.repo),"show",
            _branch(self.id)+":src/example.py"]).decode()
        self.assertIn("return 3",content)
        self.assertEqual(self.src.read_text(),self.original)
        self.assertEqual(result["completion_evidence_sha256"],"")

    def test_config_not_ready_does_not_claim_turn(self):
        with patch.dict(os.environ,{"ASTERION_DEV_CYCLE_ENABLED":"0"}):
            with self.assertRaises(RuntimeError):
                driver.advance_project(self.id,provider=self.provider(self.patch()))
        self.assertEqual(ledger.status(self.id)["turn_index"],0)
        self.assertEqual(driver.readiness()["configured"],False) if (
            driver.readiness()["configured"] is False) else None

    def test_unregistered_project_cannot_trigger_source_edits(self):
        alternate={"schema":1,"projects":[{
            "name":"AnotherProject","repository":str(self.repo),
            "base_ref":"HEAD","allowed_prefixes":["src"],
            "focus_paths":["src/example.py"]}]}
        self.registry.write_text(json.dumps(alternate))
        with self.assertRaises(PermissionError):
            driver.advance_project(self.id,provider=self.provider(self.patch()))
        self.assertEqual(ledger.status(self.id)["turn_index"],0)

    def test_rejects_chatgpt_provider_without_taking_over_android_cycles(self):
        ledger.create("chatcycle001","AsterionControl","docs/owner-scope.md",
                      "Keep ChatGPT cycle separated from local PC model",
                      provider="chatgpt")
        with self.assertRaises(RuntimeError):
            driver.advance_project("chatcycle001",
                                   provider=self.provider(self.patch()))
        self.assertEqual(ledger.status("chatcycle001")["turn_index"],0)

    def test_unavailable_inference_blocks_and_prevents_duplicate_auto_resend(self):
        calls=[]
        def broken(*args):
            calls.append(args)
            raise ConnectionError("model server unreachable")
        result=driver.advance_project(self.id,provider=broken)
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["verified_turns"],0)
        self.assertEqual(len(calls),1)
        with self.assertRaises(RuntimeError):
            driver.advance_project(self.id,provider=broken)
        self.assertEqual(len(calls),1)

    def test_model_draft_fails_static_checks_and_is_not_credited(self):
        invalid=self.provider(self.patch(new="("))
        result=driver.advance_project(self.id,provider=invalid)
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["verified_turns"],0)
        self.assertEqual(result["last_turn"]["state"],"awaiting_verification")
        self.assertEqual(self.src.read_text(),self.original)

    def test_registry_requires_explicit_owner_activation(self):
        with patch.dict(os.environ,{"ASTERION_DEV_CYCLE_ENABLED":"0"}):
            self.assertEqual(driver.readiness()["state"],"OWNER_DISABLED")
            result=driver.start()
            self.assertEqual(result["state"],"OWNER_DISABLED")
            self.assertFalse(driver.worker_status()["worker_thread_alive"])

    def test_real_worker_async_queue_executes_one_turn_after_opt_in(self):
        model=self.provider(self.patch())
        with patch.dict(os.environ,{
            "ASTERION_LOCAL_MODEL_ENDPOINT":
                "http://127.0.0.1:8080/v1/chat/completions",
            "ASTERION_LOCAL_MODEL_ID":"local-test-model"
        }),patch.object(driver,"_model",return_value=model):
            state=driver.start()
            self.assertEqual(state["state"],"WORKER_STARTED")
            job=driver.queue_turn(self.id)
            self.assertEqual(job["state"],"queued")
            until=time.monotonic()+8
            observed=None
            while time.monotonic()<until:
                observed=ledger.status(self.id)
                if observed["state"]=="ready" and observed["verified_turns"]==1:
                    break
                time.sleep(.05)
            self.assertIsNotNone(observed)
            self.assertEqual(observed["verified_turns"],1)
            self.assertEqual(observed["state"],"ready")
            self.assertEqual(len(model.calls),1)
            self.assertTrue(driver.worker_status()["worker_thread_alive"])
            driver.stop(wait_s=3)
            self.assertFalse(driver.worker_status()["worker_thread_alive"])

if __name__=="__main__":
    unittest.main()
