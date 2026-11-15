"""Immutable redacted Control incident exports with authenticated routing."""
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote import diagnostic_core as core
from asterion_remote.diagnostic_routes import router


class IncidentBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "ASTERION_DIAGNOSTIC_ROOT":self.tmp.name,
            "ASTERION_API_TOKEN":"I"*40,
        })
        self.env.start()
        app=FastAPI()
        app.include_router(router)
        self.client=TestClient(app)
        self.headers={"Authorization":"Bearer "+"I"*40}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_captures_redacted_precursor_and_immutable_digest(self):
        core.record("session_created",trace_id="trace123",
                    app="asterion.control",attributes={"stage":"started"})
        failure=core.record("transport_error",app="asterion.control",
                    trace_id="trace123",component="phone_wss_relay",
                    severity="error",state="failed",
                    attributes={"stage":"upgrade","error_class":"HandshakeRejected",
                                "status_code":403,"token":"secret",
                                "url":"https://secret.example/foo?password=key"})
        self.assertTrue(failure["incident"])
        bundle=core.incident_bundle(failure["incident_id"])
        self.assertEqual(bundle["evidence"]["classification"],"unresolved")
        self.assertTrue(bundle["immutable_snapshot"])
        self.assertEqual(len(bundle["evidence"]["events"]),2)
        encoded=json.dumps(bundle["evidence"],sort_keys=True,separators=(",",":"))
        self.assertEqual(hashlib.sha256(encoded.encode()).hexdigest(),
                         bundle["evidence_sha256"])
        self.assertNotIn("secret.example",encoded)
        self.assertNotIn("password=key",encoded)
        self.assertIn('"status_code":403',encoded)
        core.record("transport_error",app="asterion.control",
                    trace_id="trace123",component="phone_wss_relay",
                    severity="error",state="failed",
                    attributes={"stage":"upgrade","error_class":"HandshakeRejected"})
        updated=core.incident_bundle(failure["incident_id"])
        self.assertEqual(bundle["evidence_sha256"],updated["evidence_sha256"])
        self.assertEqual(updated["occurrences"],2)

    def test_signed_export_is_authenticated(self):
        fail=core.record("exception",component="on_device",incident=True,
                         attributes={"error_class":"ProcessCrash"})
        address="/api/v1/diagnostics/incidents/"+fail["incident_id"]+"/export"
        self.assertEqual(self.client.get(address).status_code,401)
        result=self.client.get(address,headers=self.headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.headers["content-type"],"application/json")
        self.assertEqual(result.headers["x-content-sha256"],
                         hashlib.sha256(result.content).hexdigest())
        self.assertIn(b'"classification":"unresolved"',result.content)

    def test_trace_query_is_bounded(self):
        core.record("phone_connected",trace_id="trace-abcd")
        core.record("phone_disconnected",trace_id="trace-abcd")
        self.assertEqual(len(core.trace_events("trace-abcd")["events"]),2)
        self.assertEqual(self.client.get("/api/v1/diagnostics/traces/trace-abcd",
            headers=self.headers).status_code,200)
        self.assertEqual(self.client.get("/api/v1/diagnostics/traces/trace-abcd?limit=501",
            headers=self.headers).status_code,422)
        self.assertIsNone(core.incident_bundle("f"*32))

if __name__=="__main__":
    unittest.main()
