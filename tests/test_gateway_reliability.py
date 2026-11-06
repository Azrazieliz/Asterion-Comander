"""MCP offsite fallback safety and idempotency acceptance tests."""
import httpx
from fastapi.testclient import TestClient
from asterion_remote import mcp_gateway, phone_cloud_relay


AUTH = {
    "Authorization": "Bearer " + "k" * 48,
    "Accept": "application/json, text/event-stream",
}
RPC = {
    "jsonrpc": "2.0", "id": 77, "method": "tools/call",
    "params": {"name": "control_phone_input",
               "arguments": {"action": "tap", "x": 55, "y": 60}},
}


def test_gateway_discovery_offsite_with_pc_and_phone_offline(monkeypatch):
    monkeypatch.setattr(mcp_gateway, "_secret", lambda _: "k" * 48)
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
        assert "control_phone_cloud_receipt" in names


def test_native_application_failure_must_never_be_replayed(monkeypatch):
    monkeypatch.setattr(mcp_gateway, "_secret", lambda _: "k" * 48)
    monkeypatch.setattr(mcp_gateway, "_phone_route",
                        lambda: ("http://192.168.4.5:8973/mcp", "x" * 48))
    async def reply(*args, **kwargs):
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": 77,
            "error": {"code": -32000, "message": "gesture refused"}})
    async def never(*args, **kwargs):
        raise AssertionError("Native error must not trigger duplicate cloud action")
    monkeypatch.setattr(mcp_gateway, "_forward", reply)
    monkeypatch.setattr(phone_cloud_relay, "submit", never)
    with TestClient(mcp_gateway.app) as client:
        result = client.post("/mcp", headers=AUTH, json=RPC)
        assert result.status_code == 200
        assert result.json()["error"]["message"] == "gesture refused"


def test_native_response_timeout_is_uncertain_and_never_replayed(monkeypatch):
    monkeypatch.setattr(mcp_gateway, "_secret", lambda _: "k" * 48)
    monkeypatch.setattr(mcp_gateway, "_phone_route",
                        lambda: ("http://192.168.4.5:8973/mcp", "x" * 48))
    async def timed_out(*args, **kwargs):
        raise httpx.ReadTimeout("Phone accepted the request but response was lost")
    async def never(*args, **kwargs):
        raise AssertionError("Ambiguous native command must never be repeated")
    monkeypatch.setattr(mcp_gateway, "_forward", timed_out)
    monkeypatch.setattr(phone_cloud_relay, "submit", never)
    with TestClient(mcp_gateway.app) as client:
        response = client.post("/mcp", headers=AUTH, json=RPC)
        assert response.status_code == 504
        assert "will not replay" in response.json()["detail"]


def test_failed_receipt_never_reports_success():
    identifier = "phone-" + "a" * 32
    actual = phone_cloud_relay.wrap_result(identifier, {
        "id": identifier, "status": "complete", "ok": False,
        "error": "Android denied access"})
    assert actual["error"]["code"] == -32009
    assert "Android denied access" in actual["error"]["message"]


def test_remote_cloud_requires_exact_id_for_receipts():
    from pytest import raises
    for value in ("phone-../etc/passwd", "phone-" + "g" * 32, "phone-" + "0" * 33):
        with raises(ValueError):
            phone_cloud_relay.url("results", value)
