"""Read-only acceptance inventory of already-paired Control phone and Windows features.

Never prints private URLs, tokens, logs, or user content. No POST and no
permission mutations. Run from the isolated checkout on the existing Windows PC.
"""
import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import httpx

state=Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl"
base=(state/"agent-host.txt").read_text(encoding="utf8").strip()
token=(state/"control-token.txt").read_text(encoding="utf8").strip()
parsed=urlsplit(base)
ip=ipaddress.ip_address(parsed.hostname or "")
if parsed.scheme!="http" or parsed.port!=8911 or not (ip.is_private or ip.is_loopback):
    raise RuntimeError("refusing_nonlocal_control_agent")
if len(token)<32:raise RuntimeError("missing_existing_token")
paths={
  "pc_health":"/api/v1/health",
  "diagnostic_triage":"/api/v1/diagnostics/triage",
  "diagnostic_snapshot":"/api/v1/diagnostics/snapshot",
  "phone_health":"/api/v1/phone/health",
  "phone_vpn":"/api/v1/phone/diagnostics/vpn",
  "phone_security":"/api/v1/phone/diagnostics/security",
  "phone_permissions":"/api/v1/phone/diagnostics/permissions",
  "phone_voice":"/api/v1/phone/voice/status",
  "phone_cycles":"/api/v1/phone/cycles/status",
  "phone_performance":"/api/v1/phone/performance/status",
  "phone_network":"/api/v1/phone/network/status",
  "app_bridge_catalog":"/api/v1/phone/app-bridge/apps",
  "ai_cycles":"/api/v1/intelligence/cycles",
}
summary={}
with httpx.Client(timeout=httpx.Timeout(20.0,connect=4.0),
                  trust_env=False,follow_redirects=False,
                  headers={"Authorization":"Bearer "+token}) as client:
    for name,path in paths.items():
        try:
            r=client.get(base+path)
            entry={"http_status":r.status_code,"working":False}
            if r.status_code==200:
                data=r.json()
                if isinstance(data,dict):
                    entry["working"]=data.get("ok",True) is not False
                    if name=="diagnostic_snapshot":
                        android=data.get("android") or {}
                        entry["phone_reachable"]=android.get("reachable") is True
                        entry["android_journal_present"]=isinstance(
                            android.get("own_process_journal"),dict)
                        entry["observed_apps"]=len((data.get(
                            "pc_instrumented_events") or {}).get("observed_apps") or [])
                    if name=="ai_cycles":
                        entry["saved_cycles"]=len(data.get("items") or [])
                    if name=="app_bridge_catalog":
                        entry["available_integrations"]=len(
                            data.get("apps") or data.get("integrations") or [])
                    if name=="phone_vpn":
                        for field in ("active","enabled","configured","peer_configured",
                                      "full_tunnel_approved","vpn_active"):
                            if type(data.get(field)) is bool: entry[field]=data[field]
                    if name=="phone_voice":
                        for field in ("enabled","active","listening"):
                            if type(data.get(field)) is bool:entry[field]=data[field]
                    if name=="phone_cycles":
                        for field in ("active","enabled","running"):
                            if type(data.get(field)) is bool:entry[field]=data[field]
            summary[name]=entry
        except Exception as e:
            summary[name]={"working":False,"error_class":type(e).__name__}
print(json.dumps(summary,sort_keys=True))
