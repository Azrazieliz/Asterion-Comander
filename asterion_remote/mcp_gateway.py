"""Asterion Control authenticated MCP-only gateway.

The gateway is an HTTPS tunnel ingress, not an AI or an application engine.
Prefer the already paired Samsung's native MCP endpoint for phone operations;
preserve optional Windows Control tools through its distinct local agent.
Android still needs an independent, stable HTTPS ingress before Windows can go.
"""
from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import os
from urllib.parse import urlsplit
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .phone_bridge import load as load_phone

ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
GATEWAY_KEY = ROOT / "mcp-gateway-token.txt"
WINDOWS_AGENT_KEY = ROOT / "control-token.txt"
# The Windows worker is optional; Android-only MCP must start without it.
# Never pin the route to a single private router's DHCP address.
WINDOWS_UPSTREAM = os.environ.get("ASTERION_CONTROL_UPSTREAM", "")
NATIVE_PHONE_PREFIXES = (
    "control_phone_status",
    "control_phone_health",
    "control_phone_screen",
    "control_phone_ui",
    "control_phone_input",
    "control_phone_apps",
    "control_phone_app_launch",
    "control_phone_chat_new",
    "control_phone_continuation_",
    "control_phone_observation_",
    "control_phone_voice_",
    "control_phone_cycle_",
    "control_phone_network_status",
)
MAX_REQUEST = 2_000_000
MAX_RESPONSE = 8_000_000
app = FastAPI(
    title="Asterion Control MCP-only gateway", docs_url=None,
    redoc_url=None, openapi_url=None
)

def _secret(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"MCP gateway credential unavailable: {path.name}") from exc
    if len(value) < 43:
        raise RuntimeError("MCP gateway bearer credential is too short")
    return value

def _phone_route():
    pairing = load_phone()  # already restricted to a private IPv4/IPv6 or VPN IP
    if not pairing:
        return None
    return pairing["base_url"] + "/mcp", pairing["token"]

def _validate_windows_route(url: str) -> str:
    parsed = urlsplit(url)
    try:
        ip = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid native Control agent route") from exc
    cgnat = ip in ipaddress.ip_network("100.64.0.0/10")
    if (parsed.scheme != "http" or port != 8911 or
        parsed.path != "/mcp" or parsed.query or parsed.fragment or
        parsed.username or parsed.password or
        ip.is_unspecified or ip.is_multicast or ip.is_link_local or
        not (ip.is_private or ip.is_loopback or cgnat)):
        raise RuntimeError("Windows MCP route must use a private Control IP")
    host = "[" + str(ip) + "]" if ip.version == 6 else str(ip)
    return "http://" + host + ":8911/mcp"

def _windows_route():
    if WINDOWS_UPSTREAM:
        url = _validate_windows_route(WINDOWS_UPSTREAM)
    else:
        from .github_bridge_git import agent_host
        try:
            url = _validate_windows_route(agent_host() + "/mcp")
        except RuntimeError:
            return None
    try:
        token = _secret(WINDOWS_AGENT_KEY)
    except RuntimeError:
        return None
    return url, token

@app.on_event("startup")
def verify_gateway():
    _secret(GATEWAY_KEY)
    # Explicit custom upstreams are validated, but Windows is not mandatory.
    if WINDOWS_UPSTREAM:
        _validate_windows_route(WINDOWS_UPSTREAM)

async def _forward(route, payload: bytes, request_headers: dict):
    url, token = route
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    for key in ("mcp-protocol-version", "mcp-session-id"):
        value = request_headers.get(key)
        if value:
            headers[key] = value
    async with httpx.AsyncClient(
        timeout=20.0, trust_env=False, follow_redirects=False
    ) as client:
        response = await client.post(url, content=payload, headers=headers)
    if len(response.content) > MAX_RESPONSE:
        raise HTTPException(502, "MCP upstream exceeded response limit")
    return response

def _response(upstream):
    extra = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if sid := upstream.headers.get("mcp-session-id"):
        extra["Mcp-Session-Id"] = sid
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers=extra,
    )

def _tool_is_native(name: str):
    return name in NATIVE_PHONE_PREFIXES or any(
        name.startswith(prefix) for prefix in NATIVE_PHONE_PREFIXES
        if prefix.endswith("_")
    )

async def _preferred(payload: bytes, headers: dict, phone_first=True):
    candidates = []
    if phone_first:
        if paired := _phone_route():
            candidates.append(paired)
        try:
            if route := _windows_route():
                candidates.append(route)
        except RuntimeError:
            pass
    else:
        try:
            if route := _windows_route():
                candidates.append(route)
        except RuntimeError:
            pass
        if paired := _phone_route():
            candidates.append(paired)
    for route in candidates:
        try:
            response = await _forward(route, payload, headers)
            if response.status_code in (200, 202):
                return response
        except httpx.HTTPError:
            continue
    raise HTTPException(503, "No authorized native Control MCP upstream reachable")

