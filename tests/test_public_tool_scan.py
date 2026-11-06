"""Unauthenticated MCP discovery is metadata-only, never device access."""
from fastapi.testclient import TestClient
from asterion_remote.mcp_gateway import app

def test_chatgpt_can_scan_protected_tool_schemas_without_connecting_devices():
    client = TestClient(app)
    headers = {"accept": "application/json, text/event-stream"}
    def rpc(method, params=None):
        return client.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
    startup = rpc("initialize")
    assert startup.status_code == 200
    assert startup.json()["result"]["serverInfo"]["name"] == "asterion-control"
    listing = rpc("tools/list")
    assert listing.status_code == 200
    tools = listing.json()["result"]["tools"]
    assert len(tools) >= 25
    assert any(t["name"] == "control_phone_voice_question" for t in tools)
    assert all(t["_meta"]["securitySchemes"] == [
        {"type": "oauth2", "scopes": ["asterion.control"]}
    ] for t in tools)
    protected = rpc("tools/call", {"name": "control_phone_status", "arguments": {}})
    assert protected.status_code == 401
    assert "resource_metadata" in protected.headers["www-authenticate"]
