"""Persistent authorized Asterion Control-side multi-step interaction sessions.

One ChatGPT request starts a bounded worker on Windows; subsequent UI actions,
waits, assertions and captures run without a per-gesture ChatGPT or GitHub turn.
The operator can inspect progress, cancel and stop. This is deterministic
execution of an explicit plan, not an autonomous screen-reading AI.
"""
from __future__ import annotations
import hashlib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator

from .phone_bridge import PhoneInput, load

class Step(BaseModel):
    kind: Literal["input","wait","assert_text","capture","health","window","assert_window"]
    payload: dict[str,Any] = Field(default_factory=dict)
    wait_ms: int = Field(default=0,ge=0,le=10000)
    text: str | None = Field(default=None,max_length=300)

    @model_validator(mode="after")
    def check(self):
        if self.kind in ("assert_text","assert_window") and not self.text:raise ValueError("Expected text required")
        if self.kind=="input" and not self.payload:raise ValueError("Input payload required")
        if self.kind=="wait" and not self.wait_ms:raise ValueError("Wait duration required")
        return self

class SessionRequest(BaseModel):
    device: Literal["phone","pc"]
    steps: list[Step] = Field(min_length=1,max_length=80)
    timeout_s: int = Field(default=120,ge=2,le=300)
    stop_on_error: bool = True

_guard=threading.RLock()
_pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix="asterion-interaction")
_jobs: dict[str,dict] = {}
_cancels: dict[str,threading.Event] = {}

def update(key: str,**kw):
    with _guard:
        _jobs[key].update(kw)
        _jobs[key]["updated_at"]=time.time()

def flatten_ui(node,found):
    if not isinstance(node,dict):return
    for field in ("text","description"):
        if isinstance(node.get(field),str) and node[field]:
            found.append(node[field])
    for child in node.get("children",[]):flatten_ui(child,found)

def perform(step: Step,device: str,client: httpx.Client | None,headers:dict | None,base:str | None):
    kind=step.kind
    if kind=="wait":return {"wait_ms":step.wait_ms}
    if device=="phone":
        if client is None or headers is None or base is None:
            raise RuntimeError("Paired native phone required")
        if kind=="input":
            data=PhoneInput(**step.payload).model_dump(exclude_none=True)
            resp=client.post(base+"/input",headers=headers,json=data)
            resp.raise_for_status()
            if not resp.json().get("ok"):raise RuntimeError("Phone did not confirm input")
            return {"ok":True,"action":data["action"]}
        if kind=="health":
            resp=client.get(base+"/health",headers=headers);resp.raise_for_status()
            value=resp.json()
            return {"ok":bool(value.get("ok")),"accessible":value.get("accessible"),
              "capture":value.get("capture"),"battery":value.get("battery")}
        if kind=="assert_text":
            resp=client.get(base+"/ui",headers=headers);resp.raise_for_status()
            contents=[];flatten_ui(resp.json().get("root"),contents)
            expected=step.text.casefold()
            matches=[v for v in contents if expected in v.casefold()]
            if not matches:raise AssertionError("Expected text is not visible: "+step.text)
            return {"matched":step.text,"visible":True}
        if kind=="capture":
            resp=client.get(base+"/screen",headers=headers);resp.raise_for_status()
            frame=resp.content
            return {"bytes":len(frame),"sha256":hashlib.sha256(frame).hexdigest()}
    else:
        from . import app as remote
        if kind in ("window","assert_window"):
            from .desktop_observe import foreground
            if kind=="window":return foreground()
            deadline=time.monotonic()+min(5.0,max(0.1,step.wait_ms/1000 if step.wait_ms else 3.0))
            state=foreground()
            while time.monotonic()<deadline and (not state.get("available") or
                    step.text.casefold() not in state.get("title","").casefold()):
                time.sleep(0.1)
                state=foreground()
            if not state.get("available") or step.text.casefold() not in state.get("title","").casefold():
                raise AssertionError("Foreground window does not contain expected title: "+step.text)
            return state
        if kind=="input":
            arg=remote.DesktopInput(**step.payload)
            result=remote.desktop_input(arg)
            if not result.get("ok"):raise RuntimeError("Windows input was not confirmed")
            return {"ok":True,"action":arg.action}
        if kind=="health":
            h=remote.health()
            return {"ok":bool(h.get("ok")),"host":h.get("host")}
        if kind=="capture":
            frame=remote.screenshot(monitor=step.payload.get("monitor",1),quality=68).body
            return {"bytes":len(frame),"sha256":hashlib.sha256(frame).hexdigest()}
        if kind=="assert_text":
            raise ValueError("Windows screen text assertions are unavailable; use capture comparison")
    raise ValueError("Unsupported step kind")

