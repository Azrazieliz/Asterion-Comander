"""Authenticated finite native assistant routes; zero external models used."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote import assistant_routes


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "ASTERION_ASSISTANT_ROOT":self.temp.name,
            "ASTERION_API_TOKEN":"A"*40,
            "ASTERION_OWNER_APPROVAL_SECRET":"B"*40,
            "ASTERION_LOCAL_MODEL_ENDPOINT":"",
            "ASTERION_LOCAL_MODEL_ID":"",
            "ASTERION_ASSISTANT_ALLOWED_TOOLS":"",
            "ASTERION_ASSISTANT_ENABLE_MUTATIONS":"0",
        })
        self.env.start()
        app=FastAPI()
        app.include_router(assistant_routes.router)
        self.client=TestClient(app)
        self.auth={"Authorization":"Bearer "+"A"*40}
        self.owner={**self.auth,"X-Owner-Approval":"B"*40}
        self.base="/api/v1/intelligence/assistant"
        self.body={"request_id":"ownerassistant-00001",
                   "prompt":"Please respond to my actual request in French"}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def test_status_reports_unconfigured_no_fake_completion(self):
        self.assertEqual(self.client.get(self.base+"/status").status_code,401)
        status=self.client.get(self.base+"/status",headers=self.auth)
        self.assertEqual(status.status_code,200)
        self.assertFalse(status.json()["local_model_configured"])
        self.assertFalse(status.json()["local_model_executed"])
        self.assertIn("host.health",status.json()["owner_tool_scopes"])
        self.assertFalse(status.json()["ordinary_requests_are_overnight_cycles"])

    def test_owner_approval_required_even_read_only(self):
        self.assertEqual(self.client.post(self.base+"/execute",headers=self.auth,
            json=self.body).status_code,403)
        response=self.client.post(self.base+"/execute",headers=self.owner,
            json=self.body)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()["detail"],"Local model not configured")
        self.assertEqual(self.client.get(self.base+"/requests",
            headers=self.auth).json()["requests"],[])

    def test_owner_allowlist_prevents_privileged_tool(self):
        request={**self.body,"tools":["native.session"],
                 "allow_device_actions":True}
        denied=self.client.post(self.base+"/execute",headers=self.owner,
                                 json=request)
        self.assertEqual(denied.status_code,403)
        self.assertIn("not allowed",denied.json()["detail"])

    def test_requires_separate_runtime_enable_for_mutation(self):
        request={**self.body,"tools":["native.session"],
                 "allow_device_actions":True}
        with patch.dict(os.environ,{
            "ASTERION_ASSISTANT_ALLOWED_TOOLS":"native.session"}):
            denied=self.client.post(self.base+"/execute",headers=self.owner,
                                     json=request)
            self.assertEqual(denied.status_code,403)
            self.assertIn("disabled",denied.json()["detail"])

    def test_real_model_adapter_routing_only_after_explicit_configuration(self):
        seen=[]
        class FakeProvider:
            def __init__(self, config):
                seen.append(config)
            def __call__(self,prompt,ident):
                self_id=ident
                self.body=(prompt,ident)
                return {"message_id":"local-test-reply-001",
                        "content":json.dumps({
                            "action":"final","message":"Reponse generale du modele"})}
        with patch.dict(os.environ,{
            "ASTERION_LOCAL_MODEL_ENDPOINT":
                "http://127.0.0.1:8080/v1/chat/completions",
            "ASTERION_LOCAL_MODEL_ID":"test-general-model"}), patch.object(
                assistant_routes,"LocalModelProvider",FakeProvider):
            result=self.client.post(self.base+"/execute",headers=self.owner,
                                    json=self.body)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["answer"],"Reponse generale du modele")
        self.assertFalse(result.json()["project_work_verified"])
        self.assertEqual(len(seen),1)
        self.assertIn("general-purpose",seen[0].system_instruction)
        status=self.client.get(self.base+"/requests/ownerassistant-00001",
                               headers=self.auth)
        self.assertEqual(status.status_code,200)
        self.assertEqual(status.json()["state"],"answered")
        self.assertNotIn(self.body["prompt"],str(status.json()))

    def test_no_model_text_executes_undeclared_tools(self):
        class MaliciousProvider:
            def __init__(self, config):pass
            def __call__(self,prompt,ident):
                return {"content":json.dumps({
                    "action":"tool","name":"native.session",
                    "arguments":{"device":"pc","steps":[
                        {"kind":"wait","wait_ms":10}]}})}
        with patch.dict(os.environ,{
            "ASTERION_LOCAL_MODEL_ENDPOINT":
                "http://127.0.0.1:8080/v1/chat/completions",
            "ASTERION_LOCAL_MODEL_ID":"test-general-model"}), patch.object(
                assistant_routes,"LocalModelProvider",MaliciousProvider):
            result=self.client.post(self.base+"/execute",headers=self.owner,
                                    json=self.body)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["state"],"needs_review")
        self.assertEqual(result.json()["error_code"],"PermissionError")
        self.assertEqual(result.json()["tool_receipts"],0)


if __name__=="__main__":
    unittest.main()
