"""Durable diagnostic journal validation without a live phone."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion_remote import diagnostic_core as diag


class DiagnosticJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"ASTERION_DIAGNOSTIC_ROOT": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_event_is_persisted_with_structured_identifier(self):
        x = diag.record("job_started", app="asterion.downloader", trace_id="trace1",
                        operation_id="job1", state="running",
                        attributes={"worker_id":"worker-1","bytes_received":1024})
        self.assertTrue(x["ok"])
        self.assertFalse(x["incident"])
        data = diag.events(trace_id="trace1")
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["attributes"]["bytes_received"],1024)
        self.assertEqual(data["next_sequence"],x["sequence"])
        self.assertEqual(diag.health()["event_count"],1)
        self.assertTrue(Path(self.tmp.name,"events.sqlite3").exists())

    def test_secrets_are_not_recorded(self):
        diag.record("http_failure", severity="error", state="failed",
                    attributes={"token":"really-secret","cookie":"session-data",
                                "headers":{"Authorization":"secret"},
                                "url":"https://example.org/video?auth=abc",
                                "status_code":403,"reason":"authorization: supersecret"})
        entries = diag.events()["events"]
        self.assertEqual(len(entries),1)
        attrs = entries[0]["attributes"]
        self.assertNotIn("token",attrs)
        self.assertNotIn("cookie",attrs)
        self.assertNotIn("url",attrs)
        self.assertNotIn("headers",attrs)
        self.assertEqual(attrs["status_code"],403)
        self.assertNotIn("supersecret",str(attrs))
        self.assertEqual(len(diag.incidents()["incidents"]),1)

    def test_same_failure_is_grouped_into_one_incident(self):
        for i in range(5):
            diag.record("transport_error", app="asterion.control",component="phone_link",
                        severity="error",state="failed",trace_id=f"trace{i}",
                        attributes={"error_class":"HandshakeRejected","stage":"wss_upgrade"})
        rows = diag.incidents()["incidents"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["count"],5)
        self.assertEqual(diag.health()["event_count"],5)

    def test_application_and_trace_filters(self):
        diag.record("job_running",app="asterion.download",trace_id="a")
        first = diag.record("job_failed",app="asterion.art",trace_id="b")
        self.assertEqual(len(diag.events(app="asterion.download")["events"]),1)
        self.assertEqual(len(diag.events(trace_id="b")["events"]),1)
        self.assertEqual(len(diag.events(since=first["sequence"])["events"]),0)

    def test_concurrent_event_records_are_not_lost(self):
        threads = [threading.Thread(target=lambda: [
            diag.record("tick",app="asterion.control",attributes={"elapsed_ms":i})
            for i in range(20)]) for _ in range(6)]
        for t in threads:t.start()
        for t in threads:t.join(timeout=12)
        self.assertTrue(all(not t.is_alive() for t in threads))
        ticks = [entry for entry in diag.events(limit=500)["events"]
                 if entry["kind"] == "tick"]
        self.assertEqual(len(ticks),120)

    def test_reject_invalid_filters(self):
        with self.assertRaises(ValueError):diag.events(limit=1000)
        with self.assertRaises(ValueError):diag.incidents(limit=-1)


if __name__=="__main__":
    unittest.main()
