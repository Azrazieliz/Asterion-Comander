"""Non-APK acceptance for genuine provider-neutral development cycles.

Tests use an ephemeral SQLite database and loopback fake inference only.
No Android/Windows production worker, paid APIs, deployment or real source edits.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from asterion_remote import overnight_supervisor as engine
from asterion_remote.local_model_provider import LocalModelConfig, LocalModelProvider

EVIDENCE = hashlib.sha256(b"real-test-receipt-placeholder-only").hexdigest()


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ, {"ASTERION_OVERNIGHT_ROOT": self.temp.name}
        )
        self.env.start()
        self.cycle_id = "sourceproject01"

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def create(self, **kwargs):
        return engine.create(
            self.cycle_id, "AsterionControl", "docs/V4-requirements.md",
            "Implement approved independent cycle work with source and tests",
            **kwargs,
        )

    def verified(self, *, next_work="Continue to implement repository tests",
                 done=False, accepted=False):
        return {
            "evidence_sha256": EVIDENCE,
            "work_summary": "Source changes executed and acceptance test receipt checked",
            "next_work": next_work,
            "done": done,
            "acceptance_verified": accepted,
        }

    def provider(self, prompt, ident):
        self.assertIn("CONTINUOUS PROJECT DEVELOPMENT TURN", prompt)
        self.assertIn(ident, prompt)
        return {"message_id": "local-response-123456", "content":
                "Plan and tool call proposal with verified receipt to be checked"}

    def executor(self, response, cycle, request_id):
        self.assertIn("Plan", response)
        self.assertEqual(cycle, self.cycle_id)
        self.assertIn("-turn-", request_id)
        return self.verified()

    def test_create_is_not_a_running_cycle_or_normal_action(self):
        row = self.create()
        self.assertEqual(row["state"], "ready")
        self.assertTrue(row["is_development_cycle"])
        self.assertFalse(row["is_normal_action"])
        self.assertEqual(row["verified_turns"], 0)
        self.assertFalse(row["automatic_progress_verified"])
        with self.assertRaises(Exception):
            self.create()

    def test_claim_written_before_dispatch_and_not_replayed(self):
        self.create()
        turn = engine.claim(self.cycle_id)
        self.assertEqual(turn["request_id"], self.cycle_id+"-turn-1")
        self.assertEqual(engine.status(self.cycle_id)["state"],
                         "dispatch_uncertain")
        with self.assertRaises(RuntimeError):
            engine.claim(self.cycle_id)
        self.assertFalse(turn["replay_allowed"])

    def test_distinct_provider_response_and_work_receipt(self):
        self.create()
        turn = engine.claim(self.cycle_id)
        result = engine.response(self.cycle_id, turn["request_id"],
                                 provider_receipt="provider-reply-001",
                                 content="text only, no verified work yet")
        self.assertFalse(result["project_work_verified"])
        self.assertEqual(engine.status(self.cycle_id)["verified_turns"], 0)
        receipt = engine.verify(self.cycle_id, turn["request_id"],
                                **self.verified())
        self.assertEqual(receipt["state"], "ready")
        self.assertEqual(receipt["verified_turns"], 1)
        self.assertTrue(receipt["project_work_verified"])
        with self.assertRaises(RuntimeError):
            engine.response(self.cycle_id, turn["request_id"],
                            provider_receipt="another-provider-reply",
                            content="duplicate")

    def test_two_turns_carry_actual_verified_evidence(self):
        self.create()
        first = engine.advance_once(
            self.cycle_id, self.provider, self.executor)
        self.assertEqual(first["verified_turns"], 1)
        second = engine.claim(self.cycle_id)
        self.assertIn(EVIDENCE, second["prompt"])
        self.assertIn("Source changes executed", second["prompt"])
        self.assertIn("Continue to implement repository tests",second["prompt"])
        self.assertNotIn("new ChatGPT conversation",second["prompt"])

    def test_unverified_response_cannot_trigger_another_turn(self):
        self.create()
        first = engine.advance_once(self.cycle_id, self.provider)
        self.assertEqual(first["state"], "awaiting_verification")
        self.assertEqual(first["verified_turns"], 0)
        with self.assertRaises(RuntimeError):
            engine.claim(self.cycle_id)

    def test_provider_error_stops_without_auto_retry(self):
        self.create()
        calls = []
        def broken(prompt, ident):
            calls.append(ident)
            raise ConnectionError("connection disappeared after uncertain send")
        result = engine.advance_once(self.cycle_id, broken,self.executor)
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["last_error_code"], "ConnectionError")
        self.assertEqual(len(calls), 1)
        with self.assertRaises(RuntimeError):
            engine.advance_once(self.cycle_id, broken,self.executor)
        self.assertEqual(len(calls), 1)

    def test_executor_error_cannot_fake_verified_work(self):
        self.create()
        def broken_executor(*args):
            raise IOError("test runner disappeared")
        result = engine.advance_once(self.cycle_id, self.provider,
                                     broken_executor)
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["verified_turns"], 0)
        self.assertEqual(result["last_turn"]["state"],"awaiting_verification")

    def test_invalid_verification_rejected(self):
        self.create()
        turn=engine.claim(self.cycle_id)
        engine.response(self.cycle_id,turn["request_id"],
                        provider_receipt="response-verified-on-screen",
                        content="not yet verified")
        with self.assertRaises(ValueError):
            engine.verify(self.cycle_id,turn["request_id"],
                          evidence_sha256="not-a-sha",
                          work_summary="Some task happened",
                          next_work="Continue")
        with self.assertRaises(ValueError):
            engine.verify(self.cycle_id,turn["request_id"],
                          **self.verified(done=True,accepted=False))
        self.assertEqual(engine.status(self.cycle_id)["verified_turns"],0)

    def test_scope_done_requires_independent_acceptance(self):
        self.create()
        def verified_done(*args):
            return self.verified(next_work="Scope verified complete",
                                 done=True,accepted=True)
        done = engine.advance_once(self.cycle_id,self.provider,verified_done)
        self.assertEqual(done["state"],"finished")
        self.assertTrue(done["scope_completed"])
        self.assertEqual(done["completion_evidence_sha256"],EVIDENCE)
        with self.assertRaises(RuntimeError):
            engine.claim(self.cycle_id)

    def test_explicit_turn_limit_not_mislabeled_completion(self):
        self.create(max_turns=1)
        state=engine.advance_once(self.cycle_id,self.provider,self.executor)
        self.assertEqual(state["state"],"turn_limit_reached")
        self.assertFalse(state["scope_completed"])
        self.assertTrue(state["turn_limit_reached"])
        self.assertEqual(state["completion_evidence_sha256"],"")

    def test_pause_resume_and_stop(self):
        self.create()
        self.assertEqual(engine.pause(self.cycle_id)["state"],"paused")
        with self.assertRaises(RuntimeError):
            engine.claim(self.cycle_id)
        self.assertEqual(engine.resume(self.cycle_id)["state"],"ready")
        self.assertEqual(engine.stop(self.cycle_id)["state"],"stopped")
        with self.assertRaises(RuntimeError):
            engine.claim(self.cycle_id)

    def test_pause_requested_during_pending_turn_applies_after_verification(self):
        self.create()
        claimed=engine.claim(self.cycle_id)
        parked=engine.pause(self.cycle_id)
        self.assertTrue(parked["pause_requested"])
        self.assertEqual(parked["state"],"dispatch_uncertain")
        engine.response(self.cycle_id,claimed["request_id"],
                        provider_receipt="actual-provider-message-1",
                        content="A confirmed response")
        parked=engine.verify(self.cycle_id,claimed["request_id"],
                             **self.verified())
        self.assertEqual(parked["state"],"paused")
        with self.assertRaises(RuntimeError):
            engine.claim(self.cycle_id)
        self.assertEqual(engine.resume(self.cycle_id)["state"],"ready")
        self.assertEqual(engine.claim(self.cycle_id)["turn_index"],2)

    def test_stop_requested_during_pending_turn_preserves_receipts(self):
        self.create()
        claimed=engine.claim(self.cycle_id)
        state=engine.stop(self.cycle_id)
        self.assertTrue(state["stop_requested"])
        self.assertEqual(state["state"],"dispatch_uncertain")
        engine.response(self.cycle_id,claimed["request_id"],
                        provider_receipt="actual-provider-message-2",
                        content="A confirmed response")
        state=engine.verify(self.cycle_id,claimed["request_id"],
                            **self.verified())
        self.assertEqual(state["state"],"stopped")
        self.assertFalse(state["scope_completed"])
        self.assertEqual(state["verified_turns"],1)
        with self.assertRaises(RuntimeError):
            engine.claim(self.cycle_id)

    def test_multiple_threads_cannot_claim_same_turn(self):
        self.create()
        with ThreadPoolExecutor(max_workers=8) as pool:
            pending = [pool.submit(engine.claim, self.cycle_id)
                       for _ in range(8)]
        successes = [p.result() for p in pending if p.exception() is None]
        self.assertEqual(len(successes), 1)
        self.assertEqual(engine.status(self.cycle_id)["turn_index"],1)

    def test_bounded_batch_runs_real_callbacks_not_elapsed_timer(self):
        self.create()
        calls = []
        def worker(*args):
            calls.append(args[2])
            return self.verified()
        state = engine.advance_until_blocked(
            self.cycle_id,self.provider,worker,max_turns_per_call=3)
        self.assertEqual(state["verified_turns"],3)
        self.assertEqual(state["state"],"ready")
        self.assertEqual(len(calls),3)
        with self.assertRaises(ValueError):
            engine.advance_until_blocked(self.cycle_id,self.provider,worker,
                                         max_turns_per_call=10000)

    def test_no_sensitive_objective_leaks_into_status(self):
        self.create()
        serialized = json.dumps(engine.status(self.cycle_id))
        self.assertNotIn("Implement approved independent cycle work",serialized)
        self.assertEqual(engine.recent()[0]["cycle_id"],self.cycle_id)

    def test_durable_receipt_survives_new_connection(self):
        self.create()
        engine.advance_once(self.cycle_id,self.provider,self.executor)
        # Fresh SQLite connection instead of in-memory global session.
        self.assertEqual(engine.status(self.cycle_id)["verified_turns"],1)
        self.assertEqual(len(engine.recent()),1)


class ModelAdapterTests(unittest.TestCase):
    def test_refuses_external_or_credential_urls(self):
        for url in [
            "https://api.example.com/v1/chat/completions",
            "http://google.com:8080/v1/chat/completions",
            "http://127.0.0.1:8080/other",
            "http://user:pass@127.0.0.1:8080/v1/chat/completions",
            "http://127.0.0.1:8080/v1/chat/completions?paid=true",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                LocalModelConfig(endpoint=url)

    def test_local_model_rejects_redirect_without_contacting_external_host(self):
        # Test the installed redirect handler itself. The previous
        # server/socket test sporadically failed with Windows Winsock 10053
        # before the handler saw the HTTP 302; no external host was contacted.
        # A separate test below exercises real localhost HTTP inference.
        import urllib.error
        import urllib.request
        from asterion_remote.local_model_provider import _RefuseRedirect
        provider=LocalModelProvider(LocalModelConfig(
            endpoint="http://127.0.0.1:8080/v1/chat/completions"))
        installed=[x for x in provider.opener.handlers
                   if isinstance(x,_RefuseRedirect)]
        self.assertEqual(len(installed),1)
        request=urllib.request.Request(
            provider.config.endpoint,data=b'{"private":"prompt"}',
            method="POST")
        with self.assertRaises(urllib.error.HTTPError) as observed:
            installed[0].redirect_request(
                request,None,302,"Found",{"Location":
                "https://api.example.com/collect-private-prompt"},
                "https://api.example.com/collect-private-prompt")
        self.assertEqual(observed.exception.code,302)
        self.assertEqual(observed.exception.reason,
                         "local_inference_redirect_forbidden")
        # Neither provider.open nor urllib.urlopen was called: fail-closed
        # handler logic was exercised with zero outbound network traffic.

    def test_real_http_loopback_conversation_with_fake_model(self):
        seen={}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length=int(self.headers["Content-Length"])
                body=json.loads(self.rfile.read(length))
                seen["path"]=self.path
                seen["body"]=body
                data=json.dumps({"id":"chatcmpl-test-0001","choices":[{
                    "message":{"role":"assistant","content":"Local model result"}
                }]}).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def log_message(self,*args):
                pass

        server=HTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            endpoint=f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            provider=LocalModelProvider(LocalModelConfig(endpoint=endpoint,
                            model="test-local",timeout_s=10))
            response=provider("A valid development cycle prompt is provided.",
                              "testcycle-turn-1")
            self.assertEqual(response["content"],"Local model result")
            self.assertFalse(response["paid_cloud_used"])
            self.assertEqual(seen["path"],"/v1/chat/completions")
            self.assertEqual(seen["body"]["model"],"test-local")
            self.assertFalse(seen["body"]["stream"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
