"""Demonstrate real Control use on Windows and Wi-Fi transfer to Samsung.
Runs entirely through already-authenticated Asterion Control endpoints; the
connected GitHub fallback may launch this one process but is NOT between steps
or in the file data path. Does not use ADB, Work or Desktop Commander.
"""
from __future__ import annotations
import hashlib,json,os,time
from pathlib import Path
import httpx

STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl"
TOKEN=(STATE/"control-token.txt").read_text("utf-8").strip()
BASE="http://192.168.1.133:8911"
HEADERS={"Authorization":"Bearer "+TOKEN}
PLAN={
 "device":"pc",
 "timeout_s":90,
 "stop_on_error":True,
 "steps":[
    {"kind":"health"},
    {"kind":"input","payload":{"action":"hotkey","keys":["win","r"]}},
    {"kind":"wait","wait_ms":350},
    {"kind":"input","payload":{"action":"type","text":"notepad"}},
    {"kind":"input","payload":{"action":"press","keys":["enter"]}},
    {"kind":"wait","wait_ms":1100},
    {"kind":"input","payload":{"action":"type","text":"ASTERION CONTROL - PC CONTROL VERIFIED\nDirect persistent session\nWi-Fi transfer verification"}},
    {"kind":"wait","wait_ms":250},
    {"kind":"capture","payload":{"monitor":1}},
    {"kind":"health"}
 ]
}
def report(tag,obj):print(tag+" "+json.dumps(obj,ensure_ascii=False,separators=(",",":")),flush=True)

def check_status(client,path,deadline=25):
    started=time.perf_counter()
    while time.perf_counter()-started<deadline:
        r=client.get(path);r.raise_for_status();data=r.json()
        if data["state"] in ("completed","cancelled","timed_out","failed"):
            return data
        time.sleep(.2)
    raise TimeoutError("Control session/transfer status exceeded deadline")

with httpx.Client(timeout=httpx.Timeout(15,connect=4),
                  trust_env=False,follow_redirects=False,headers=HEADERS) as client:
    info=client.get(BASE+"/api/v1/phone")
    info.raise_for_status()
    phone=info.json()
    report("PHONE_BEFORE",{"paired":phone.get("paired"),"reachable":phone.get("reachable"),
         "accessible":phone.get("info",{}).get("accessible"),
         "capture":phone.get("info",{}).get("capture")})
    started=time.perf_counter()
    response=client.post(BASE+"/api/v1/sessions",json=PLAN)
    response.raise_for_status()
    session=response.json()["id"]
    final=check_status(client,BASE+"/api/v1/sessions/"+session,deadline=80)
    report("PC_SESSION",{"state":final["state"],
      "steps_passed":sum(row["ok"] for row in final["results"]),
      "steps_total":final["steps_total"],
      "elapsed_ms":round((time.perf_counter()-started)*1000,1),
      "step_timings_ms":[{"kind":r["kind"],"elapsed_ms":r["elapsed_ms"],"ok":r["ok"]}
                for r in final["results"]],
      "screenshot_bytes":next((r.get("observation",{}).get("bytes") for r in final["results"]
                if r["kind"]=="capture"),None),
      "error":final.get("error")})
    if final["state"]!="completed":
        raise RuntimeError("PC interaction session did not complete")

    text="Asterion Control verified a direct private-WiFi transfer from Windows to Android.\nNo ADB, GitHub or cloud storage was used to carry file contents.\n"
    home=Path.home()
    path=home/"Asterion-Control-WiFi-Proof.txt"
    if path.exists() and path.read_text("utf-8")!=text:
        path=home/"Asterion-Control-WiFi-Proof-2.txt"
    if not path.exists():path.write_text(text,"utf-8")
    want=hashlib.sha256(path.read_bytes()).hexdigest()
    launched=time.perf_counter()
    response=client.post(BASE+"/api/v1/phone/transfers",
                         json={"pc_path":str(path),"name":path.name})
    response.raise_for_status()
    job=response.json()["id"]
    result=check_status(client,BASE+"/api/v1/phone/transfers/"+job,deadline=80)
    proof=result.get("result") or {}
    report("WIFI_TRANSFER",{"state":result["state"],
      "bytes_sent":result.get("bytes_sent"),"size":result.get("size"),
      "elapsed_ms":round((time.perf_counter()-launched)*1000,1),
      "android_location":proof.get("location"),"verified":proof.get("verified"),
      "sha256_matching":proof.get("sha256")==want,
      "error":result.get("error")})
    if result["state"]!="completed" or proof.get("sha256")!=want:
        raise RuntimeError("Wi-Fi transfer was not verified on Android")
