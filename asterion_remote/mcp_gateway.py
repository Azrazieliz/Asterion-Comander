"""Asterion Control MCP-only ingress for a HTTPS tunnel.

Security boundaries:
- binds ONLY loopback; TLS termination belongs to an outbound HTTPS tunnel
- exposes solely POST /mcp, no Windows REST API and no screen streaming URLs
- independent random bearer token (never embed credentials in the plugin ZIP)
- forwards to already-authenticated Windows Control MCP over the private loopback/LAN
- the native Android agent remains the principal device; Windows relays to it
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
GATEWAY_KEY = ROOT / "mcp-gateway-token.txt"
AGENT_KEY = ROOT / "control-token.txt"
UPSTREAM = os.environ.get("ASTERION_CONTROL_UPSTREAM", "http://192.168.1.133:8911/mcp")
LIMIT = 2_000_000
app = FastAPI(title="Asterion Control MCP-only ingress", docs_url=None, redoc_url=None, openapi_url=None)

def _secret(path: Path) -> str:
    try:
        s=path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"MCP gateway credential file missing: {path.name}") from exc
    if len(s) < 43:
        raise RuntimeError("MCP gateway credential too short")
    return s

@app.on_event("startup")
def verify_secret_files():
    _secret(GATEWAY_KEY)
    _secret(AGENT_KEY)
    if UPSTREAM not in ("http://127.0.0.1:8911/mcp","http://192.168.1.133:8911/mcp"):
        raise RuntimeError("MCP upstream must be the fixed authorized Windows Control agent")

@app.post("/mcp")
async def rpc(req: Request):
    header=req.headers.get("authorization","")
    if not header.startswith("Bearer ") or not hmac.compare_digest(
        header[7:].encode(),_secret(GATEWAY_KEY).encode()
    ):
        raise HTTPException(401,detail="Asterion Control authorization required",
            headers={"WWW-Authenticate":"Bearer"})
    accepted=req.headers.get("accept","")
    if "application/json" not in accepted or "text/event-stream" not in accepted:
        raise HTTPException(406,"Accept must contain application/json and text/event-stream")
    size=int(req.headers.get("content-length") or 0)
    if size>LIMIT: raise HTTPException(413,"Request too large")
    payload=await req.body()
    if len(payload)>LIMIT: raise HTTPException(413,"Request too large")
    headers={"Authorization":"Bearer "+_secret(AGENT_KEY),
             "Content-Type":"application/json",
             "Accept":"application/json, text/event-stream"}
    for k in ("mcp-protocol-version","mcp-session-id"):
        if v:=req.headers.get(k):headers[k]=v
    try:
        async with httpx.AsyncClient(timeout=20.0,trust_env=False,follow_redirects=False) as client:
            upstream=await client.post(UPSTREAM,content=payload,headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(503,detail="Authorized Control agent unavailable: "+type(e).__name__) from e
    body=upstream.content
    if len(body)>8_000_000:raise HTTPException(502,"Excessively large agent response")
    forwarded={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}
    if sid:=upstream.headers.get("mcp-session-id"):forwarded["Mcp-Session-Id"]=sid
    return Response(content=body,status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type","application/json"),
                    headers=forwarded)

@app.get("/mcp")
@app.delete("/mcp")
async def no_sse():
    return Response(status_code=405,headers={"Allow":"POST"})

@app.get("/healthz")
def health():
    return {"service":"asterion-control-mcp-gateway","ok":True,"version":1}
