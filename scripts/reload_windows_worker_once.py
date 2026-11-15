"""One-shot supervised Windows Control API reload after an additive source update.

Runs detached AFTER the remote command receipt has returned, not inside the
agent it restarts. Does not touch native WSS, phone pairing, Android, keys,
service installs, or repository bridge. Refuses to act when unrelated jobs run.
"""
from __future__ import annotations
import argparse
import json
import os
import time
from pathlib import Path

import httpx
import psutil


def write_report(path:Path,record:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record,sort_keys=True),encoding="utf8")
    tmp.replace(path)


def listener():
    ids=sorted({c.pid for c in psutil.net_connections(kind="tcp")
                if c.laddr and c.laddr.port==8911 and c.status=="LISTEN"})
    if len(ids)!=1:
        raise RuntimeError("Unexpected Control API listener count")
    proc=psutil.Process(ids[0])
    cmd=" ".join(proc.cmdline())
    if "asterion_remote.app:app" not in cmd or proc.name().lower()!="python.exe":
        raise RuntimeError("Unexpected process at Control API listener")
    return proc


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--delay",type=int,default=12)
    opts=args.parse_args()
    if os.name!="nt" or not 10<=opts.delay<=60:
        raise RuntimeError("Valid owner Windows environment/delay required")
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    report=state/"diagnostic-worker-reload.json"
    base=(state/"agent-host.txt").read_text(encoding="utf8").strip()
    token=(state/"control-token.txt").read_text(encoding="utf8").strip()
    if len(token)<32:
        raise RuntimeError("Existing private Windows token unavailable")
    time.sleep(opts.delay)
    result={"attempted":False,"restarted":False,"verified":False}
    try:
        with httpx.Client(base_url=base,timeout=5,trust_env=False,
              headers={"Authorization":"Bearer "+token}) as client:
            health=client.get("/api/v1/health")
            health.raise_for_status()
            if not health.json().get("ok"):
                raise RuntimeError("Owner Windows agent not healthy before reload")
            jobs=client.get("/api/v1/commands")
            jobs.raise_for_status()
            active=[j["id"] for j in jobs.json().get("items",[])
                    if j.get("status")=="running"]
            if active:
                raise RuntimeError("Other active PC commands; refusing service reload")
        original=listener()
        result["old_pid"]=original.pid
        result["attempted"]=True
        original.terminate()
        try:
            original.wait(timeout=8)
        except psutil.TimeoutExpired:
            raise RuntimeError("Agent did not stop gracefully; no force-kill authorized")
        result["restarted"]=True
        # Existing start_windows.ps1 supervisor/watchdog owns restart and
        # must continue preserving all original service/pairing state.
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            try:
                current=listener()
                if current.pid!=original.pid:
                    with httpx.Client(base_url=base,timeout=4,trust_env=False,
                          headers={"Authorization":"Bearer "+token}) as client:
                        health=client.get("/api/v1/diagnostics/health")
                    if health.status_code==200 and health.json().get("ok"):
                        result.update({"verified":True,"new_pid":current.pid,
                           "diagnostics_available":True,
                           "schema":health.json().get("schema_version")})
                        break
            except (RuntimeError,psutil.Error,httpx.HTTPError,ValueError):
                pass
            time.sleep(2)
        if not result["verified"]:
            result["error"]="supervised_restart_or_diagnostics_not_verified"
    except Exception as exc:
        result["error"]=type(exc).__name__+": "+str(exc)[:120]
    write_report(report,result)


if __name__=="__main__":
    main()
