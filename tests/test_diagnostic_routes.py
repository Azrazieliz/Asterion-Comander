"""Authenticated telemetry routing and boundaries."""
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote.diagnostic_routes import router


class DiagnosticApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ, {
            "ASTERION_DIAGNOSTIC_ROOT":self.tmp.name,
            "ASTERION_API_TOKEN":"T"*40,
        })
        self.env.start()
        app=FastAPI()
        app.include_router(router)
        self.client=TestClient(app)
        self.headers={"Authorization":"Bearer "+"T"*40}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_denies_unauthenticated_reader(self):
        self.assertEqual(self.client.get("/api/v1/diagnostics/health").status_code,401)

    def test_authorized_health_and_replay(self):
        h=self.client.get("/api/v1/diagnostics/health",headers=self.headers)
        self.assertEqual(h.status_code,200)
        self.assertEqual(h.json()["event_count"],0)
        event={"kind":"http_failure","app":"asterion.downloader",
               "state":"failed","severity":"error","trace_id":"trace-1",
               "attributes":{"status_code":403,"stage":"media_resolution",
                             "password":"must-never-record"}}
        response=self.client.post("/api/v1/diagnostics/events",json=event,headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["incident"])
        events=self.client.get("/api/v1/diagnostics/events",headers=self.headers).json()["events"]
        self.assertEqual(events[0]["attributes"]["status_code"],403)
        self.assertNotIn("password",events[0]["attributes"])
        issues=self.client.get("/api/v1/diagnostics/incidents",headers=self.headers).json()["incidents"]
        self.assertEqual(issues[0]["kind"],"http_failure")

    def test_rejects_invalid_values(self):
        self.assertEqual(self.client.post("/api/v1/diagnostics/events",
            headers=self.headers,json={"kind":"invalid event type"}).status_code,422)
        self.assertEqual(self.client.get("/api/v1/diagnostics/events?limit=9999",
            headers=self.headers).status_code,422)


if __name__=="__main__":
    unittest.main()
