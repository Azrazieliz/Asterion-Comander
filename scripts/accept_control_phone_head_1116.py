"""Read-only exact partner bridge/phone inference inventory.

No authorization, partner call, installation, model files, tokens, or private
application data are read. Output is bounded sanitized capability metadata.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asterion_remote import phone_bridge
paths=["/app-bridge/apps","/health","/diagnostics/vpn"]
result={}
for path in paths:
    try:
        response=phone_bridge.request(path,timeout=6)
        value=response.json()
        if path=="/app-bridge/apps":
            result["app_bridge"]={"http":response.status_code,
                "apps":[{"package":str(a.get("package",""))[:120],
                        "approved":a.get("approved") is True,
                        "protocol":str(a.get("protocol",""))[:40],
                        "requires_local_approval":a.get("requires_local_approval") is True}
                        for a in (value.get("apps") or [])[:30] if isinstance(a,dict)]}
        elif path=="/diagnostics/vpn":
            result["phone_vpn"]={"http":response.status_code,
                "backend":value.get("backend"),"active":value.get("active"),
                "configuration_present":value.get("configuration_present"),
                "peer_reachability_verified":value.get("peer_reachability_verified")}
        else:
            result["phone_health"]={"http":response.status_code,
                "android":value.get("android"),
                "available_memory_bytes":(value.get("memory") or {}).get("available")
                if isinstance(value.get("memory"),dict) else None}
    except Exception as exc:
        result[path]={"error":type(exc).__name__}
print(json.dumps(result,sort_keys=True))
