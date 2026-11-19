"""Cellular WSS phone RPC: authentication, exact Android tools and no side-effect replay."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from asterion_remote import native_phone_rpc as rpc
from asterion_remote import phone_bridge

TOKEN = "paired-native-control-test-" + "K" * 40


def app_client(monkeypatch, online=True):
    monkeypatch.setattr(rpc, "load_registered_phone", lambda: {"token": TOKEN})
    monkeypatch.setattr(rpc, "connected", lambda: online)
    app = FastAPI()
    app.include_router(rpc.router)
    return TestClient(app, client=("127.0.0.1", 8123))


def test_phone_rpc_is_loopback_and_pairing_only(monkeypatch):
    monkeypatch.setattr(rpc, "load_registered_phone", lambda: {"token": TOKEN})
    app = FastAPI()
    app.include_router(rpc.router)
    with TestClient(app) as public_client:
        assert public_client.post("/phone/rpc", json={"path": "/health"}).status_code == 403
    with app_client(monkeypatch) as client:
        assert client.post("/phone/rpc", json={"path": "/health"}).status_code == 401
        assert client.post("/phone/rpc", headers={"Authorization": "Bearer bad"},
                           json={"path": "/health"}).status_code == 401


def test_phone_rpc_connected_cellular_uses_android_tool(monkeypatch):
    called = []
    async def invoke(record, timeout):
        called.append((record, timeout))
        return {"jsonrpc": "2.0", "id": record["id"],
                "result": {"content": [{"type": "text", "text": json.dumps(
                    {"ok": True, "network": "cellular", "connected": True})}]}}
    monkeypatch.setattr(rpc, "invoke", invoke)
    with app_client(monkeypatch) as client:
        result = client.post("/phone/rpc", headers={"Authorization": "Bearer " + TOKEN},
                             json={"path": "/network/status", "method": "GET"}).json()
    assert result["kind"] == "json"
    assert result["value"]["network"] == "cellular"
    assert called[0][0]["params"] == {"name": "control_phone_network_status", "arguments": {}}
    assert len(called) == 1


def test_post_dispatch_is_once_and_preserves_arguments(monkeypatch):
    sent = []
    async def invoke(record, timeout):
        sent.append(record)
        return {"jsonrpc": "2.0", "id": record["id"],
                "result": {"content": [{"type": "text", "text": '{"ok":true}'}]}}
    monkeypatch.setattr(rpc, "invoke", invoke)
    with app_client(monkeypatch) as client:
        resp = client.post("/phone/rpc", headers={"Authorization": "Bearer " + TOKEN},
                           json={"path": "/input", "method": "POST",
                                 "payload": {"action": "home"}})
        assert resp.status_code == 200, resp.text
    assert len(sent) == 1
    assert sent[0]["params"]["arguments"] == {"action": "home"}


def test_missing_socket_is_proven_not_dispatched(monkeypatch):
    with app_client(monkeypatch, online=False) as client:
        resp = client.post("/phone/rpc", headers={"Authorization": "Bearer " + TOKEN},
                           json={"path": "/input", "method": "POST",
                                 "payload": {"action": "home"}})
    assert resp.status_code == 503
    assert resp.json()["detail"] == {"state": "no_session", "dispatched": False}


def test_uncertain_socket_cannot_be_called_success(monkeypatch):
    async def uncertain(record, timeout):
        raise rpc.DirectPhoneUncertain("session dropped")
    monkeypatch.setattr(rpc, "invoke", uncertain)
    with app_client(monkeypatch) as client:
        resp = client.post("/phone/rpc", headers={"Authorization": "Bearer " + TOKEN},
                           json={"path": "/input", "method": "POST",
                                 "payload": {"action": "home"}})
    assert resp.status_code == 504
    assert resp.json()["detail"]["dispatched"] is True


def test_route_map_matches_android_implemented_tools():
    src = (Path(__file__).resolve().parents[1] / "android/app/src/main/java/"
           "com/asterion/control/AndroidMcp.java").read_text(encoding="utf-8")
    for name in rpc.ROUTES.values():
        assert 'case "' + name + '"' in src, name


def test_unknown_route_cannot_dispatch(monkeypatch):
    with app_client(monkeypatch) as client:
        resp = client.post("/phone/rpc", headers={"Authorization": "Bearer " + TOKEN},
                           json={"path": "/shell", "method": "POST", "payload": {}})
    assert resp.status_code == 404
    assert resp.json()["detail"]["dispatched"] is False


def test_windows_phone_bridge_uses_wss_before_private_lan(monkeypatch, tmp_path):
    monkeypatch.setattr(phone_bridge, "STATE", tmp_path / "pair.json")
    phone_bridge.STATE.write_text(json.dumps({"base_url": "http://192.168.5.8:8973",
                                                "token": TOKEN}))
    seen = []
    class Native:
        def post(self, url, json, headers, timeout):
            seen.append(("wss", json["path"]))
            return httpx.Response(200, json={"kind": "json",
                                                "value": {"network": "cellular"}})
        def request(self, *a, **kw):
            raise AssertionError("Cellular command must not dial stale LAN address")
    monkeypatch.setattr(phone_bridge, "_phone_http", Native())
    result = phone_bridge.request("/network/status").json()
    assert result["network"] == "cellular"
    assert seen == [("wss", "/network/status")]


def test_no_replay_of_uncertain_phone_post(monkeypatch, tmp_path):
    monkeypatch.setattr(phone_bridge, "STATE", tmp_path / "pair.json")
    phone_bridge.STATE.write_text(json.dumps({"base_url": "http://192.168.5.8:8973",
                                                "token": TOKEN}))
    class Lost:
        def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("socket response vanished")
        def request(self, *a, **kw):
            raise AssertionError("POST side effect must NEVER replay over LAN")
    monkeypatch.setattr(phone_bridge, "_phone_http", Lost())
    with pytest.raises(HTTPException, match="outcome unknown"):
        phone_bridge.request("/input", "POST", {"action": "home"})


def test_no_session_allows_private_lan_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(phone_bridge, "STATE", tmp_path / "pair.json")
    phone_bridge.STATE.write_text(json.dumps({"base_url": "http://192.168.5.8:8973",
                                                "token": TOKEN}))
    seen = []
    class NoSession:
        def post(self, *a, **kw):
            seen.append("native-no-session")
            return httpx.Response(503, json={"detail": {"state": "no_session",
                                                           "dispatched": False}})
        def request(self, method, url, json, headers, timeout):
            seen.append("private-lan")
            return httpx.Response(200, json={"ok": True})
    monkeypatch.setattr(phone_bridge, "_phone_http", NoSession())
    assert phone_bridge.request("/health").json()["ok"] is True
    assert seen == ["native-no-session", "private-lan"]


def test_wss_roundtrip_probe_never_falls_back_to_wifi(monkeypatch, tmp_path):
    monkeypatch.setattr(phone_bridge, "STATE", tmp_path / "pair.json")
    phone_bridge.STATE.write_text(json.dumps({"base_url":"http://192.168.5.8:8973",
                                              "token":TOKEN}))
    attempted=[]
    monkeypatch.setattr(phone_bridge, "_request_via_outbound_wss",
                        lambda *a, **kw: attempted.append("wss") or None)
    class NoLan:
        def request(self, *args, **kwargs):
            pytest.fail("Native WSS-only verification must not use private LAN")
    monkeypatch.setattr(phone_bridge, "_phone_http", NoLan())
    assert phone_bridge.probe_native_wss_roundtrip() == {
        "verified": False, "reason": "native_wss_unavailable"}
    assert attempted == ["wss"]


def test_wss_roundtrip_probe_requires_real_native_network_response(monkeypatch, tmp_path):
    monkeypatch.setattr(phone_bridge, "STATE", tmp_path / "pair.json")
    phone_bridge.STATE.write_text(json.dumps({"base_url":"http://192.168.5.8:8973",
                                              "token":TOKEN}))
    monkeypatch.setattr(phone_bridge, "_request_via_outbound_wss",
                        lambda *args, **kwargs: httpx.Response(
                            200, json={"network":"cellular","connected":True}))
    verified=phone_bridge.probe_native_wss_roundtrip()
    assert verified["verified"] is True
    assert verified["network"] == "cellular"
    assert verified["transport"] == "native_wss"
    assert verified["roundtrip_ms"] >= 0
    assert verified["observed_unix_ms"] > 0
    monkeypatch.setattr(phone_bridge, "_request_via_outbound_wss",
                        lambda *args, **kwargs: httpx.Response(200, json={"ok":True}))
    assert phone_bridge.probe_native_wss_roundtrip()["verified"] is False
