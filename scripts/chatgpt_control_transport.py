"""ChatGPT fallback transport to existing authenticated Asterion MCP gateway.

Purpose: when native ChatGPT Asterion tools cannot attach, use the already
connected authorized Windows worker ONLY as a transport to the phone-first
Control gateway. No ADB, GitHub queue, secret output, or retry after uncertainty.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

GATEWAY = "http://127.0.0.1:8995/mcp"
KEYFILE = Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl" / "mcp-gateway-token.txt"
READ_ONLY = frozenset({
    "control_phone_status",
    "control_phone_direct_status",
    "control_phone_network_status",
    "control_phone_health",
    "control_phone_performance_status",
    "control_phone_voice_status",
    "control_phone_cycle_status",
    "control_phone_continuation_status",
    "control_phone_observation_status",
    "control_phone_observation_events",
    "control_phone_observation_timeline",
    "control_phone_apps",
    "control_phone_ui",
    "control_pc_status",
    "control_pc_health",
    "control_pc_performance_status",
})
SENSITIVE = {"token", "secret", "password", "apikey", "api_key", "bearer",
             "authorization", "headers", "refresh_token", "access_token",
             "connection_key", "gateway_key", "approval_code"}
def scrub(obj:Any) -> Any:
    if isinstance(obj,dict):
        return {k:("[REDACTED]" if k.lower().replace("-","_") in SENSITIVE else scrub(v))
                for k,v in obj.items()}
    if isinstance(obj,list):
        return [scrub(v) for v in obj[:80]]
    if isinstance(obj,str):
        return obj[:8192]
    return obj

def main() -> int:
    parser=argparse.ArgumentParser(description="Authorized Asterion Control MCP transport")
    parser.add_argument("--tool",required=True)
    parser.add_argument("--args-json",default="{}")
    parser.add_argument("--allow-write",action="store_true")
    ns=parser.parse_args()
    name=ns.tool
    if not (name.startswith("control_phone_") or name.startswith("control_pc_")):
        print("ERROR=unsupported_control_tool_namespace")
        return 2
    try:
        args=json.loads(ns.args_json)
        if not isinstance(args,dict):
            raise ValueError("parameters must be an object")
    except (ValueError,TypeError):
        print("ERROR=invalid_json_parameters")
        return 2
    if name not in READ_ONLY and not ns.allow_write:
        print("ERROR=action_requires_explicit_approval")
        return 3
    try:
        key=KEYFILE.read_text(encoding="utf-8").strip()
        if len(key)<43:raise ValueError("invalid owner's local gateway key")
    except (OSError,ValueError):
        print("ERROR=gateway_owner_credential_not_found")
        return 4
    headers={"Authorization":"Bearer "+key,
             "Accept":"application/json, text/event-stream",
             "Content-Type":"application/json"}
    def rpc(client:httpx.Client,method:str,ident:int,params=None):
        payload={"jsonrpc":"2.0","id":ident,"method":method}
        if params is not None: payload["params"]=params
        response=client.post(GATEWAY,json=payload,headers=headers)
        if response.status_code!=200:
            raise RuntimeError("gateway_http_"+str(response.status_code))
        body=response.json()
        if "error" in body:
            raise RuntimeError("mcp_rpc_error_"+str(body["error"].get("code","unknown")))
        return body.get("result",{})
    try:
        with httpx.Client(timeout=22.0,trust_env=False,follow_redirects=False) as client:
            listing=rpc(client,"tools/list",1)
            known={entry.get("name") for entry in listing.get("tools",[])
                   if isinstance(entry,dict)}
            if name not in known:
                print("ERROR=tool_not_in_authenticated_catalog")
                return 5
            result=rpc(client,"tools/call",2,{"name":name,"arguments":args})
    except (httpx.HTTPError,RuntimeError,ValueError) as exc:
        print("ERROR="+str(exc)[:180])
        print("EXECUTION_RECEIPT=unknown_or_not_received")
        print("RETRY=not_automatic")
        return 6
    print("GATEWAY_AUTHENTICATED=true")
    print("TOOL="+name)
    print("RPC_IS_ERROR="+str(bool(result.get("isError",False))).lower())
    content=result.get("content",[])
    if content:
        for entry in content[:4]:
            if entry.get("type")!="text":continue
            raw=entry.get("text","")
            try:parsed=json.loads(raw)
            except (ValueError,TypeError):parsed={"text":str(raw)[:8192]}
            print("RECEIPT="+json.dumps(scrub(parsed),ensure_ascii=False,default=str)[:16000])
    else:
        print("RECEIPT="+json.dumps(scrub(result),ensure_ascii=False,default=str)[:16000])
    return 1 if result.get("isError") else 0

if __name__=="__main__":
    sys.exit(main())
