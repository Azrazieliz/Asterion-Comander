"""OAuth connection, consent and token-rotation regression tests."""
import base64
import hashlib
import importlib
import re
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

def test_oauth_discovery_owner_approval_and_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from asterion_remote import oauth_bridge
    importlib.reload(oauth_bridge)
    key = oauth_bridge.GATEWAY_KEY
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text("x" * 50)
    app = FastAPI()
    app.include_router(oauth_bridge.router)
    client = TestClient(app)
    discovery = client.get("/.well-known/oauth-protected-resource/mcp")
    assert discovery.status_code == 200
    assert discovery.json()["resource"] == oauth_bridge.RESOURCE
    info = client.get("/.well-known/oauth-authorization-server").json()
    assert info["code_challenge_methods_supported"] == ["S256"]
    assert info["authorization_response_iss_parameter_supported"]
    redirect = "https://chatgpt.com/connector_platform_oauth_redirect"
    assert client.post("/oauth/register", json={"redirect_uris": ["https://evil.invalid"]}).status_code == 400
    register = client.post("/oauth/register", json={"redirect_uris": [redirect]})
    assert register.status_code == 201
    client_id = register.json()["client_id"]
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = dict(client_id=client_id, redirect_uri=redirect, response_type="code",
                  scope="asterion.control offline_access", state="opaque", code_challenge=challenge,
                  code_challenge_method="S256", resource=oauth_bridge.RESOURCE)
    approval_page = client.get("/oauth/authorize", params=params)
    assert approval_page.status_code == 200
    request_id = re.search("name='request_id' value='([^']+)'", approval_page.text).group(1)
    assert client.post("/oauth/approve", data={"request_id": request_id, "key": "bad"}).status_code == 403
    redirect_reply = client.post("/oauth/approve", data={"request_id": request_id, "key": "x" * 50}, follow_redirects=False)
    assert redirect_reply.status_code == 302
    query = parse_qs(urlsplit(redirect_reply.headers["location"]).query)
    assert query["iss"] == [oauth_bridge.ORIGIN]
    token_response = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "client_id": client_id, "redirect_uri": redirect,
        "code": query["code"][0], "code_verifier": verifier, "resource": oauth_bridge.RESOURCE})
    assert token_response.status_code == 200
    access = token_response.json()["access_token"]
    assert oauth_bridge.valid_access(access)
    assert not oauth_bridge.valid_access("invalid")
    refreshed = client.post("/oauth/token", data={
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": token_response.json()["refresh_token"]})
    assert refreshed.status_code == 200
    assert oauth_bridge.valid_access(refreshed.json()["access_token"])
    assert client.post("/oauth/token", data={
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": token_response.json()["refresh_token"]}).status_code == 400
