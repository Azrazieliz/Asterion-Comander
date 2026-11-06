"""Owner-approved OAuth 2.1 bridge for the existing Asterion Control MCP gateway.

This supplements (does not replace) the original gateway bearer key. OAuth
access requires an owner's explicit approval using that key. Tokens and keys
are never included in repository files.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

ORIGIN = os.getenv("ASTERION_CONTROL_MCP_ORIGIN", "https://wise-eagle-c8b55706.tunnl.gg").rstrip("/")
RESOURCE = ORIGIN + "/mcp"
SCOPE = "asterion.control"
ROOT = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
DB_PATH = ROOT / "mcp-oauth.sqlite3"
GATEWAY_KEY = ROOT / "mcp-gateway-token.txt"
router = APIRouter()
_lock = threading.RLock()
_pending: dict[str, dict] = {}
_failed: dict[str, tuple[int, int]] = {}

def _now() -> int:
    return int(time.time())

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def _db():
    ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=5)
    db.execute("CREATE TABLE IF NOT EXISTS clients (client_id TEXT PRIMARY KEY, redirects TEXT NOT NULL, created INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS codes (digest TEXT PRIMARY KEY, client_id TEXT, redirect TEXT, challenge TEXT, resource TEXT, expires INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS tokens (digest TEXT PRIMARY KEY, kind TEXT, client_id TEXT, resource TEXT, expires INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS owner_approvals (digest TEXT PRIMARY KEY, expires INTEGER NOT NULL)")
    # Older releases called these columns hash/redirect_uri/redirect_uris.
    # SQLite CREATE IF NOT EXISTS does not change existing tables. Migrate
    # column names without dropping any client, authorization code or token.
    for table, legacy, canonical in (
        ("clients","redirect_uris","redirects"),
        ("codes","hash","digest"),
        ("codes","redirect_uri","redirect"),
        ("tokens","hash","digest"),
    ):
        columns={row[1] for row in db.execute("PRAGMA table_info("+table+")")}
        if legacy in columns and canonical not in columns:
            db.execute("ALTER TABLE "+table+" RENAME COLUMN "+legacy+" TO "+canonical)
    db.commit()
    return db

def _callback_ok(uri: str) -> bool:
    try:
        u = urlsplit(uri)
        return (u.scheme == "https" and u.hostname == "chatgpt.com" and
                u.port is None and not u.username and not u.password and
                not u.query and not u.fragment and
                (u.path == "/connector_platform_oauth_redirect" or
                 (u.path.startswith("/connector/oauth/") and len(u.path) > len("/connector/oauth/"))))
    except (ValueError, TypeError):
        return False

def _resource_ok(value: str) -> bool:
    return value in ("", RESOURCE, ORIGIN)

def _form(body: bytes) -> dict:
    if len(body) > 32768:
        raise HTTPException(413, "OAuth request too large")
    try:
        return {k: values[-1] for k, values in parse_qs(body.decode(), keep_blank_values=True, max_num_fields=24).items()}
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Invalid OAuth form")

def _owner_key_valid(candidate: str) -> bool:
    if not isinstance(candidate, str) or not (32 <= len(candidate) <= 256):
        return False
    # Continue accepting the original owner's gateway key via the existing
    # OAuth form; do not rotate it, disclose it, or change prior pairing.
    try:
        expected = GATEWAY_KEY.read_text(encoding="utf-8").strip()
    except OSError:
        expected = ""
    if len(expected) >= 43 and hmac.compare_digest(candidate.encode(), expected.encode()):
        return True
    # Owner-requested mobile approvals are one-use and expire after ten minutes.
    # Store only the digest, not a reusable device or gateway credential.
    with _lock, _db() as db:
        now = _now()
        db.execute("DELETE FROM owner_approvals WHERE expires <= ?", (now,))
        digest = _hash(candidate)
        row = db.execute("SELECT expires FROM owner_approvals WHERE digest=?", (digest,)).fetchone()
        if row and row[0] > now:
            db.execute("DELETE FROM owner_approvals WHERE digest=?", (digest,))
            return True
    return False


@router.post("/oauth/phone-approval")
def phone_approval(request: Request):
    """Phone-owner-tapped bootstrap: mobile data works; no permanent secret leaves gateway."""
    from .phone_live import connected
    from .phone_bridge import load as load_registered_phone
    bearer = request.headers.get("authorization", "")
    candidate = bearer[7:] if bearer.startswith("Bearer ") else ""
    record = load_registered_phone()
    registered = record.get("token") if isinstance(record, dict) else None
    if (not isinstance(registered, str) or len(registered) < 32 or
            not isinstance(candidate, str) or len(candidate) != len(registered) or
            not hmac.compare_digest(candidate.encode(), registered.encode()) or
            not connected()):
        raise HTTPException(401, "An actively connected registered Android owner is required")
    code = secrets.token_urlsafe(32)
    with _lock, _db() as db:
        now = _now()
        db.execute("DELETE FROM owner_approvals WHERE expires <= ?", (now,))
        outstanding = db.execute("SELECT COUNT(*) FROM owner_approvals").fetchone()[0]
        if outstanding >= 3:
            raise HTTPException(429, "Too many outstanding owner approvals")
        db.execute("INSERT INTO owner_approvals (digest,expires) VALUES (?,?)",
                   (_hash(code), now + 600))
    return JSONResponse({
        "server_url": RESOURCE,
        "authorization_code": code,
        "expires_in": 600,
        "one_time": True,
    }, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})



def challenge() -> str:
    return f'Bearer resource_metadata="{ORIGIN}/.well-known/oauth-protected-resource", scope="{SCOPE}", error="invalid_token"'

def valid_access(token: str) -> bool:
    if not token or len(token) > 256:
        return False
    with _lock, _db() as db:
        row = db.execute("SELECT expires FROM tokens WHERE digest=? AND kind='access' AND resource=?",
                         (_hash(token), RESOURCE)).fetchone()
    return bool(row and row[0] > _now())

@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
def resource_metadata():
    return JSONResponse({"resource": RESOURCE, "authorization_servers": [ORIGIN],
                         "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"]},
                        headers={"Cache-Control": "no-store"})

@router.get("/.well-known/oauth-authorization-server")
def authorization_metadata():
    return JSONResponse({"issuer": ORIGIN,
                         "authorization_endpoint": ORIGIN + "/oauth/authorize",
                         "token_endpoint": ORIGIN + "/oauth/token",
                         "registration_endpoint": ORIGIN + "/oauth/register",
                         "authorization_response_iss_parameter_supported": True,
                         "response_types_supported": ["code"],
                         "grant_types_supported": ["authorization_code", "refresh_token"],
                         "token_endpoint_auth_methods_supported": ["none"],
                         "code_challenge_methods_supported": ["S256"],
                         "scopes_supported": [SCOPE, "offline_access"]},
                        headers={"Cache-Control": "no-store"})

@router.post("/oauth/register")
async def register(request: Request):
    raw = await request.body()
    if len(raw) > 32768:
        raise HTTPException(413, "Registration request too large")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Invalid OAuth client")
    if not isinstance(body, dict):
        raise HTTPException(400, "Invalid OAuth client")
    redirects = body.get("redirect_uris")
    if not isinstance(redirects, list) or not (1 <= len(redirects) <= 4) or any(
            not isinstance(x, str) or not _callback_ok(x) for x in redirects):
        raise HTTPException(400, "Only known ChatGPT redirect URIs are supported")
    if body.get("token_endpoint_auth_method", "none") != "none":
        raise HTTPException(400, "PKCE public clients only")
    client_id = "asterion_" + secrets.token_urlsafe(24)
    with _lock, _db() as db:
        db.execute("INSERT INTO clients VALUES (?,?,?)", (client_id, json.dumps(redirects), _now()))
    return JSONResponse({"client_id": client_id, "client_id_issued_at": _now(),
                         "redirect_uris": redirects, "client_name": "ChatGPT Asterion Control",
                         "grant_types": ["authorization_code", "refresh_token"],
                         "response_types": ["code"], "token_endpoint_auth_method": "none"},
                        status_code=201, headers={"Cache-Control": "no-store"})

@router.get("/oauth/authorize")
def authorize(client_id: str = "", redirect_uri: str = "", response_type: str = "",
              scope: str = "", state: str = "", code_challenge: str = "",
              code_challenge_method: str = "", resource: str = ""):
    if not (response_type == "code" and code_challenge_method == "S256" and
            43 <= len(code_challenge) <= 128 and all(c.isalnum() or c in "-_" for c in code_challenge) and
            SCOPE in scope.split() and _resource_ok(resource) and
            _callback_ok(redirect_uri) and 0 < len(state) <= 2048):
        raise HTTPException(400, "Invalid OAuth authorization request")
    with _lock, _db() as db:
        row = db.execute("SELECT redirects FROM clients WHERE client_id=?", (client_id,)).fetchone()
        if not row or redirect_uri not in json.loads(row[0]):
            raise HTTPException(400, "ChatGPT client not registered")
        request_id = secrets.token_urlsafe(32)
        _pending[request_id] = {"client_id": client_id, "redirect": redirect_uri,
                                "challenge": code_challenge, "state": state,
                                "expires": _now() + 600}
        for key, value in list(_pending.items()):
            if value["expires"] < _now():
                _pending.pop(key, None)
    rid = html.escape(request_id, quote=True)
    page = ("<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Asterion Control authorization</title><style>body{font:16px system-ui;"
            "max-width:480px;margin:7vh auto;padding:18px}input,button{box-sizing:border-box;"
            "width:100%;padding:12px;margin:12px 0}button{background:#4338ca;color:white}"
            "</style></head><body><h2>Authorize Asterion Control</h2>"
            "<p>Approve ChatGPT access to your already-paired devices. "
            "On your Samsung, open Asterion Control &gt; Devices &gt; "
            "Authorize ChatGPT (one-time code), then copy the temporary code.</p>"
            "<form action='/oauth/approve' method='post'>"
            f"<input type='hidden' name='request_id' value='{rid}'>"
            "<label>One-time phone approval code (or existing gateway key)"
            "<input type='password' name='key' required autocomplete='off'></label>"
            "<button type='submit'>Authorize ChatGPT</button></form>"
            "<p>The phone code expires after 10 minutes and is valid once. "
            "Never enter your code or gateway key in ChatGPT messages.</p></body></html>")
    return HTMLResponse(page, headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                  "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"})

@router.post("/oauth/approve")
async def approve(request: Request):
    form = _form(await request.body())
    rid = form.get("request_id", "")
    remote = request.client.host if request.client else "unknown"
    with _lock:
        attempts, blocked_until = _failed.get(remote, (0, 0))
        if attempts >= 5 and blocked_until > _now():
            raise HTTPException(429, "Too many authorization attempts")
        pending = _pending.get(rid)
        if not pending or pending["expires"] < _now():
            raise HTTPException(400, "Authorization expired")
        if not _owner_key_valid(form.get("key", "")):
            _failed[remote] = (attempts + 1, _now() + 900)
            raise HTTPException(403, "Owner approval rejected")
        _failed.pop(remote, None)
        _pending.pop(rid, None)
        code = secrets.token_urlsafe(48)
        with _db() as db:
            db.execute("INSERT INTO codes VALUES (?,?,?,?,?,?)",
                       (_hash(code), pending["client_id"], pending["redirect"],
                        pending["challenge"], RESOURCE, _now() + 120))
    return RedirectResponse(pending["redirect"] + "?" + urlencode(
        {"code": code, "state": pending["state"], "iss": ORIGIN}),
        status_code=302, headers={"Cache-Control": "no-store"})

@router.post("/oauth/token")
async def token(request: Request):
    form = _form(await request.body())
    client_id = form.get("client_id", "")
    if not client_id:
        raise HTTPException(400, "OAuth client_id missing")
    with _lock, _db() as db:
        if form.get("grant_type") == "authorization_code":
            digest = _hash(form.get("code", ""))
            row = db.execute("SELECT client_id,redirect,challenge,resource,expires FROM codes WHERE digest=?",
                             (digest,)).fetchone()
            db.execute("DELETE FROM codes WHERE digest=?", (digest,))
            if (not row or row[0] != client_id or row[1] != form.get("redirect_uri") or row[4] < _now()):
                raise HTTPException(400, "Authorization code invalid or expired")
            verifier = form.get("code_verifier", "")
            if not (43 <= len(verifier) <= 128):
                raise HTTPException(400, "PKCE verifier required")
            calculated = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if not hmac.compare_digest(calculated, row[2]):
                raise HTTPException(400, "PKCE verification failed")
            audience = row[3]
        elif form.get("grant_type") == "refresh_token":
            digest = _hash(form.get("refresh_token", ""))
            row = db.execute("SELECT client_id,resource,expires FROM tokens WHERE digest=? AND kind='refresh'",
                             (digest,)).fetchone()
            if not row or row[0] != client_id or row[2] < _now():
                raise HTTPException(400, "Refresh token invalid")
            db.execute("DELETE FROM tokens WHERE digest=?", (digest,))
            audience = row[1]
        else:
            raise HTTPException(400, "Grant type unsupported")
        if not _resource_ok(form.get("resource", "")):
            raise HTTPException(400, "Invalid resource audience")
        access = secrets.token_urlsafe(48)
        refresh = secrets.token_urlsafe(48)
        db.execute("INSERT INTO tokens VALUES (?,?,?,?,?)",
                   (_hash(access), "access", client_id, audience, _now() + 3600))
        db.execute("INSERT INTO tokens VALUES (?,?,?,?,?)",
                   (_hash(refresh), "refresh", client_id, audience, _now() + 2592000))
        db.execute("DELETE FROM tokens WHERE expires < ?", (_now(),))
    return JSONResponse({"access_token": access, "token_type": "Bearer", "expires_in": 3600,
                         "refresh_token": refresh, "scope": SCOPE},
                        headers={"Cache-Control": "no-store"})
