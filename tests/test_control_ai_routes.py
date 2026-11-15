"""Authenticated Control AI API tests; isolated local state, no model install."""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote.control_ai_routes import router


class ControlAiRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "ASTERION_API_TOKEN":"A"*40,
            "ASTERION_OWNER_APPROVAL_SECRET":"B"*40,
            "ASTERION_OVERNIGHT_ROOT":self.temp.name,
        },clear=False)
        self.env.start()
        app=FastAPI()
        app.include_router(router)
        self.client=TestClient(app)
        self.auth={"Authorization":"Bearer "+"A"*40}
        self.owner={**self.auth,"X-Owner-Approval":"B"*40}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def cycle(self):
        return {"cycle_id":"ownerproject01","project":"AsterionControl",
                "spec_reference":"docs/CONTROL_V5.md",
                "objective":"Implement a verified project upgrade with real tests",
                "provider":"pc_local","max_turns":0}

    def test_auth_and_distinct_owner_approval(self):
        self.assertEqual(self.client.get("/api/v1/intelligence/cycles").status_code,401)
        self.assertEqual(self.client.post("/api/v1/intelligence/cycles",
            headers=self.auth,json=self.cycle()).status_code,403)
        created=self.client.post("/api/v1/intelligence/cycles",
            headers=self.owner,json=self.cycle())
        self.assertEqual(created.status_code,200)
        self.assertTrue(created.json()["is_development_cycle"])
        self.assertFalse(created.json()["automatic_turns_running"])
        self.assertFalse(created.json()["provider_executor_bound"])
        self.assertEqual(self.client.post("/api/v1/intelligence/cycles",
            headers=self.owner,json=self.cycle()).status_code,409)

    def test_status_rejects_fabricated_running_claim(self):
        self.client.post("/api/v1/intelligence/cycles",
                         headers=self.owner,json=self.cycle())
        status=self.client.get("/api/v1/intelligence/cycles/ownerproject01",
                               headers=self.auth)
        self.assertEqual(status.status_code,200)
        self.assertEqual(status.json()["state"],"ready")
        self.assertFalse(status.json()["automatic_turns_running"])
        self.assertFalse(status.json()["automatic_progress_verified"])
        self.assertEqual(self.client.get("/api/v1/intelligence/cycles",
                        headers=self.auth).json()["items"][0]["verified_turns"],0)

    def test_pause_resume_stop_require_owner_credential(self):
        self.client.post("/api/v1/intelligence/cycles",
                         headers=self.owner,json=self.cycle())
        base="/api/v1/intelligence/cycles/ownerproject01"
        self.assertEqual(self.client.post(base+"/pause",headers=self.auth).status_code,403)
        self.assertEqual(self.client.post(base+"/pause",headers=self.owner).json()["state"],"paused")
        self.assertEqual(self.client.post(base+"/resume",headers=self.owner).json()["state"],"ready")
        self.assertEqual(self.client.post(base+"/stop",headers=self.owner).json()["state"],"stopped")

    def test_autonomy_route_fails_closed_when_no_owner_runtime(self):
        self.client.post("/api/v1/intelligence/cycles",
                         headers=self.owner,json=self.cycle())
        endpoint="/api/v1/intelligence/cycles/ownerproject01/advance"
        denied=self.client.post(endpoint,headers=self.auth)
        self.assertEqual(denied.status_code,403)
        unavailable=self.client.post(endpoint,headers=self.owner)
        self.assertEqual(unavailable.status_code,503)
        self.assertEqual(self.client.get(
            "/api/v1/intelligence/cycles/ownerproject01",
            headers=self.auth).json()["verified_turns"],0)

    def test_autonomy_queue_receipt_is_not_misreported_as_completed(self):
        from asterion_remote import control_ai_routes as routes
        self.client.post("/api/v1/intelligence/cycles",
                         headers=self.owner,json=self.cycle())
        endpoint="/api/v1/intelligence/cycles/ownerproject01/advance"
        with patch.object(routes.development_cycle_driver,"start",
                          return_value={"configured":True}), patch.object(
               routes.development_cycle_driver,"queue_turn",
               return_value={"ok":True,"cycle_id":"ownerproject01",
                             "state":"queued","completed":False}):
            response=self.client.post(endpoint,headers=self.owner)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["state"],"queued")
        self.assertFalse(response.json()["completed"])
        cycle=self.client.get(
            "/api/v1/intelligence/cycles/ownerproject01",headers=self.auth)
        self.assertEqual(cycle.json()["verified_turns"],0)

    def test_status_distinguishes_active_automatic_worker_from_stored_cycle(self):
        from asterion_remote import control_ai_routes as routes
        self.client.post("/api/v1/intelligence/cycles",
                         headers=self.owner,json=self.cycle())
        with patch.object(routes.development_cycle_driver,"worker_status",
                return_value={"recent_turns":[{
                    "cycle_id":"ownerproject01","state":"running"}]}):
            current=self.client.get(
                "/api/v1/intelligence/cycles/ownerproject01",
                headers=self.auth)
        self.assertTrue(current.json()["automatic_turns_running"])
        self.assertEqual(current.json()["verified_turns"],0)

    def test_local_model_unconfigured_not_faked(self):
        req={"prompt":"Investigate current source evidence for a real project",
             "request_id":"owner-request-12345"}
        with patch.dict(os.environ,{
            "ASTERION_LOCAL_MODEL_ENDPOINT":"",
            "ASTERION_LOCAL_MODEL_ID":""}):
            response=self.client.post("/api/v1/intelligence/local-model/complete",
                headers=self.owner,json=req)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()["detail"],
                         "Local model not configured on this host")

    def test_local_inference_owner_approval_and_provenance(self):
        req={"prompt":"Investigate current source evidence for a real project",
             "request_id":"owner-request-12345","max_tokens":512}
        class Provider:
            def __init__(self,config):
                self.config=config
            def __call__(self,prompt,request_id):
                return {"message_id":"local-test-12345","content":"test result",
                        "origin":"owner_local_loopback_inference",
                        "model":self.config.model,"paid_cloud_used":False}
        env={"ASTERION_LOCAL_MODEL_ENDPOINT":
             "http://127.0.0.1:8080/v1/chat/completions",
             "ASTERION_LOCAL_MODEL_ID":"test-local"}
        with patch.dict(os.environ,env), patch(
                "asterion_remote.control_ai_routes.LocalModelProvider",Provider):
            self.assertEqual(self.client.post(
                "/api/v1/intelligence/local-model/complete",
                headers=self.auth,json=req).status_code,403)
            response=self.client.post(
                "/api/v1/intelligence/local-model/complete",
                headers=self.owner,json=req)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()["tool_execution_performed"])
        self.assertFalse(response.json()["project_work_verified"])
        self.assertFalse(response.json()["paid_cloud_used"])


if __name__ == "__main__":
    unittest.main()
