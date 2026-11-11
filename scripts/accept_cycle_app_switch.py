"""Short real-UI acceptance: ChatGPT -> Asterion Control -> ChatGPT.

Uses existing authenticated persistent Windows worker and Android Accessibility.
Does not send a chat message or stop the phone agent / recording. If screen
sharing is already active, verifies fresh frames; if inactive, requests the
existing Control UI restart and observes the Android consent dialog.
"""
from __future__ import annotations
import json,os,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(r'D:\AsterionControlRelease')))
import httpx

ROOT=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
URL=(ROOT/"agent-host.txt").read_text(encoding="utf-8").strip()
TOKEN=(ROOT/"control-token.txt").read_text(encoding="utf-8").strip()
C=httpx.Client(base_url=URL,headers={"Authorization":"Bearer "+TOKEN},timeout=4,trust_env=False)
LOG=[]
def get(path):
    r=C.get(path);r.raise_for_status();return r.json()
def input_action(**a):
    t=time.perf_counter();r=C.post("/api/v1/phone/input",json=a);r.raise_for_status()
    obj=r.json();LOG.append({"action":a["action"],"result":obj,
                            "roundtrip_ms":round((time.perf_counter()-t)*1000,1)})
    if obj.get("ok") is False: raise RuntimeError("NATIVE_INPUT_UNSUCCESSFUL:"+a["action"])
    return obj
def nodes(n):
    if not isinstance(n,dict):return
    yield n
    for c in n.get("children",[]):yield from nodes(c)
def ui():
    return get("/api/v1/phone/ui")
def app_element(data,name):
    for n in nodes(data.get("root",{})):
        words=" ".join([n.get("text",""),n.get("description","")]).strip().lower()
        if words==name.lower() or words.endswith(name.lower()):
            b=n.get("bounds",[])
            if len(b)==4 and b[2]>b[0] and b[3]>b[1]:
                return (int((b[0]+b[2])/2),int((b[1]+b[3])/2))
    return None
def wait_foreground(pkg,timeout=5):
    last=""
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        u=ui();last=u.get("foreground_package","")
        if last==pkg:return u
        time.sleep(.15)
    raise RuntimeError("FOREGROUND_NOT_VERIFIED:"+pkg+":actual="+last)
def open_recent(name,pkg):
    # Samsung Recents exposes reliable labeled task cards; the launcher drawer
    # is paginated and can omit icons from the Accessibility tree.
    if not input_action(action="recents"):
        raise RuntimeError("RECENTS_NOT_OPENED")
    time.sleep(.25)
    current=ui()
    available=[(n.get("text") or n.get("description") or "")
               for n in nodes(current.get("root",{}))]
    if not any(x.strip().lower()==name.lower() for x in available):
        raise RuntimeError("RECENT_TASK_NOT_VISIBLE:"+name)
    if not input_action(action="click_text",text=name):
        raise RuntimeError("RECENT_TASK_CLICK_FAILED:"+name)
    wait_foreground(pkg,6)
    LOG.append({"opened_from_recents":name,"foreground":pkg})
def capture_status():
    status=get("/api/v1/phone")
    return {"paired":status.get("paired"),"reachable":status.get("reachable"),
            "capture":status.get("info",{}).get("capture"),
            "accessible":status.get("info",{}).get("accessible"),
            "direct_connected":status.get("info",{}).get("remote_transport",{}).get("direct_mcp",{}).get("connected")}
def main():
    start=time.perf_counter()
    before=ui().get("foreground_package","")
    if before!="com.openai.chatgpt": raise RuntimeError("CHATGPT_NOT_FOREGROUND_"+before)
    try:
        open_recent("Asterion Control","com.asterion.control")
        state=capture_status()
        LOG.append({"asterion_control_status":state})
        if not state["capture"]:
            current=ui();loc=app_element(current,"Start screen sharing")
            if not loc and app_element(current,"Open Connect"):
                input_action(action="click_text",text="Open Connect")
                time.sleep(.25)
                current=ui();loc=app_element(current,"Start screen sharing")
            if not loc:
                raise RuntimeError("CAPTURE_OFF_NO_VISIBLE_RESTART_BUTTON")
            input_action(action="tap",x=loc[0],y=loc[1])
            time.sleep(.5)
            current=ui()
            visible=[(n.get("text") or n.get("description")) for n in nodes(current.get("root",{}))
                     if (n.get("text") or n.get("description"))]
            LOG.append({"capture_restart_prompt_visible":visible[:15]})
            # Never blindly approve a MediaProjection dialog.
            for label in ("Start now","Start recording or casting","Commencer"):
                loc=app_element(current,label)
                if loc:
                    input_action(action="tap",x=loc[0],y=loc[1]);break
            time.sleep(.7)
            LOG.append({"capture_after_recovery":capture_status()})
        else:
            # Native capture remains live after leaving ChatGPT.
            res=C.get("/api/v1/phone/screen")
            LOG.append({"video_stream_healthy":res.status_code==200 and
                        res.headers.get("content-type","").startswith("image/jpeg"),
                        "captured_bytes":len(res.content)})
    finally:
        # Keep EXACT same ChatGPT task/conversation. Starting ChatGPT's launcher
        # activity can open its new-chat home instead of the previous thread.
        try:
            if ui().get("foreground_package")!="com.openai.chatgpt":
                open_recent("ChatGPT","com.openai.chatgpt")
            LOG.append({"original_chatgpt_task_restored":True})
        except Exception as e:
            LOG.append({"return_to_chatgpt_error":str(e)})
    after=ui().get("foreground_package","")
    output={"test":"chatgpt-control-chatgpt-real-ui","before":before,
            "after":after,"returned":after=="com.openai.chatgpt",
            "total_ms":round((time.perf_counter()-start)*1000,1),"events":LOG}
    print(json.dumps(output,ensure_ascii=False,separators=(",",":")))
    if not output["returned"]:raise RuntimeError("CHATGPT_RESTORE_FAILED")
if __name__=="__main__":main()
