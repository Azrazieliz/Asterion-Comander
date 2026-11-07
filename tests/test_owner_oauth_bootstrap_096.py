"""Owner-approved one-time OAuth bootstrap on registered Android, with replay protection."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from asterion_remote import oauth_bridge, phone_live, phone_bridge

def client(tmp_path,monkeypatch,registered="native-"+"a"*44,connected=True):
    monkeypatch.setattr(oauth_bridge,"DB_PATH",tmp_path/"oauth-test.sqlite3")
    private=tmp_path/"owner-gateway-key.txt"
    private.write_text("g"*48,encoding="utf-8")
    monkeypatch.setattr(oauth_bridge,"GATEWAY_KEY",private)
    monkeypatch.setattr(phone_bridge,"load",lambda:{"token":registered})
    monkeypatch.setattr(phone_live,"connected",lambda:connected)
    app=FastAPI()
    app.include_router(oauth_bridge.router)
    return TestClient(app)

def test_native_owner_can_issue_one_use_code_on_cellular(tmp_path,monkeypatch):
    token="native-"+"a"*44
    with client(tmp_path,monkeypatch,registered=token) as c:
        response=c.post("/oauth/phone-approval",
            headers={"Authorization":"Bearer "+token})
        assert response.status_code==200
        body=response.json()
        assert body["one_time"] is True and body["expires_in"]==600
        assert body["server_url"]=="https://wise-eagle-c8b55706.tunnl.gg/mcp"
        code=body["authorization_code"]
        assert 32<=len(code)<=256
        assert oauth_bridge._owner_key_valid(code)
        assert not oauth_bridge._owner_key_valid(code)
        assert oauth_bridge._owner_key_valid("g"*48)

def test_public_bootstrap_rejects_absent_or_invalid_registration(tmp_path,monkeypatch):
    token="native-"+"a"*44
    with client(tmp_path,monkeypatch,registered=token) as c:
        assert c.post("/oauth/phone-approval").status_code==401
        assert c.post("/oauth/phone-approval",
            headers={"Authorization":"Bearer "+("x"*48)}).status_code==401

def test_bootstrap_needs_active_device_and_limits_codes(tmp_path,monkeypatch):
    token="native-"+"a"*44
    with client(tmp_path,monkeypatch,registered=token,connected=False) as c:
        assert c.post("/oauth/phone-approval",
            headers={"Authorization":"Bearer "+token}).status_code==401
    with client(tmp_path,monkeypatch,registered=token) as c:
        for _ in range(3):
            assert c.post("/oauth/phone-approval",
                headers={"Authorization":"Bearer "+token}).status_code==200
        assert c.post("/oauth/phone-approval",
            headers={"Authorization":"Bearer "+token}).status_code==429

def test_expired_approval_not_accepted(tmp_path,monkeypatch):
    token="native-"+"a"*44
    with client(tmp_path,monkeypatch,registered=token) as c:
        r=c.post("/oauth/phone-approval",
            headers={"Authorization":"Bearer "+token})
        code=r.json()["authorization_code"]
        monkeypatch.setattr(oauth_bridge,"_now",lambda:10**12)
        assert not oauth_bridge._owner_key_valid(code)

def test_bootstrap_server_uses_stable_gateway_and_no_raw_secret_over_cellular():
    root=Path(__file__).resolve().parents[1]
    src=(root/"asterion_remote/mcp_setup.py").read_text()
    android=(root/"android/app/src/main/java/com/asterion/control/MainActivity.java").read_text()
    assert "mcp-stable-https-url.txt" in src
    assert 'mcp-tunnel-url.txt' not in src
    assert "trycloudflare.com" not in src
    assert 'AgentService.token(this)' in android
    assert 'One-time Control approval' not in android
    assert 'Copy connection key' not in android
    assert 'Check direct Control link' in android
    assert 'One-time mobile approval unavailable:' in android
    assert "phone_live" not in src
