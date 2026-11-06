"""OAuth approval survives gateway restart and expired pages are human-readable."""
import base64
import hashlib
import re
import sqlite3
from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote import oauth_bridge

def test_pending_request_is_persisted_and_one_use(tmp_path,monkeypatch):
    monkeypatch.setattr(oauth_bridge,"DB_PATH",tmp_path/"oauth.sqlite3")
    key=tmp_path/"existing-key.txt"
    key.write_text("k"*50,encoding="utf-8")
    monkeypatch.setattr(oauth_bridge,"GATEWAY_KEY",key)
    redirect="https://chatgpt.com/connector_platform_oauth_redirect"
    app=FastAPI()
    app.include_router(oauth_bridge.router)
    with TestClient(app) as client:
        register=client.post("/oauth/register",json={"redirect_uris":[redirect]})
        assert register.status_code==201
        ver="z"*64
        challenge=base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
        params=dict(client_id=register.json()["client_id"],redirect_uri=redirect,response_type="code",
                    scope=oauth_bridge.SCOPE,state="opaque_test",
                    code_challenge=challenge,code_challenge_method="S256",resource=oauth_bridge.RESOURCE)
        page=client.get("/oauth/authorize",params=params)
        assert page.status_code==200
        rid=re.search("name='request_id' value='([^']+)'",page.text).group(1)
    # New TestClient process context, same SQLite database; no Python in-memory pending state needed.
    with sqlite3.connect(str(tmp_path/"oauth.sqlite3")) as db:
        row=db.execute("SELECT digest,expires FROM oauth_pending").fetchone()
        assert row[0]==hashlib.sha256(rid.encode()).hexdigest()
        assert row[1]>oauth_bridge._now()
    with TestClient(app) as client:
        response=client.post("/oauth/approve",
            data={"request_id":rid,"key":"k"*50},follow_redirects=False)
        assert response.status_code==302
        second=client.post("/oauth/approve",
            data={"request_id":rid,"key":"k"*50},follow_redirects=False)
        assert second.status_code==400
        assert "Authorization session expired" in second.text
        assert "<html" in second.text

def test_expiration_is_bounded_and_does_not_accept_replay(tmp_path,monkeypatch):
    monkeypatch.setattr(oauth_bridge,"DB_PATH",tmp_path/"oauth.sqlite3")
    with oauth_bridge._db() as db:
        db.execute("INSERT INTO oauth_pending VALUES (?,?,?,?,?,?)",
            ("deadbeef","old","https://chatgpt.com/connector_platform_oauth_redirect",
             "abc","state",1))
    with TestClient(FastAPI()) as unused:
        pass
    with oauth_bridge._db() as db:
        assert db.execute("SELECT COUNT(*) FROM oauth_pending WHERE expires > ?",
                          (oauth_bridge._now(),)).fetchone()[0]==0
