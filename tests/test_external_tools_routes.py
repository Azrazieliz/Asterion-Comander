"""Authenticated browser/reverse routes and finite-model delegated real tools."""
import os
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote import browser_routes,reverse_routes,native_assistant


class ExternalToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "ASTERION_API_TOKEN":"A"*40,
            "ASTERION_OWNER_APPROVAL_SECRET":"B"*40,
            "ASTERION_ASSISTANT_ROOT":self.temp.name
        })
        self.env.start()
        self.app=FastAPI()
        self.app.include_router(browser_routes.router)
        self.app.include_router(reverse_routes.router)
        self.client=TestClient(self.app)
        self.auth={"Authorization":"Bearer "+"A"*40}
        self.owner={**self.auth,"X-Owner-Approval":"B"*40}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def test_browsing_requires_owner_approval(self):
        body={"url":"https://example.com/"}
        path="/api/v1/intelligence/browser/open"
        self.assertEqual(self.client.post(path,json=body).status_code,401)
        self.assertEqual(self.client.post(path,json=body,
                                          headers=self.auth).status_code,403)

    def test_browsing_returns_real_source_contract_not_claimed_download(self):
        event={"ok":True,"url":"https://example.com/",
               "http_status":200,"text":"Example Domain",
               "title":"Example Domain","links":[],
               "page_js_executed":False,"media_downloaded":False,
               "response_is_untrusted_data":True}
        with patch.object(browser_routes.shared_browser,"fetch",
                          return_value=event) as invoke:
            response=self.client.post("/api/v1/intelligence/browser/open",
                        headers=self.owner,json={"url":"https://example.com/"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["title"],"Example Domain")
        self.assertFalse(response.json()["page_js_executed"])
        invoke.assert_called_once_with("https://example.com/",tor=False,
                                       timeout_s=9.0)

    def test_reverse_requires_owner_approval_and_safe_root(self):
        p="/api/v1/intelligence/reverse/inspect"
        self.assertEqual(self.client.post(p,
            headers=self.auth,json={"path":"app.apk"}).status_code,403)
        from asterion_remote import app as control
        with patch.object(control,"ROOT",Path(self.temp.name)), patch.object(
            control,"EXTRA_ROOTS",[]):
            denied=self.client.post(p,headers=self.owner,
                                    json={"path":"../secret.exe"})
            self.assertEqual(denied.status_code,403)

    def test_actual_external_binary_route_reports_structure(self):
        p="/api/v1/intelligence/reverse/inspect"
        binary=Path(self.temp.name)/"opaque.bin"
        binary.write_bytes(b"non-executable unknown byte content")
        from asterion_remote import app as control
        with patch.object(control,"ROOT",Path(self.temp.name)), patch.object(
            control,"EXTRA_ROOTS",[]):
            result=self.client.post(p,headers=self.owner,
                                    json={"path":"opaque.bin"})
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.json()["static_analysis_only"])
        self.assertEqual(result.json()["format"]["type"],"unrecognized")
        self.assertFalse(result.json()["full_source_decompiled"])

    def test_model_cannot_use_network_without_explicit_grant(self):
        request="Find the current public website documentation for the owner"
        ident="owner-tools-000001"
        called=[]
        def model(prompt,request_id):
            called.append(request_id)
            return {"content":json.dumps({
                "action":"tool","name":"browser.read",
                "arguments":{"url":"https://example.com"}})}
        with patch("asterion_remote.shared_browser.fetch",
                   side_effect=AssertionError("must not browse")):
            result=native_assistant.execute(request,ident,model)
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"],"needs_review")
        self.assertEqual(result["error_code"],"PermissionError")
        self.assertEqual(result["tool_receipts"],0)

    def test_authorized_native_agent_can_read_bounded_public_page(self):
        request="Find the current public website documentation for the owner"
        seen=[]
        def model(prompt,request_id):
            seen.append((prompt,request_id))
            if len(seen)==1:
                return {"content":json.dumps({
                    "action":"tool","name":"browser.read",
                    "arguments":{"url":"https://example.com"}})}
            return {"content":json.dumps({
                "action":"final","message":"The source showed Example Domain"})}
        evidence={"ok":True,"title":"Example Domain",
                  "url":"https://example.com","text":"Example Domain",
                  "content_sha256":"a"*64,"page_js_executed":False}
        with patch("asterion_remote.shared_browser.fetch",return_value=evidence):
            result=native_assistant.execute(request,"owner-tools-000002",
                  model,owner_grants=frozenset({"browser.read"}))
        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_receipts"],1)
        self.assertIn("Example Domain",seen[1][0])
        self.assertFalse(result["project_work_verified"])


if __name__=="__main__":
    unittest.main()
