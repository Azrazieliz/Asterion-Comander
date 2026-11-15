"""Check owner-authenticated GitHub MCP routes without actual GitHub service."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote import mcp_tool_routes


class FakeMcpClient:
    def __init__(self):
        self.calls=[]

    def list_tools(self):
        return {"ok":True,"items":[{"name":"safe.echo","owner_approved":True}],
                "owner_authorized_tools":1,"secrets_exposed":False}

    def call_tool(self,name,args):
        if name!="safe.echo":
            raise PermissionError("mcp_tool_not_owner_approved")
        self.calls.append((name,args))
        return {"ok":True,"tool_name":name,"result":{
            "content":[{"type":"text","text":args["text"]}]},
            "project_work_verified":False}


class McpRoutesTests(unittest.TestCase):
    def setUp(self):
        self.environment=patch.dict(os.environ,{
            "ASTERION_API_TOKEN":"C"*40,
            "ASTERION_OWNER_APPROVAL_SECRET":"D"*40,
            "ASTERION_GITHUB_MCP_EXECUTABLE":"",
            "ASTERION_GITHUB_MCP_BINARY_SHA256":"",
            "ASTERION_GITHUB_MCP_ALLOWED_TOOLS":"",
            "GITHUB_PERSONAL_ACCESS_TOKEN":"",
        })
        self.environment.start()
        api=FastAPI()
        api.include_router(mcp_tool_routes.router)
        self.client=TestClient(api)
        self.auth={"Authorization":"Bearer "+"C"*40}
        self.owner={**self.auth,"X-Owner-Approval":"D"*40}

    def tearDown(self):
        self.client.close()
        self.environment.stop()

    def test_unconfigured_reports_no_fake_github_mcp(self):
        status=self.client.get("/api/v1/intelligence/mcp/status",
                               headers=self.auth)
        self.assertEqual(status.status_code,200)
        self.assertFalse(status.json()["configured"])
        self.assertFalse(status.json()["retired_control_gateway_restarted"])
        tools=self.client.get("/api/v1/intelligence/mcp/tools",
                              headers=self.owner)
        self.assertEqual(tools.status_code,503)

    def test_mcp_tool_access_requires_distinct_owner_approval(self):
        self.assertEqual(self.client.get(
            "/api/v1/intelligence/mcp/status").status_code,401)
        self.assertEqual(self.client.get(
            "/api/v1/intelligence/mcp/tools",headers=self.auth).status_code,403)
        self.assertEqual(self.client.post(
            "/api/v1/intelligence/mcp/call",headers=self.auth,
            json={"tool_name":"safe.echo","arguments":{"text":"hello"}}).status_code,403)

    def test_tool_result_is_not_falsely_verified_project_work(self):
        fake=FakeMcpClient()
        with patch.object(mcp_tool_routes,"_get_client",return_value=fake):
            catalog=self.client.get("/api/v1/intelligence/mcp/tools",
                                    headers=self.owner)
            self.assertEqual(catalog.status_code,200)
            result=self.client.post("/api/v1/intelligence/mcp/call",
                headers=self.owner,
                json={"tool_name":"safe.echo","arguments":{"text":"actual"}})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["result"]["content"][0]["text"],"actual")
        self.assertFalse(result.json()["project_work_verified"])
        self.assertEqual(fake.calls,[("safe.echo",{"text":"actual"})])

    def test_disallowed_write_tool_fails_closed(self):
        fake=FakeMcpClient()
        with patch.object(mcp_tool_routes,"_get_client",return_value=fake):
            result=self.client.post("/api/v1/intelligence/mcp/call",
                headers=self.owner,
                json={"tool_name":"danger.delete",
                      "arguments":{"path":"owner-originals"}})
        self.assertEqual(result.status_code,403)
        self.assertEqual(fake.calls,[])


if __name__=="__main__":
    unittest.main()
