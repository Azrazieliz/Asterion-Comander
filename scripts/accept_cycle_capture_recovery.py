"""Safe recovery acceptance when Android projection and direct WSS drop mid-cycle.

Only taps UI labels visible on the phone, preserves ChatGPT draft and pairing,
never force-stops the native Agent. Android consent prompt is owner-authorized
for this test; if inaccessible, report manual approval required.
"""
import json,os,time,sys
from pathlib import Path
sys.path.insert(0,r"D:\AsterionControlRelease")
import httpx
from asterion_remote.phone_bridge import request
STATE=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
URL=(STATE/"agent-host.txt").read_text(encoding="utf-8").strip()
TOKEN=(STATE/"control-token.txt").read_text(encoding="utf-8").strip()
C=httpx.Client(base_url=URL,headers={"Authorization":"Bearer "+TOKEN},timeout=5,trust_env=False)
LOG=[]
def get(p):r=C.get(p);r.raise_for_status();return r.json()
def action(**args):
    r=C.post("/api/v1/phone/input",json=args);r.raise_for_status()
    j=r.json();LOG.append({"action":args["action"],"target":args.get("text",""),"ok":j.get("ok")})
    return j.get("ok",False)
def ui():return get("/api/v1/phone/ui")
def nodes(n):
    if not isinstance(n,dict):return
    yield n
    for child in n.get("children",[]):yield from nodes(child)
def labels(u):
    return [str(n.get("text") or n.get("description")).strip()
            for n in nodes(u.get("root",{})) if (n.get("text") or n.get("description"))]
def wait(pkg,seconds=5):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        u=ui()
        if u.get("foreground_package")==pkg:return u
        time.sleep(.2)
    raise RuntimeError("FOREGROUND_TIMEOUT_"+pkg)
def open_control():
    if ui().get("foreground_package")=="com.asterion.control":return
    if not action(action="recents"):raise RuntimeError("RECENTS_FAILED")
    time.sleep(.25)
    u=ui()
    cards=labels(u)
    if not any("Asterion Control" in z for z in cards):
        raise RuntimeError("NO_CONTROL_RECENT_CARD")
    if not action(action="click_text",text="Asterion Control"):
        raise RuntimeError("OPEN_CONTROL_CARD_FAILED")
    wait("com.asterion.control")
def phone():
    h=get("/api/v1/phone")
    i=h.get("info",{})
    return {"paired":h.get("paired"),"reachable":h.get("reachable"),
            "capture":i.get("capture"),
            "direct_connected":i.get("remote_transport",{}).get("direct_mcp",{}).get("connected")}
def main():
    begin=time.perf_counter()
    LOG.append({"before":phone()})
    open_control()
    control=ui()
    LOG.append({"opened_control":True,"visible_controls":[x for x in labels(control) if
                any(z in x.lower() for z in ("sharing","capture","device","screen"))][:16]})
    if not phone()["capture"]:
        if not any("Start screen sharing" in z for z in labels(control)):
            if any(z.lower()=="devices" for z in labels(control)):
                action(action="click_text",text="Devices")
                time.sleep(.25);control=ui()
        if not any("Start screen sharing" in z for z in labels(control)):
            raise RuntimeError("CAPTURE_RESTART_BUTTON_NOT_VISIBLE")
        if not action(action="click_text",text="Start screen sharing"):
            raise RuntimeError("START_SCREEN_SHARING_FAILED")
        time.sleep(.4)
        prompt=ui()
        words=labels(prompt)
        LOG.append({"consent_foreground":prompt.get("foreground_package"),
                    "dialog_labels":[w for w in words if
                        any(z in w.lower() for z in ("screen","start","share","record","commencer","partager"))][:22]})
        for exact in ("Start now","Start sharing","Share screen","Commencer","Démarrer","Start"):
            if any(x.strip().lower()==exact.lower() for x in words):
                if action(action="click_text",text=exact):
                    LOG.append({"android_consent_button":exact})
                    break
        time.sleep(.7)
    LOG.append({"after_capture_attempt":phone()})
    if ui().get("foreground_package")=="com.asterion.control":
        launched=request("/apps/launch","POST",{"package":"com.openai.chatgpt"},timeout=6).json()
        LOG.append({"chatgpt_launch":launched})
        if launched.get("intent_dispatched"):
            wait("com.openai.chatgpt",6)
    elif ui().get("foreground_package")=="com.openai.chatgpt":
        LOG.append({"chatgpt_already_foreground":True})
    LOG.append({"final_foreground":ui().get("foreground_package"),
                "total_ms":round((time.perf_counter()-begin)*1000,1)})
    print(json.dumps({"test":"cycle_capture_recovery_native_control",
                       "events":LOG},ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":
    try:main()
    except Exception as e:
        print(json.dumps({"test":"cycle_capture_recovery_native_control",
                          "error":str(e),"events":LOG},ensure_ascii=False,separators=(",",":")))
        raise
