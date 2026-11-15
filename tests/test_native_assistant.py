"""Actual finite AI assistant tool execution, distinct from overnight cycles.

No paid APIs, installed model or actual Android device actions are needed.
One optional PC wait-only session test uses the real native session worker,
journal and deterministic postcondition; never touches owner files.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion_remote import native_assistant as agent


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "ASTERION_ASSISTANT_ROOT":self.tmp.name,
            "ASTERION_DIAGNOSTIC_ROOT":self.tmp.name,
            "ASTERION_SKILL_STUDIO_ROOT":self.tmp.name,
        })
        self.env.start()
        self.ident="ownerrequest-00001"
        self.prompt="Check the actual Control worker health and available tasks"

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    @staticmethod
    def provider_script(*items):
        remaining=list(items)
        captured=[]
        def provider(prompt,ident):
            captured.append((prompt,ident))
            if not remaining:
                raise RuntimeError("unexpected_model_call")
            return {"content":json.dumps(remaining.pop(0),
                                          separators=(",",":")),
                    "message_id":"actual-test-model-msg"}
        provider.calls=captured
        return provider

    def test_real_host_health_then_final_is_not_project_completion(self):
        provider=self.provider_script(
            {"action":"tool","name":"host.health","arguments":{}},
            {"action":"final","message":"Local host health was observed"})
        result=agent.execute(self.prompt,self.ident,provider)
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_receipts"],1)
        self.assertEqual(result["answer"],"Local host health was observed")
        self.assertFalse(result["project_work_verified"])
        self.assertFalse(result["model_answer_verified"])
        self.assertEqual(len(provider.calls),2)
        self.assertIn("observed",provider.calls[1][0])
        self.assertTrue(provider.calls[0][1].startswith("agent-"))
        self.assertEqual(agent.status(self.ident)["state"],"answered")
        self.assertNotIn(self.prompt,str(agent.list_recent()))

    def test_duplicate_never_resubmits_inference_or_tools(self):
        provider=self.provider_script(
            {"action":"final","message":"One actual model reply"})
        first=agent.execute(self.prompt,self.ident,provider)
        second=agent.execute(self.prompt,self.ident,provider)
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertTrue(second["replayed"])
        self.assertEqual(len(provider.calls),1)
        self.assertFalse(second["replay_allowed"])

    def test_same_id_different_request_rejected(self):
        agent.execute(self.prompt,self.ident,
                      self.provider_script({"action":"final","message":"Done"}))
        with self.assertRaises(ValueError):
            agent.execute("A different request entirely",self.ident,
                self.provider_script({"action":"final","message":"Wrong"}))

    def test_unknown_and_unapproved_tool_never_run(self):
        for tool,expected in (
            ("os.run_any_shell", "ValueError"),
            ("native.session", "PermissionError"),
        ):
            with self.subTest(tool=tool):
                ident=self.ident+"-"+tool.replace(".","-")
                provider=self.provider_script(
                    {"action":"tool","name":tool,"arguments":{}},
                    {"action":"final","message":"falsely done"})
                result=agent.execute(self.prompt,ident,provider)
                self.assertEqual(result["state"],"needs_review")
                self.assertEqual(result["error_code"],expected)
                self.assertEqual(result["tool_receipts"],0)
                self.assertEqual(len(provider.calls),1)

    def test_privileged_tool_requires_separate_device_action_consent(self):
        provider=self.provider_script({
            "action":"tool","name":"native.session",
            "arguments":{"device":"pc","steps":[
                {"kind":"wait","wait_ms":40}],"timeout_s":5}
        })
        result=agent.execute(self.prompt,self.ident,provider,
                             owner_grants=frozenset({"native.session"}),
                             allow_device_actions=False)
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["error_code"],"PermissionError")
        from asterion_remote import session_journal
        self.assertEqual(session_journal.recent(),[])

    def test_real_pc_wait_session_is_started_with_durable_request(self):
        provider=self.provider_script(
            {"action":"tool","name":"native.session",
             "arguments":{"device":"pc",
                          "steps":[{"kind":"wait","wait_ms":30}],
                          "timeout_s":5}},
            {"action":"final","message":"Session submitted; verify status separately"}
        )
        result=agent.execute(
            self.prompt,self.ident,provider,
            owner_grants=frozenset({"native.session"}),
            allow_device_actions=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_receipts"],1)
        self.assertEqual(result["verified_device_sessions"],0)
        self.assertIn("Session submitted",result["answer"])
        from asterion_remote import session_journal
        until=time.monotonic()+4
        row=None
        while time.monotonic()<until:
            recent=session_journal.recent()
            row=recent[0] if recent else None
            if row and row["state"] in {"completed","failed","cancelled","timed_out"}:
                break
            time.sleep(.04)
        self.assertIsNotNone(row)
        self.assertEqual(row["state"],"completed")
        self.assertEqual(row["client_request_id"],self.ident+":0")
        self.assertFalse(row["replay_allowed"])

    def test_actual_owner_scoped_source_file_read_is_not_default(self):
        from asterion_remote import app as control_app
        source=Path(self.tmp.name)/"example.py"
        source.write_text("def alive():\\n    return 42\\n".replace(
            "\\\\n","\\n"),encoding="utf-8")
        provider=self.provider_script(
            {"action":"tool","name":"files.read_text",
             "arguments":{"path":"example.py","start_line":1,"max_lines":5}},
            {"action":"final","message":"I read the actual code"})
        with patch.object(control_app,"ROOT",Path(self.tmp.name)), patch.object(
                control_app,"EXTRA_ROOTS",[]):
            result=agent.execute(self.prompt,self.ident,provider,
                      owner_grants=frozenset({"files.read_text"}))
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_receipts"],1)
        self.assertIn("return 42",provider.calls[1][0])
        self.assertNotIn("return 42",str(agent.list_recent()))

    def test_hidden_credentials_are_not_sent_to_model(self):
        provider=self.provider_script({
            "action":"tool","name":"files.read_text",
            "arguments":{"path":".env","start_line":1}})
        result=agent.execute(self.prompt,self.ident,provider,
                      owner_grants=frozenset({"files.read_text"}))
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["error_code"],"PermissionError")
        self.assertEqual(result["tool_receipts"],0)

    def test_preapproved_skill_executes_actual_session_not_fake_done(self):
        from asterion_remote import skill_studio,session_journal
        created=skill_studio.create("sample_skill_01",
            "Wait briefly on PC without changing owner data",
            "pc",[{"kind":"wait","wait_ms":25}],timeout_s=5)
        skill_studio.approve("sample_skill_01",created["sha256"])
        provider=self.provider_script(
            {"action":"tool","name":"skills.execute",
             "arguments":{"skill_id":"sample_skill_01",
                          "sha256":created["sha256"]}},
            {"action":"final",
             "message":"Authorized skill submitted; execution status separate"})
        result=agent.execute(self.prompt,self.ident,provider,
                    owner_grants=frozenset({"skills.execute"}),
                    allow_device_actions=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["verified_device_sessions"],0)
        self.assertEqual(result["tool_receipts"],1)
        until=time.monotonic()+4
        entry=None
        while time.monotonic()<until:
            receipts=session_journal.recent()
            entry=receipts[0] if receipts else None
            if entry and entry["state"] in (
                 "completed","failed","cancelled","timed_out"):
                break
            time.sleep(.04)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["state"],"completed")
        self.assertEqual(entry["client_request_id"],self.ident+":0")
        self.assertEqual(
            skill_studio.details("sample_skill_01")["executions"],1)

    def test_model_cannot_inject_own_idempotency_key(self):
        provider=self.provider_script({
            "action":"tool","name":"native.session",
            "arguments":{"device":"pc","steps":[
                {"kind":"wait","wait_ms":30}],"timeout_s":5,
                "request_id":"arbitrary-replay-id"}
        })
        result=agent.execute(self.prompt,self.ident,provider,
            owner_grants=frozenset({"native.session"}),allow_device_actions=True)
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["error_code"],"ValueError")

    def test_tool_execution_failure_never_claims_completion(self):
        provider=self.provider_script(
            {"action":"tool","name":"sessions.status",
             "arguments":{"session_id":"missing-session-001"}},
            {"action":"final","message":"falsely complete"})
        result=agent.execute(self.prompt,self.ident,provider)
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["tool_receipts"],0)
        self.assertEqual(len(provider.calls),1)

    def test_step_budget_enforced_with_honest_incomplete_result(self):
        provider=self.provider_script({
            "action":"tool","name":"host.health","arguments":{}
        })
        result=agent.execute(self.prompt,self.ident,provider,max_steps=1)
        self.assertEqual(result["state"],"budget_exhausted")
        self.assertFalse(result["ok"])
        self.assertEqual(result["tool_receipts"],1)
        self.assertFalse(result["project_work_verified"])

    def test_non_json_model_answer_causes_review_not_execute(self):
        provider=self.provider_script()
        def malformed(*args):
            return {"content":"Please execute arbitrary scripts now."}
        result=agent.execute(self.prompt,self.ident,malformed)
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["error_code"],"JSONDecodeError")
        self.assertFalse(result["replay_allowed"])

    def test_scope_requires_explicit_frozenset_and_known_tools(self):
        for grant in ({"host.health"},frozenset({"unknown.tool"})):
            with self.assertRaises(ValueError):
                agent.execute(self.prompt,self.ident,
                    self.provider_script({"action":"final","message":"A"}),
                    owner_grants=grant)
        self.assertEqual(agent.list_recent(),[])

    def test_no_prompt_or_response_text_saved_in_sqlite(self):
        prompt="Private owner question not to persist as plaintext"
        answer="Sensitive private answer should not be stored"
        agent.execute(prompt,self.ident,
            self.provider_script({"action":"final","message":answer}))
        contents=(Path(self.tmp.name)/"requests.sqlite3").read_bytes()
        self.assertNotIn(prompt.encode(),contents)
        self.assertNotIn(answer.encode(),contents)
        self.assertEqual(agent.status(self.ident)["answer_sha256"],
                         hashlib.sha256(answer.encode()).hexdigest())


if __name__=="__main__":
    unittest.main()
