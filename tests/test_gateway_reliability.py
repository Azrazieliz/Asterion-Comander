"""Direct encrypted Asterion Control MCP: no GitHub runtime fallback.

Deterministic transport tests, separate from real Samsung acceptance.
"""
import hashlib
import json
import httpx
from fastapi.testclient import TestClient
from asterion_remote import mcp_gateway, phone_live

AUTH = {
    "Authorization": "Bearer " + "k" * 48,
    "Accept": "application/json, text/event-stream",
}
RPC = {
    "jsonrpc": "2.0", "id": 77, "method": "tools/call",
    "params": {"name": "control_phone_input",
               "arguments": {"action": "tap", "x": 55, "y": 60}},
}


def _authorize(monkeypatch):
    monkeypatch.setattr(mcp_gateway, "_secret", lambda _: "k" * 48)


def test_mcp_discovery_works_without_phone_and_pc(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(mcp_gateway, "phone_live_connected", lambda: False)
    monkeypatch.setattr(mcp_gateway, "_phone_route", lambda: None)
    monkeypatch.setattr(mcp_gateway, "_windows_route", lambda: None)
    with TestClient(mcp_gateway.app) as client:
        init = client.post("/mcp", headers=AUTH, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"}})
        assert init.status_code == 200
        assert init.json()["result"]["serverInfo"]["name"] == "asterion-control"
        listed = client.post("/mcp", headers=AUTH, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert listed.status_code == 200
        names = {x["name"] for x in listed.json()["result"]["tools"]}
        assert "control_phone_voice_ack" in names
        assert "control_phone_cycle_start" in names
        assert "control_phone_cloud_receipt" not in names


def test_direct_cellular_mcp_preserves_native_application_errors(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(mcp_gateway, "phone_live_connected", lambda: True)
    monkeypatch.setattr(mcp_gateway, "_phone_route", lambda: None)
    async def direct(rpc, timeout=22):
        assert rpc["params"]["name"] == "control_phone_input"
        return {"jsonrpc": "2.0", "id": 77,
                "error": {"code": -32000, "message": "gesture refused"}}
    monkeypatch.setattr(mcp_gateway, "phone_live_invoke", direct)
    with TestClient(mcp_gateway.app) as client:
        result = client.post("/mcp", headers=AUTH, json=RPC)
        assert result.status_code == 200
        assert result.json()["error"]["message"] == "gesture refused"


def test_direct_disconnection_is_uncertain_and_never_replayed(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(mcp_gateway, "phone_live_connected", lambda: True)
    async def uncertain(rpc, timeout=22):
        raise phone_live.DirectPhoneUncertain("Message may have executed")
    monkeypatch.setattr(mcp_gateway, "phone_live_invoke", uncertain)
    async def never(*args, **kwargs):
        raise AssertionError("Unexpected duplicate LAN execution")
    monkeypatch.setattr(mcp_gateway, "_forward", never)
    with TestClient(mcp_gateway.app) as client:
        result = client.post("/mcp", headers=AUTH, json=RPC)
        assert result.status_code == 504
        assert "replay" in result.json()["detail"].lower()


def test_private_wifi_phone_mcp_works_without_github(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(mcp_gateway, "phone_live_connected", lambda: False)
    monkeypatch.setattr(mcp_gateway, "_phone_route",
                        lambda: ("http://192.168.4.5:8973/mcp", "x" * 48))
    async def native(*args, **kwargs):
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": 77,
            "result": {"content": [{"type": "text", "text": "{\\\"ok\\\":true}"}]}})
    monkeypatch.setattr(mcp_gateway, "_forward", native)
    with TestClient(mcp_gateway.app) as client:
        result = client.post("/mcp", headers=AUTH, json=RPC)
        assert result.status_code == 200
        assert result.json()["result"]["content"][0]["type"] == "text"


def test_authorized_phone_pairing_token_required_for_public_websocket(tmp_path, monkeypatch):
    credential = "paired-" + "p" * 48
    file = tmp_path / "authorized-devices.json"
    file.write_text(json.dumps([
        {"device": "Samsung", "hash": hashlib.sha256(credential.encode()).hexdigest()}
    ]), encoding="utf-8")
    from asterion_remote import pairing
    monkeypatch.setattr(pairing, "PAIRED", file)
    assert phone_live._authorized(credential)
    assert not phone_live._authorized(credential[:-1] + "x")
    assert not phone_live._authorized("")
    assert not phone_live._authorized("p" * 1024)
    file.unlink()
    assert not phone_live._authorized(credential)


def test_public_mcp_requires_authentication(monkeypatch):
    _authorize(monkeypatch)
    with TestClient(mcp_gateway.app) as client:
        assert client.post("/mcp", headers={"Accept": AUTH["Accept"]},
                           json=RPC).status_code == 401

def test_performance_mcp_uses_native_phone_cellular_route(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(mcp_gateway, "phone_live_connected", lambda: True)
    names=[]
    async def android(rpc, timeout=22):
        names.append(rpc["params"]["name"])
        return {"jsonrpc":"2.0","id":rpc["id"],
                "result":{"content":[{"type":"text","text":"ok"}]}}
    monkeypatch.setattr(mcp_gateway, "phone_live_invoke", android)
    with TestClient(mcp_gateway.app) as client:
        for tool in ("control_phone_performance_status",
                     "control_phone_performance_mode",
                     "control_phone_performance_optimize"):
            response=client.post("/mcp",headers=AUTH,json={
                "jsonrpc":"2.0","id":901,"method":"tools/call",
                "params":{"name":tool,"arguments":{"mode":"automatic"}}})
            assert response.status_code==200
    assert names==[
        "control_phone_performance_status",
        "control_phone_performance_mode",
        "control_phone_performance_optimize",
    ]


def test_canonical_tools_survive_stale_subordinate_agent(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(mcp_gateway, "phone_live_connected", lambda: False)
    monkeypatch.setattr(mcp_gateway, "_phone_route", lambda: None)
    monkeypatch.setattr(
        mcp_gateway, "_windows_route",
        lambda: ("http://192.168.0.12:8911/mcp", "m" * 48))
    async def stale(*args, **kwargs):
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": 55,
            "result": {"tools": [{
                "name": "remote_system", "description": "Older Windows agent",
                "inputSchema": {"type": "object", "properties": {}}
            }]}})
    monkeypatch.setattr(mcp_gateway, "_forward", stale)
    with TestClient(mcp_gateway.app) as client:
        reply = client.post("/mcp", headers=AUTH, json={
            "jsonrpc": "2.0", "id": 55, "method": "tools/list"})
        assert reply.status_code == 200
        tools = {t["name"] for t in reply.json()["result"]["tools"]}
        assert "control_phone_performance_optimize" in tools
        assert "control_pc_performance_mode" in tools
        assert "control_phone_cycle_start" in tools
        assert "remote_system" in tools


def test_registered_phone_agent_token_supports_direct_cellular(monkeypatch):
    """Native phone identity, not Windows pairing preferences, is the WSS key."""
    from asterion_remote import pairing
    token = "phone-owned-" + "p" * 48
    monkeypatch.setattr(phone_live, "load_registered_phone",
                        lambda: {"device": "Samsung", "token": token})
    monkeypatch.setattr(phone_live, "paired_device_is_authorized", lambda key: False)
    assert phone_live._authorized(token) is True
    assert phone_live._authorized(token + "extra") is False
    assert phone_live._authorized("") is False
    monkeypatch.setattr(phone_live, "load_registered_phone", lambda: None)
    assert phone_live._authorized(token) is False


def test_revoked_native_registration_cannot_connect(monkeypatch):
    token = "agent-" + "a" * 44
    monkeypatch.setattr(phone_live, "load_registered_phone",
                        lambda: {"device": "Samsung", "token": token})
    monkeypatch.setattr(phone_live, "paired_device_is_authorized", lambda key: False)
    assert phone_live._authorized(token)
    monkeypatch.setattr(phone_live, "load_registered_phone", lambda: None)
    assert not phone_live._authorized(token)
