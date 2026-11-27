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
        self.assertEqual(called.call_count, 4)
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


def test_measured_resource_pressure_is_reported_without_private_mount_paths():
    gib=1024**3
    with patch("asterion_remote.diagnostic_snapshot.host_health",return_value={
        "sampled_at":12345,"memory":{"available":gib+1,"total":8*gib},
        "disks":[{"mount":"C:\\","free":gib-1,"total":120*gib},
                 {"mount":"D:\\","free":80*gib,"total":500*gib},
                 {"mount":"/private/user/folder","free":gib,"total":100*gib}],
        "token":"private-secret"}):
        result=snapshot._pc_resources()
    assert result["observed"] is True
    assert result["memory"]["pressure_band"]=="low"
    assert result["volumes"][0]["volume"]=="C:"
    assert result["volumes"][0]["pressure_band"]=="critical"
    assert result["volumes"][1]["pressure_band"]=="above_low_threshold"
    assert result["volumes"][2]["volume"]=="volume-3"
    assert len(result["findings"])==3
    assert all(f["root_cause_verified"] is False for f in result["findings"])
    assert "private" not in str(result)

def test_invalid_resource_measurement_and_unavailable_host_are_not_zero():
    assert snapshot._resource_pair(None,1024)["available"] is False
    assert snapshot._resource_pair(True,1024)["available"] is False
    assert snapshot._resource_pair(2048,1024)["available"] is False
    with patch("asterion_remote.diagnostic_snapshot.host_health",side_effect=RuntimeError("private secret")):
        result=snapshot._pc_resources()
    assert result=={"observed":False,"reason":"RuntimeError","findings":[],"root_cause_verified":False}

def test_phone_fresh_resource_and_native_transport_measurements_are_separate():
    gib=1024**3
    with patch("asterion_remote.diagnostic_snapshot.phone_bridge.load",return_value={"device":"Samsung"}), \
         patch("asterion_remote.diagnostic_snapshot.phone_bridge.request",side_effect=[
             PhoneReply({"ok":True,"memory_available":gib-1,"memory_total":12*gib,
                         "storage_available":80*gib,"storage_total":500*gib,
                         "remote_transport":{"network":"wifi","connected":True,"validated":True,
                                             "direct_mcp":{"transport":"direct_wss","connected":False}}}),
             RuntimeError("no journal"),RuntimeError("no exits")]):
        result=snapshot._phone()
    assert result["reachability_verified"] is True
    assert result["transport"]["connected"] is True
    assert result["transport"]["native_wss_connected"] is False
    assert result["resources"]["memory"]["pressure_band"]=="critical"
    assert result["resources"]["storage"]["pressure_band"]=="above_low_threshold"
    assert len(result["resources"]["findings"])==1
