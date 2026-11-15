"""One-shot incident snapshot never confuses telemetry with causal proof."""
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote import diagnostic_core as core
from asterion_remote import diagnostic_snapshot as snapshot
from asterion_remote.diagnostic_routes import router


class PhoneReply:
    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


class DiagnosticSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "ASTERION_DIAGNOSTIC_ROOT": self.temp.name,
            "ASTERION_API_TOKEN": "A" * 40,
        })
        self.env.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "A" * 40}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def test_no_pairing_does_not_claim_phone_offline(self):
        core.record("job_created", app="asterion.downloader",
                    operation_id="item17", state="queued")
        with patch("asterion_remote.diagnostic_snapshot.phone_bridge.load",
                   return_value=None):
            result = snapshot.collect(app="asterion.downloader")
        self.assertTrue(result["ok"])
        self.assertFalse(result["android"]["paired"])
        self.assertFalse(result["android"]["reachable"])
        self.assertFalse(result["root_cause_verified"])
        self.assertEqual(result["pc_instrumented_events"]["events_examined"], 1)
        self.assertFalse(result["side_effects_performed"])

    def test_private_native_evidence_is_bounded_and_no_token_leaks(self):
        def fake_request(path, method="GET", payload=None, timeout=5):
            if path == "/health":
                return PhoneReply({
                    "ok": True, "android": "17", "accessible": True, "capture": True,
                    "remote_transport": {"connected": True, "validated": True},
                    "token": "SENSITIVE-SECRET",
                })
            if path == "/diagnostics/events":
                if payload["limit"] == 1:
                    return PhoneReply({
                        "scope": "asterion_control_process_only",
                        "latest_sequence": 44, "events": [],
                    })
                return PhoneReply({
                    "scope": "asterion_control_process_only",
                    "events": [{"seq": 44, "kind": "transport_error",
                                "state": "failed", "stage": "wss",
                                "reason_code": "disconnected",
                                "private": "SENSITIVE-SECRET"}],
                })
            if path == "/diagnostics/exit-history":
                return PhoneReply({
                    "scope": "own_process_only",
                    "supported": True,
                    "exits": [{"reason_code": 4, "timestamp_ms": 1730000000,
                               "extra": "SENSITIVE-SECRET"}],
                })
            raise AssertionError(path)
        with patch("asterion_remote.diagnostic_snapshot.phone_bridge.load",
                   return_value={"device": "Samsung", "token": "SENSITIVE-SECRET"}), \
             patch("asterion_remote.diagnostic_snapshot.phone_bridge.request",
                   side_effect=fake_request) as called:
            result = snapshot.collect()
        self.assertEqual(called.call_count, 3)
        self.assertTrue(result["android"]["reachable"])
        self.assertEqual(result["android"]["own_process_journal"]["records"][0]["kind"],
                         "transport_error")
        self.assertEqual(result["android"]["own_process_exit_history"]["records"][0]["reason_code"], 4)
        self.assertNotIn("SENSITIVE-SECRET", str(result))
        self.assertFalse(result["cross_app_private_logs_accessible"])

    def test_phone_failure_retains_pc_evidence_without_false_root_cause(self):
        core.record("http_failure", app="asterion.downloader",
                    state="failed", attributes={"status_code": 403})
        with patch("asterion_remote.diagnostic_snapshot.phone_bridge.load",
                   return_value={"device": "Samsung"}), \
             patch("asterion_remote.diagnostic_snapshot.phone_bridge.request",
                   side_effect=TimeoutError("private secret")):
            result = snapshot.collect()
        self.assertFalse(result["android"]["reachable"])
        self.assertFalse(result["android"]["reachability_verified"])
        self.assertEqual(result["pc_instrumented_events"]["findings"][0]["code"],
                         "http_403")
        self.assertFalse(result["root_cause_verified"])
        self.assertNotIn("private secret", str(result))

    def test_strict_auth_and_limits(self):
        self.assertEqual(self.client.get("/api/v1/diagnostics/snapshot").status_code,
                         401)
        for query in ("limit=3001", "lookback_minutes=0", "app=invalid%20app"):
            result = self.client.get("/api/v1/diagnostics/snapshot?" + query,
                                     headers=self.headers)
            self.assertEqual(result.status_code, 422)
        result = self.client.get("/api/v1/diagnostics/snapshot?phone=false",
                                 headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["android"]["requested"])

if __name__ == "__main__":
    unittest.main()