@app.post("/mcp")
async def rpc(req: Request):
    bearer = req.headers.get("authorization", "")
    if not bearer.startswith("Bearer ") or not hmac.compare_digest(
        bearer[7:].encode(), _secret(GATEWAY_KEY).encode()
    ):
        raise HTTPException(
            401, "Asterion Control authorization required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    accepted = req.headers.get("accept", "")
    if "application/json" not in accepted or "text/event-stream" not in accepted:
        raise HTTPException(406, "MCP requires JSON and event-stream Accept")
    try:
        length = int(req.headers.get("content-length") or "0")
    except ValueError:
        raise HTTPException(400, "Malformed content length")
    if length > MAX_REQUEST:
        raise HTTPException(413, "MCP request too large")
    payload = await req.body()
    if len(payload) > MAX_REQUEST:
        raise HTTPException(413, "MCP request too large")
    try:
        message = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid JSON-RPC body")
    if not isinstance(message, dict):
        raise HTTPException(400, "A single MCP JSON-RPC object is required")
    method = message.get("method")
    name = (message.get("params") or {}).get("name") if isinstance(message.get("params"), dict) else ""
    if method == "tools/call":
        from . import phone_cloud_relay
        params = message.get("params") or {}
        if name == "control_phone_cloud_receipt":
            args = params.get("arguments") or {}
            if not isinstance(args, dict) or not isinstance(args.get("id"), str):
                raise HTTPException(422, "A private Control receipt ID is required")
            try:
                answer = await phone_cloud_relay.receipt(args["id"], message.get("id"))
            except (RuntimeError, ValueError, httpx.HTTPError):
                raise HTTPException(503, "Private phone receipt is not accessible")
            return Response(content=json.dumps(answer), media_type="application/json",
                            headers={"Cache-Control":"no-store"})
        native = isinstance(name, str) and _tool_is_native(name)
        if native:
            # Try LAN/VPN briefly. Do not wait for a timeout against an address
            # that the Samsung has left when it switched to cellular.
            if paired := _phone_route():
                try:
                    direct = await asyncio.wait_for(
                        _forward(paired,payload,req.headers),timeout=4.0)
                    if direct.status_code == 200:
                        # MCP application errors are definitive results. Retrying
                        # after one would duplicate a side-effecting operation.
                        parsed = json.loads(direct.content)
                        if isinstance(parsed,dict) and parsed.get("jsonrpc")=="2.0":
                            return _response(direct)
                    if direct.status_code not in (502,503,504):
                        return _response(direct)
                except (httpx.ConnectError,httpx.ConnectTimeout):
                    # Failed before a connection was established: cloud retry safe.
                    pass
                except (asyncio.TimeoutError,httpx.ReadTimeout,httpx.RemoteProtocolError):
                    raise HTTPException(504,
                        "Native Control command outcome uncertain; will not replay")
                except (ValueError,):
                    raise HTTPException(502,"Native Control returned invalid MCP JSON")
            # The existing private GitHub bridge is outbound HTTPS from Android.
            # It operates on mobile data with a separately authorized repo token.
            try:
                args = params.get("arguments") or {}
                answer = await phone_cloud_relay.submit(name,args,message.get("id"))
                return Response(content=json.dumps(answer),media_type="application/json",
                                headers={"Cache-Control":"no-store"})
            except (RuntimeError,ValueError,httpx.HTTPError):
                pass
        upstream = await _preferred(payload, req.headers, phone_first=native)
        return _response(upstream)
    if method == "tools/list":
        # Merge the phone and optional Windows tool catalogues. A phone-owned
        # tool name wins over its older Windows proxy with the same name.
        catalogs = []
        for route in (_phone_route(),):
            if route is None:
                continue
            try:
                response = await _forward(route, payload, req.headers)
                if response.status_code == 200:
                    catalogs.append(json.loads(response.content))
            except (httpx.HTTPError, ValueError):
                pass
        try:
            route = _windows_route()
            if route is not None:
                response = await _forward(route, payload, req.headers)
                if response.status_code == 200:
                    catalogs.append(json.loads(response.content))
        except (RuntimeError, httpx.HTTPError, ValueError):
            pass
        if not catalogs:
            # Discovery must remain available on cellular when the phone is
            # temporarily unreachable or the Windows worker is switched off.
            # This is a STATIC tool schema, NOT a false availability claim:
            # each tool still returns an explicit pending/offline result.
            from .mcp_protocol import TOOLS
            catalogs=[{"result":{"tools":TOOLS}}]
        merged = {}
        # Reverse so the first/native catalogue wins.
        for item in reversed(catalogs):
            for spec in item.get("result", {}).get("tools", []):
                if isinstance(spec, dict) and isinstance(spec.get("name"), str):
                    merged[spec["name"]] = spec
        merged["control_phone_cloud_receipt"]={
            "name":"control_phone_cloud_receipt",
            "description":"Retrieve a durable result for an offsite Android command using its pending ID",
            "inputSchema":{"type":"object","properties":{"id":{"type":"string"}},
                           "required":["id"]}
        }
        response = {
            "jsonrpc": "2.0", "id": message.get("id"),
            "result": {"tools": list(merged.values())},
        }
        return Response(content=json.dumps(response), media_type="application/json",
                        headers={"Cache-Control": "no-store"})
    if method == "initialize":
        return Response(content=json.dumps({
            "jsonrpc":"2.0","id":message.get("id"),
            "result":{"protocolVersion":"2025-11-25",
                      "capabilities":{"tools":{}},
                      "serverInfo":{"name":"asterion-control","version":"0.9.0"}}
        }),media_type="application/json",headers={"Cache-Control":"no-store"})
    if method == "ping":
        return Response(content=json.dumps({
            "jsonrpc":"2.0","id":message.get("id"),"result":{}
        }),media_type="application/json",headers={"Cache-Control":"no-store"})
    return _response(await _preferred(payload, req.headers, phone_first=True))

@app.get("/mcp")
@app.delete("/mcp")
async def no_sse():
    return Response(status_code=405, headers={"Allow": "POST"})

@app.get("/healthz")
def health():
    return {"service": "asterion-control-mcp-gateway", "ok": True, "version": 2}
