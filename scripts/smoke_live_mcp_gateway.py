"""Smoke-test exact ChatGPT-facing MCP tools against the installed phone.

Uses development gateway in-process while the production MCP gateway is left
running. Gateway forwards to the already deployed live Windows Control server.
No Android gesture is authorized: one inspection, a rejected mismatched token,
and another inspection. The actual device state is not printed.
"""
import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient
from asterion_remote.mcp_gateway import app, LIVE_OPERATOR_TOOLS

ROOT=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
key=(ROOT/"mcp-gateway-token.txt").read_text("utf-8").strip()
headers={"Authorization":"Bearer "+key,
         "Accept":"application/json, text/event-stream",
         "Content-Type":"application/json"}


def call(client,name,args,index):
    response=client.post("/mcp",headers=headers,json={
        "jsonrpc":"2.0","id":index,"method":"tools/call",
        "params":{"name":name,"arguments":args}})
    if response.status_code!=200:
        raise RuntimeError("Gateway "+name+" returned HTTP "+str(response.status_code)+
                           ": "+response.text[:150])
    data=response.json()
    if data.get("id")!=index:
        raise RuntimeError("Unexpected JSON-RPC response identifier")
    return data["result"]


def main():
    assert {"control_live_ui","control_live_action","control_live_launch"} <= {
        item["name"] for item in LIVE_OPERATOR_TOOLS}
    start=time.perf_counter()
    with TestClient(app) as client:
        initial=call(client,"control_live_ui",{},1)
        if initial.get("isError"):raise RuntimeError("Cannot inspect device")
        state=initial["structuredContent"]
        if not state.get("ok") or not state.get("state_id"):
            raise RuntimeError("Gateway did not return native state token")
        refused=call(client,"control_live_action",{
            "state_id":"intentionally-wrong-state-id","action":"back"},2)
        if refused.get("isError") is not True:
            raise RuntimeError("Gateway did not reject a mismatched token")
        later=call(client,"control_live_ui",{},3)
        if later.get("isError") or not later["structuredContent"].get("ok"):
            raise RuntimeError("Gateway reinspection failed after refusal")
    print("LIVE_MCP_GATEWAY_ACCEPTANCE "+json.dumps({
        "status":"passed","direct_persistent_websocket":True,
        "mcp_tool_names_registered":True,
        "live_ui_state_token":True,"mismatched_action_rejected":True,
        "independent_reinspection":True,"actual_phone_input_executed":False,
        "screen_capture_requested":False,
        "full_test_ms":round((time.perf_counter()-start)*1000,1),
    },separators=(",",":")),flush=True)


if __name__=="__main__":
    main()