def worker(key: str,request: SessionRequest,cancel:threading.Event):
    started=time.monotonic()
    update(key,state="running")
    pairing=load() if request.device=="phone" else None
    if request.device=="phone" and pairing is None:
        update(key,state="failed",error="Phone not paired");return
    client=httpx.Client(timeout=httpx.Timeout(8.0,connect=3.0),
                        trust_env=False,follow_redirects=False) if pairing else None
    try:
        results=[]
        for i,step in enumerate(request.steps):
            if cancel.is_set():
                update(key,state="cancelled",current_step=i)
                return
            if time.monotonic()-started>request.timeout_s:
                update(key,state="timed_out",error="Session time budget exhausted")
                return
            step_started=time.perf_counter()
            try:
                if step.kind=="wait":
                    deadline=time.monotonic()+step.wait_ms/1000
                    while time.monotonic()<deadline:
                        if cancel.wait(min(0.05,max(0,deadline-time.monotonic()))):
                            update(key,state="cancelled",current_step=i);return
                    observation={"wait_ms":step.wait_ms}
                else:
                    observation=perform(step,request.device,client,
                        {"Authorization":"Bearer "+pairing["token"]} if pairing else None,
                        pairing["base_url"] if pairing else None)
                result={"index":i,"kind":step.kind,"ok":True,
                        "elapsed_ms":round((time.perf_counter()-step_started)*1000,1),
                        "observation":observation}
            except Exception as e:
                result={"index":i,"kind":step.kind,"ok":False,
                        "elapsed_ms":round((time.perf_counter()-step_started)*1000,1),
                        "error":type(e).__name__+": "+str(e)[:200]}
            results.append(result)
            update(key,current_step=i+1,results=results.copy())
            if not result["ok"] and request.stop_on_error:
                update(key,state="failed",error=result["error"]);return
        update(key,state="completed",elapsed_ms=round((time.monotonic()-started)*1000,1))
    finally:
        if client:client.close()

def start(data:SessionRequest):
    with _guard:
        if sum(1 for j in _jobs.values() if j["state"] in ("queued","running"))>=3:
            raise HTTPException(429,"Maximum concurrent control sessions reached")
        ident=uuid.uuid4().hex
        _jobs[ident]={"id":ident,"state":"queued","device":data.device,
                      "steps_total":len(data.steps),"current_step":0,"results":[],
                      "error":None,"created_at":time.time(),"updated_at":time.time()}
        cancel=threading.Event()
        _cancels[ident]=cancel
    _pool.submit(worker,ident,data,cancel)
    return {"id":ident,"state":"queued","device":data.device,
            "steps_total":len(data.steps),
            "status_path":"/api/v1/sessions/"+ident}

def status(key:str):
    with _guard:
        if key not in _jobs:raise HTTPException(404,"Unknown control session")
        return _jobs[key].copy()

def cancel(key:str):
    with _guard:
        if key not in _jobs:raise HTTPException(404,"Unknown control session")
        if _jobs[key]["state"] not in ("queued","running"):
            return {"ok":False,"state":_jobs[key]["state"]}
        _cancels[key].set()
    return {"ok":True,"state":"cancelling"}
