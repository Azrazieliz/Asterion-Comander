"""End to end registered phone one-time code for an OAuth request."""
import base64,hashlib,re
from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote import oauth_bridge,phone_live,phone_bridge

def test_phone_generated_approval_completes_authorize(tmp_path,monkeypatch):
    token="native-"+("d"*44)
    key=tmp_path/"gateway.txt"
    key.write_text("g"*48,encoding="utf8")
    monkeypatch.setattr(oauth_bridge,"DB_PATH",tmp_path/"oauth.sqlite3")
    monkeypatch.setattr(oauth_bridge,"GATEWAY_KEY",key)
    monkeypatch.setattr(phone_bridge,"load",lambda:{"token":token})
    monkeypatch.setattr(phone_live,"connected",lambda:True)
    app=FastAPI();app.include_router(oauth_bridge.router)
    with TestClient(app) as c:
        redirect="https://chatgpt.com/connector_platform_oauth_redirect"
        cid=c.post("/oauth/register",json={"redirect_uris":[redirect]}).json()["client_id"]
        ver="j"*64
        ch=base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
        a=c.get("/oauth/authorize",params={
            "client_id":cid,"redirect_uri":redirect,"response_type":"code",
            "scope":oauth_bridge.SCOPE,"state":"opaque",
            "code_challenge":ch,"code_challenge_method":"S256","resource":oauth_bridge.RESOURCE})
        assert a.status_code==200
        rid=re.search("name='request_id' value='([^']+)'",a.text).group(1)
        p=c.post("/oauth/phone-approval",headers={"Authorization":"Bearer "+token})
        assert p.status_code==200
        once=p.json()["authorization_code"]
        res=c.post("/oauth/approve",data={"request_id":rid,"key":once},follow_redirects=False)
        assert res.status_code==302
        assert res.headers["location"].startswith(redirect+"?")
        assert c.post("/oauth/approve",data={"request_id":rid,"key":once}).status_code==400
