"""Read-only production acceptance for ChatGPT-facing state-aware MCP tools.

Checks the actual Windows local MCP gateway: catalog, native UI inspection,
one rejected mismatched state, and a subsequent inspection. Never performs a
successful Android input or exposes bearer tokens in output.
"""
import json
import os
import time
from pathlib import Path
import httpx

ROOT=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
KEY=(ROOT/"mcp-gateway-token.txt").read_text("utf-8").strip()
ENDPOINT="http://127.0.0.1:8996/mcp"
HEADERS={"Authorization":"Bearer "+KEY,
         "Accept":"application/json, text/event-stream",
         "Content-Type":"application/json"}


def send(client,method,name=None,arguments=None,reqid=1):
    message={"jsonrpc":"2.0","id":reqid,"method":method}
    if method=="tools/call":
        message["params"]={"name":name,"arguments":arguments or {}}
    response=client.post(ENDPOINT,json=message,headers=HEADERS,timeout=13)
    response.raise_for_status()
    answer=response.json()
    if answer.get("id")!=reqid or "result" not in answer:
        raise RuntimeError("Control gateway returned an invalid MCP result")
    return answer["result"]


def main():
    started=time.perf_counter()
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=14) as client:
        catalog=send(client,"tools/list",reqid=10)
        found={item.get("name") for item in catalog.get("tools",[])}
        required={"control_live_ui","control_live_action","control_live_launch"}
        if not required.issubset(found):
            raise RuntimeError("Production MCP catalog lacks live interactive tools")
        observed=send(client,"tools/call","control_live_ui",reqid=11)
        current=observed.get("structuredContent") or {}
        if not current.get("ok") or not current.get("state_id"):
            raise RuntimeError("Production MCP UI inspection failed")
        declined=send(client,"tools/call","control_live_action",
                      {"state_id":"deliberately-invalid-state","action":"back"},reqid=12)
        if declined.get("isError") is not True:
            raise RuntimeError("Production MCP sent an action without valid state")
        again=send(client,"tools/call","control_live_ui",reqid=13)
        if not (again.get("structuredContent") or {}).get("ok"):
            raise RuntimeError("Production MCP could not continue after rejected action")
    print("CONTROL_MCP_HTTP_ACCEPTED "+json.dumps({
        "status":"passed","tools_exposed":sorted(required),
        "persistent_direct_phone_state_available":True,
        "stale_action_rejected":True,"independent_followup_observation":True,
        "phone_actions_executed":False,"screenshots_requested":False,
        "elapsed_ms":round((time.perf_counter()-started)*1000,1),
    },separators=(",",":")),flush=True)

if __name__=="__main__":
    main()
