"""Authenticated GitHub MCP stdio tool surface for Asterion Intelligence.

Never resuscitates the retired Control MCP HTTP gateway. This new module is
an OWNER-CONFIGURED MCP CLIENT to the official local GitHub MCP server.

Runtime is off until a specific installed local executable, SHA256 pin,
token and tool allowlist are configured by the owner. No process launch,
network access, package installation or API call occurs at import time.
Existing GitHub relay, Android pairing, WSS and Windows worker unchanged.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .security import require_token
from .control_v2_routes import _owner_approval
from .local_mcp_client import McpServerConfig,McpStdioClient

router=APIRouter(prefix="/api/v1/intelligence/mcp",
                 dependencies=[Depends(require_token)])
_LOCK=threading.RLock()
_CLIENT:McpStdioClient|None=None
_CLIENT_KEY:str|None=None
_SHA=re.compile(r"^[a-f0-9]{64}$")
_NAME=re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")


def configured()->dict:
    binary=os.environ.get("ASTERION_GITHUB_MCP_EXECUTABLE","")
    sha=os.environ.get("ASTERION_GITHUB_MCP_BINARY_SHA256","")
    scopes=os.environ.get("ASTERION_GITHUB_MCP_ALLOWED_TOOLS","")
    token=os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN","")
    names=frozenset(x.strip() for x in scopes.split(",") if x.strip())
    eligible=(bool(binary and Path(binary).is_absolute()) and
              bool(_SHA.fullmatch(sha)) and bool(names) and bool(token))
    return {"configured":eligible,"binary":binary,"sha":sha,
            "scopes":names,"token":token,
            "protocol":os.getenv("ASTERION_GITHUB_MCP_PROTOCOL","2025-11-25")}


@router.get("/status")
def mcp_status():
    c=configured()
    # No credential/file path or tool names are exposed without second owner
    # authorization; even authorized callers get only a summary here.
    return {"ok":True,"configured":c["configured"],
            "provider":"official_github_mcp_local_stdio",
            "binary_verified":bool(_CLIENT and c["configured"]),
            "owner_allowlist_size":len(c["scopes"]),
            "retired_control_gateway_restarted":False,
            "paid_cloud_required":False}


def _get_client()->McpStdioClient:
    global _CLIENT,_CLIENT_KEY
    c=configured()
    if not c["configured"]:
        raise HTTPException(503,"Owner-configured local GitHub MCP server unavailable")
    # Credentials are never incorporated into keys, returned or logged. Config
    # changes require explicit restart by the owner rather than mixing tokens.
    key=c["binary"]+"|"+c["sha"]+"|"+c["protocol"]+"|"+",".join(sorted(c["scopes"]))
    with _LOCK:
        if _CLIENT is not None and key != _CLIENT_KEY:
            _CLIENT.close()
            _CLIENT=None
            _CLIENT_KEY=None
        if _CLIENT is None:
            try:
                config=McpServerConfig(
                    executable=Path(c["binary"]),sha256=c["sha"],
                    arguments=("stdio",),
                    tools_allowed=c["scopes"],
                    inherited_env={"GITHUB_PERSONAL_ACCESS_TOKEN":c["token"]},
                    protocol=c["protocol"],timeout_s=20)
                client=McpStdioClient(config)
                client.start()
                _CLIENT=client
                _CLIENT_KEY=key
            except (ValueError, OSError, RuntimeError, TimeoutError) as exc:
                raise HTTPException(
                    503,"Local GitHub MCP unavailable: "+
                    type(exc).__name__) from exc
        return _CLIENT


@router.get("/tools")
def mcp_tools(x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:
        with _LOCK:
            return _get_client().list_tools()
    except HTTPException:raise
    except Exception as exc:
        raise HTTPException(503,"MCP catalog unavailable: "+type(exc).__name__) from exc


class McpCall(BaseModel):
    tool_name:str=Field(pattern=r"^[A-Za-z0-9_.:/-]{1,128}$")
    arguments:dict=Field(default_factory=dict)


@router.post("/call")
def mcp_call(body:McpCall,
             x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:
        with _LOCK:
            client=_get_client()
            # Tool discovery and per-tool owner scopes are separate checks.
            client.list_tools()
            return client.call_tool(body.tool_name,body.arguments)
    except PermissionError as exc:
        raise HTTPException(403,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422,type(exc).__name__) from exc
    except HTTPException:raise
    except Exception as exc:
        # Do not leak tool args, server credentials, file paths or server stderr.
        raise HTTPException(503,"MCP tool outcome uncertain: "+
                            type(exc).__name__) from exc


def shutdown_mcp()->None:
    """Explicit worker shutdown cleanup; does not disturb native WSS."""
    global _CLIENT,_CLIENT_KEY
    with _LOCK:
        if _CLIENT is not None:
            _CLIENT.close()
        _CLIENT=None
        _CLIENT_KEY=None
