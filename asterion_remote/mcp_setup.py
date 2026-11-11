"""Show the owner the one-time ChatGPT connector setup details inside Android Asterion Control.

Never expose setup to unauthenticated callers or log the bearer secret.
The native Samsung app requires explicit user tap before this endpoint is called.
"""
from __future__ import annotations
from pathlib import Path
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from .security import require_token
from .pairing import private_peer

router=APIRouter(prefix="/api/v1",dependencies=[Depends(require_token)])

@router.post("/mcp-connection")
def owner_mcp_connection(request: Request):
    if not request.client or not private_peer(request.client.host):
        raise HTTPException(403,"Connection setup requires private LAN/VPN")
    folder=Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl"
    token_file=folder/"mcp-gateway-token.txt"
    url_file=folder/"mcp-stable-https-url.txt"
    try:
        secret=token_file.read_text("utf-8").strip()
        base=url_file.read_text("utf-8").strip().rstrip("/")
    except OSError:
        raise HTTPException(503,"Start the owner-authorized MCP gateway first")
    if (len(secret)<43 or
        base != "https://wise-eagle-c8b55706.tunnl.gg/mcp"):
        raise HTTPException(503,"MCP HTTPS setup is incomplete")
    return JSONResponse({
      "server_url":base,
      "api_key":secret,
      "kind":"private-bearer",
      "temporary":False,
       "note":"Existing stable HTTPS MCP endpoint. Never share the permanent credential."
    },headers={"Cache-Control":"no-store","Pragma":"no-cache","X-Content-Type-Options":"nosniff"})
