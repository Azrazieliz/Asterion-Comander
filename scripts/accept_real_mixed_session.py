"""Non-disruptive acceptance of actual worker-resident mixed PC/Android sessions.

Three real Control jobs; each executes verified PC/phone native reads and
current foreground-package assertion without changing windows, apps or files.
"""
from __future__ import annotations
import json
import os
import statistics
import time
from pathlib import Path
import httpx


def main():
    root=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    base=(root/"agent-host.txt").read_text(encoding="utf8").strip()
    token=(root/"control-token.txt").read_text(encoding="utf8").strip()
    outcomes=[]
    with httpx.Client(base_url=base,timeout=8,trust_env=False,
         headers={"Authorization":"Bearer "+token}) as client:
        for attempt in range(3):
            initial=client.get("/api/v1/phone/ui")
            initial.raise_for_status()
            package=initial.json().get("foreground_package")
            if not isinstance(package,str) or not package:
                raise RuntimeError("Actual Android foreground package unavailable")
            request={"device":"mixed","steps":[
                {"kind":"health","device":"pc"},
                {"kind":"health","device":"phone"},
                {"kind":"assert_package","device":"phone","text":package},
                {"kind":"window","device":"pc"}],
                "timeout_s":25,"stop_on_error":True}
            began=time.perf_counter()
            accepted=client.post("/api/v1/sessions",json=request)
            accepted.raise_for_status()
            ident=accepted.json()["id"]
            finish=None
            for _ in range(70):
                response=client.get("/api/v1/sessions/"+ident)
                response.raise_for_status()
                finish=response.json()
                if finish["state"] not in ("queued","running"):
                    break
                time.sleep(.1)
            if finish is None or finish["state"] in ("queued","running"):
                raise RuntimeError("Mixed control session failed to reach a terminal state")
            results=finish.get("results",[])
            health_ok=all(r.get("ok") for r in results)
            verified=any(
                r.get("kind")=="assert_package" and
                r.get("observation",{}).get("verified") is True
                for r in results)
            outcomes.append({
                "attempt":attempt+1,"state":finish["state"],
                "steps":len(results),"successful_steps":sum(bool(r.get("ok")) for r in results),
                "package_verified":verified,
                "elapsed_ms":round((time.perf_counter()-began)*1000,1),
                "error":finish.get("error")
            })
            if finish["state"]!="completed" or not health_ok or not verified or len(results)!=4:
                break
        # Check the actual incident recorder without claiming partner engine coverage.
        health=client.get("/api/v1/diagnostics/health")
        health.raise_for_status()
        report={
            "test":"real_mixed_pc_phone_nondisruptive",
            "attempts":outcomes,
            "passed":len(outcomes)==3 and all(x["state"]=="completed" and
                     x["successful_steps"]==4 and x["package_verified"] for x in outcomes),
            "median_session_ms":round(statistics.median(x["elapsed_ms"] for x in outcomes),1),
            "diagnostic_api":health.json().get("ok"),
            "scope":"real Windows worker and paired Samsung; non-destructive read-only",
            "chatgpt_inclusive":False,
        }
        print(json.dumps(report,separators=(",",":")))


if __name__=="__main__":
    main()
