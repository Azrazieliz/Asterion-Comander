"""Authenticated phone-native candidate preflight tests, no model download."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote import model_capacity_routes as routes


class CapacityApiTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{"ASTERION_API_TOKEN":"A"*40})
        self.env.start()
        app=FastAPI()
        app.include_router(routes.router)
        self.client=TestClient(app)
        self.auth={"Authorization":"Bearer "+"A"*40}
        self.phone={"paired":True,"reachable":True,
            "device":"SM-S948B",
            "info":{"device":"SM-S948B","android":"17",
                    "memory_available":3_656_753_152,
                    "memory_total":11_623_395_328,
                    "storage_available":68_251_230_208,
                    "battery":{"percent":48,"charging":True},
                    "thermals":{"status":2}}}

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_actual_phone_health_endpoint_without_model_claims(self):
        with patch.object(routes,"phone_status",return_value=self.phone):
            noauth=self.client.get(
                "/api/v1/intelligence/models/capacity/phone")
            self.assertEqual(noauth.status_code,401)
            result=self.client.get(
                "/api/v1/intelligence/models/capacity/phone",
                headers=self.auth)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["memory_available"],3_656_753_152)
        self.assertFalse(result.json()["model_loaded"])
        self.assertFalse(result.json()["phone_model_verified"])

    def test_missing_phone_is_explicit_not_zero_ram(self):
        with patch.object(routes,"phone_status",
                          return_value={"paired":False}):
            response=self.client.get(
                "/api/v1/intelligence/models/capacity/phone",
                headers=self.auth)
        self.assertEqual(response.json()["state"],"PHONE_UNREACHABLE")

    def test_candidate_admission_uses_live_mobile_budget(self):
        body={"repository":"Qwen/Qwen3.5-2B",
              "license_id":"apache-2.0","weight_file_bytes":1_350_000_000,
              "estimated_peak_ram_bytes":2_050_000_000,
              "artifact_sha256":"a"*64,
              "original_author_verified":True}
        with patch.object(routes,"phone_status",return_value=self.phone):
            response=self.client.post(
                "/api/v1/intelligence/models/capacity/phone/check",
                headers=self.auth,json=body)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["candidate_for_device_test"])
        self.assertFalse(response.json()["model_downloaded"])
        self.assertFalse(response.json()["inference_device_benchmarked"])

    def test_large_unverified_model_not_admitted(self):
        body={"repository":"Untrusted/very-large",
              "license_id":"unknown","weight_file_bytes":8_000_000_000,
              "estimated_peak_ram_bytes":12_000_000_000}
        with patch.object(routes,"phone_status",return_value=self.phone):
            result=self.client.post(
                "/api/v1/intelligence/models/capacity/phone/check",
                headers=self.auth,json=body)
        self.assertEqual(result.status_code,200)
        self.assertFalse(result.json()["candidate_for_device_test"])
        self.assertIn("weights_exceed_free_memory_after_os_reserve",
                      result.json()["blockers"])


if __name__=="__main__":
    unittest.main()
