"""MCP must challenge OAuth before discovery and complete the standard handshake."""
from fastapi.testclient import TestClient
from asterion_remote import mcp_gateway
import pytest

ACCEPT = {"Accept": "application/json, text/event-stream"}
SECRET = "k"*48
AUTHORIZED = {**ACCEPT, "Authorization": "Bearer "+SECRET}

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mcp_gateway, "_secret",lambda _:SECRET)
    monkeypatch.setattr(mcp_gateway, "valid_access",lambda token:False)
    monkeypatch.setattr(mcp_gateway, "phone_live_connected",lambda:False)
    monkeypatch.setattr(mcp_gateway, "_phone_route",lambda:None)
    monkeypatch.setattr(mcp_gateway, "_windows_route",lambda:None)
    with TestClient(mcp_gateway.app) as c: yield c

def request(method,id=1):
    payload={"jsonrpc":"2.0","id":id,"method":method}
    if method=="initialize":
        payload["params"]={"protocolVersion":"2025-11-25",
                           "capabilities":{},
                           "clientInfo":{"name":"test-client","version":"1.0.0"}}
    if method=="tools/call":
        payload["params"]={"name":"control_phone_status","arguments":{}}
    if method=="notifications/initialized":payload.pop("id")
    return payload

@pytest.mark.parametrize("method",["initialize","tools/list","tools/call","notifications/initialized"])
def test_unauthenticated_mcp_requires_oauth(client,method):
    resp=client.post("/mcp",headers=ACCEPT,json=request(method))
    assert resp.status_code==401
    challenge=resp.headers.get("www-authenticate","")
    assert 'resource_metadata="' in challenge
    assert "oauth-protected-resource" in challenge

def test_authorized_handshake_then_tool_catalogue(client):
    init=client.post("/mcp",headers=AUTHORIZED,json=request("initialize"))
    assert init.status_code==200
    assert init.json()["result"]["serverInfo"]["name"]=="asterion-control"
    notif=client.post("/mcp",headers=AUTHORIZED,json=request("notifications/initialized"))
    assert notif.status_code==202
    listed=client.post("/mcp",headers=AUTHORIZED,json=request("tools/list"))
    assert listed.status_code==200
    catalog=listed.json()["result"]["tools"]
    assert len(catalog)>=30
    names={item["name"] for item in catalog}
    assert "control_phone_status" in names
    assert "control_phone_voice_question" in names

def test_invalid_token_always_challenged(client):
    headers={**ACCEPT,"Authorization":"Bearer wrong"}
    assert client.post("/mcp",headers=headers,json=request("tools/list")).status_code==401

def test_oauth_metadata_is_public(client):
    info=client.get("/.well-known/oauth-protected-resource/mcp")
    assert info.status_code==200
    assert info.json()["resource"].endswith("/mcp")
