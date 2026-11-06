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
        assert "no replay" in result.json()["detail"].lower()


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
    monkeypatch.setattr(phone_live, "AUTHORIZED", file)
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
