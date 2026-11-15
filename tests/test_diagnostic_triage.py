"""Evidence-only multi-app triage: historical status must not claim live truth."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote import diagnostic_analysis as analysis
from asterion_remote import diagnostic_core as core
from asterion_remote.diagnostic_routes import router


class DiagnosticTriageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "ASTERION_DIAGNOSTIC_ROOT": self.tmp.name,
            "ASTERION_API_TOKEN": "T" * 40,
        })
        self.env.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + "T" * 40}
        self.pkg = "asterion.downloader"

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_old_queued_event_requires_fresh_state_not_false_stall_verdict(self):
        receipt = core.record(
            "job_created", app=self.pkg, component="scheduler",
            state="queued", operation_id="dld101", trace_id="trace101",
            attributes={"stage": "queued", "queue_depth": 3,
                        "active_workers": 0, "worker_limit": 4})
        snapshot = analysis.inspect(
            app=self.pkg, stale_after_seconds=120,
            now_ms=int(time.time() * 1000) + 5 * 60 * 1000)
        self.assertFalse(snapshot["current_runtime_state_verified"])
        self.assertEqual(snapshot["events_examined"], 1)
        self.assertEqual(snapshot["operations"][0]["last_sequence"], receipt["sequence"])
        self.assertEqual(snapshot["operations"][0]["last_state"], "queued")
        self.assertEqual(snapshot["operations"][0]["last_reported_queue_depth"], 3)
        self.assertEqual(snapshot["needs_fresh_state"][0]["assessment"],
                         "fresh_engine_or_worker_snapshot_required")
        self.assertEqual(snapshot["findings"][0]["confidence"],
                         "historical_observation_only")
        self.assertNotIn("root_cause", str(snapshot))

    def test_terminal_completion_clears_stale_pending_warning(self):
        core.record("job_created", app=self.pkg, state="queued",
                    operation_id="dld102")
        core.record("job_completed", app=self.pkg, state="completed",
                    operation_id="dld102", attributes={"verified": True})
        snapshot = analysis.inspect(
            app=self.pkg, stale_after_seconds=30,
            now_ms=int(time.time() * 1000) + 8 * 60 * 1000)
        self.assertEqual(snapshot["operations"][0]["last_state"], "completed")
        self.assertEqual(snapshot["operations"][0]["event_count"], 2)
        self.assertFalse(snapshot["needs_fresh_state"])

    def test_403_is_symptom_only_and_secrets_are_not_reflected(self):
        core.record(
            "http_failure", app=self.pkg, component="extractor",
            severity="error", state="failed", operation_id="dl403",
            trace_id="trace403",
            attributes={"status_code": 403, "provider": "hentaibros",
                        "stage": "response", "url": "https://secret.invalid",
                        "authorization": "Bearer hidden"})
        snapshot = analysis.inspect(app=self.pkg)
        self.assertEqual(snapshot["symptom_counts"]
                         ["http_403_observed_not_root_cause"], 1)
        self.assertEqual(snapshot["findings"][0]["code"], "http_403")
        self.assertEqual(snapshot["findings"][0]["confidence"],
                         "observed_http_status_only")
        self.assertNotIn("geo_blocked", str(snapshot))
        self.assertNotIn("secret.invalid", str(snapshot))
        self.assertNotIn("Bearer hidden", str(snapshot))
        self.assertEqual(snapshot["notable_events"][0]["trace_id"], "trace403")

    def test_app_filter_isolation(self):
        core.record("worker_dead", app=self.pkg, severity="error",
                    state="failed", operation_id="jobA")
        core.record("crash", app="asterion.writer", severity="critical",
                    state="crashed", operation_id="jobB")
        snapshot = analysis.inspect(app=self.pkg)
        self.assertEqual(snapshot["observed_apps"], [self.pkg])
        self.assertEqual(len(snapshot["operations"]), 1)
        self.assertEqual(snapshot["operations"][0]["operation_id"], "jobA")
        self.assertNotIn("crash_reported", snapshot["symptom_counts"])
        all_apps = analysis.inspect()
        self.assertEqual(set(all_apps["observed_apps"]),
                         {self.pkg, "asterion.writer"})

    def test_event_window_is_bounded_and_declares_truncation(self):
        for index in range(4):
            core.record("probe", app=self.pkg, operation_id="probe" + str(index))
        snapshot = analysis.inspect(app=self.pkg, limit=2)
        self.assertEqual(snapshot["events_examined"], 2)
        self.assertTrue(snapshot["window_may_be_truncated"])
        self.assertEqual(len(snapshot["operations"]), 2)

    def test_validation_and_authentication(self):
        with self.assertRaises(ValueError):
            analysis.inspect(app="asterion.download;DROP TABLE events")
        with self.assertRaises(ValueError):
            analysis.inspect(limit=3001)
        with self.assertRaises(ValueError):
            analysis.inspect(stale_after_seconds=0)
        unauth = self.client.get("/api/v1/diagnostics/triage")
        self.assertIn(unauth.status_code, {401, 403})
        invalid = self.client.get("/api/v1/diagnostics/triage?limit=0",
                                  headers=self.headers)
        self.assertEqual(invalid.status_code, 422)
        good = self.client.get("/api/v1/diagnostics/triage?app=asterion.downloader",
                               headers=self.headers)
        self.assertEqual(good.status_code, 200)
        self.assertFalse(good.json()["current_runtime_state_verified"])

    def test_no_events_is_explicitly_empty_not_clean(self):
        result = analysis.inspect(app=self.pkg)
        self.assertEqual(result["events_examined"], 0)
        self.assertEqual(result["observed_apps"], [])
        self.assertFalse(result["current_runtime_state_verified"])
        self.assertIn("Only opted-in sanitized events",
                      result["limitations"][0])


if __name__ == "__main__":
    unittest.main()
