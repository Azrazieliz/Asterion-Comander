"""Test real partner visibility without false claims of complete instrumentation."""
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote import diagnostic_core as core
from asterion_remote.diagnostic_routes import router


class Answer:
    def __init__(self,data):self.data=data
    def json(self):return self.data


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "ASTERION_API_TOKEN":"A"*40,
            "ASTERION_DIAGNOSTIC_ROOT":self.tmp.name,
        })
        self.env.start()
        app=FastAPI()
        app.include_router(router)
        self.client=TestClient(app)
        self.auth={"Authorization":"Bearer "+"A"*40}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_unauthenticated_coverage_is_denied(self):
        self.assertIn(self.client.get("/api/v1/diagnostics/coverage").status_code,
                      (401,403))
        self.assertEqual(self.client.get(
            "/api/v1/diagnostics/coverage?limit=0",
            headers=self.auth).status_code,422)

    def test_owner_coverage_never_fabricates_partner_instrumentation(self):
        core.record("test_event",app="asterion.control")
        def phone(path,timeout=6):
            if path=="/apps":
                return Answer({"apps":[
                    {"package":"com.asterion.control","label":"Asterion Control"},
                    {"package":"com.asterion.art","label":"Asterion Art"},
                    {"package":"com.openlocal.office","label":"Asterion Rounder"},
                    {"package":"com.google.android.gm","label":"Gmail"},
                ]})
            if path=="/app-bridge/apps":
                return Answer({"apps":[
                    {"package":"com.asterion.art","approved":False}
                ]})
            raise AssertionError(path)
        with patch("asterion_remote.diagnostic_routes.phone_bridge.request",
                   side_effect=phone):
            response=self.client.get("/api/v1/diagnostics/coverage",
                                     headers=self.auth)
        self.assertEqual(response.status_code,200)
        value=response.json()
        self.assertFalse(value["complete_cross_app_coverage_verified"])
        self.assertFalse(value["private_other_app_logs_accessed"])
        self.assertEqual(len(value["apps"]),3)
        bypkg={a["package"]:a for a in value["apps"]}
        self.assertTrue(bypkg["com.asterion.control"][
            "recent_instrumented_event_observed"])
        self.assertFalse(bypkg["com.asterion.art"][
            "recent_instrumented_event_observed"])
        self.assertTrue(bypkg["com.asterion.art"]["partner_bridge_discovered"])
        self.assertFalse(bypkg["com.asterion.art"]["partner_bridge_approved"])
        self.assertFalse(bypkg["com.openlocal.office"]["partner_bridge_discovered"])

    def test_unavailable_phone_catalog_is_not_zero_partner_claim(self):
        with patch("asterion_remote.diagnostic_routes.phone_bridge.request",
                   side_effect=TimeoutError("secret token")):
            r=self.client.get("/api/v1/diagnostics/coverage",headers=self.auth)
        self.assertEqual(r.status_code,200)
        x=r.json()
        self.assertFalse(x["phone_app_catalog_available"])
        self.assertFalse(x["partner_bridge_catalog_available"])
        self.assertIsNone(x["native_partner_count"])
        self.assertNotIn("secret token",str(x))
        self.assertEqual(x["app_catalog_error_code"],"TimeoutError")


if __name__=="__main__":
    unittest.main()
