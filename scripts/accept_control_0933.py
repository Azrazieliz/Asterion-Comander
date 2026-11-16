"""Read-only live v0.9.33 acceptance on the existing owner-paired Windows agent.

Checks authenticated registered routes, the updated diagnostic page, and native
phone reachability without dumping bearer tokens, URLs or private contents.
"""
from __future__ import annotations
import argparse, json, os, ipaddress
from pathlib import Path
from urllib.parse import urlsplit
import httpx

PATHS={
    "health":"/api/v1/health",
    "ai_readiness":"/api/v1/intelligence/capabilities",
    "intelligence_cycles":"/api/v1/intelligence/cycles",
    "models":"/api/v1/v2/models",
    "skills":"/api/v1/v2/skills",
    "phone_vpn":"/api/v1/phone/diagnostics/vpn",
    "partner_coverage":"/api/v1/diagnostics/coverage",
    "phone_health":"/api/v1/phone/health",
    "diagnostic_triage":"/api/v1/diagnostics/triage",
}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-only",action="store_true")
    args=parser.parse_args()
    if args.source_only:
        import sys
        sys.path.insert(0,"D:/AsterionControlRelease")
        from asterion_remote.app import app
        live={getattr(route,"path","") for route in app.routes}
        missing=[route for route in PATHS.values() if route not in live]
        print(json.dumps({"ok":not missing,"mode":"installed_source_import",
                          "routes_checked":len(PATHS),
                          "path_sample":sorted(live)[:35],"missing":missing}))
        return
    folder=Path(os.environ.get("LOCALAPPDATA",""))/"AsterionControl"
    base=(folder/"agent-host.txt").read_text("utf8").strip()
    token=(folder/"control-token.txt").read_text("utf8").strip()
    location=urlsplit(base)
    ip=ipaddress.ip_address(location.hostname or "")
    if location.scheme!="http" or location.port!=8911 or not (ip.is_private or ip.is_loopback) or len(token)<32:
        raise RuntimeError("refusing_nonowner_http_endpoint")
    outcomes={}
    with httpx.Client(timeout=httpx.Timeout(12,connect=4),trust_env=False,
                      follow_redirects=False,
                      headers={"Authorization":"Bearer "+token}) as client:
        for label,path in PATHS.items():
            try:
                response=client.get(base+path)
                entry={"http":response.status_code}
                if response.status_code==200:
                    data=response.json()
                    entry["valid"]=isinstance(data,dict) and data.get("ok",True) is not False
                    if label=="ai_readiness":
                        entry["model_ready"]=data.get("local_model_configured") is True
                        entry["autonomous_executor"]=data.get("work_executor_bound") is True
                    if label=="partner_coverage":
                        entry["observed_sources"]=data.get("recent_event_source_count")
                        entry["bridge_count"]=data.get("native_partner_count")
                    if label=="phone_health":
                        entry["reachable"]=entry["valid"]
                outcomes[label]=entry
            except (httpx.HTTPError,ValueError,KeyError) as exc:
                outcomes[label]={"http":None,"error":type(exc).__name__}
        for name in ("index.html","app.js","style.css"):
            location=Path("D:/AsterionControlRelease")/"asterion_remote"/"static"/name
            outcomes["dashboard_"+name]={"installed":location.is_file()}
        html=(Path("D:/AsterionControlRelease")/"asterion_remote/static/index.html").read_text("utf8")
        js=(Path("D:/AsterionControlRelease")/"asterion_remote/static/app.js").read_text("utf8")
        outcomes["new_diagnostics_ui"]={"installed":
            "What needs attention" in html and "loadIntegrationCoverage" in js
            and "diagnostic-timeline" in html}
    all_routes=all(item.get("http")==200 and item.get("valid",False)
                   for item in list(outcomes.values())[:len(PATHS)])
    outcome={"ok":all_routes,"api":outcomes,
             "phone_pairing_or_owner_data_modified":False}
    print(json.dumps(outcome,sort_keys=True),flush=True)
    if not all_routes:raise SystemExit(2)

if __name__=="__main__":
    main()
