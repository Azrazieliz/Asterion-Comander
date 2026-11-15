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
from . import session_journal
from .diagnostic_core import try_record

class Step(BaseModel):
    kind: Literal["input","wait","assert_text","capture","health","window","assert_window","assert_package","await_package"]
    device: Literal["phone","pc"] | None = None
    payload: dict[str,Any] = Field(default_factory=dict)
    wait_ms: int = Field(default=0,ge=0,le=10000)
    text: str | None = Field(default=None,max_length=300)

    @model_validator(mode="after")
    def check(self):
        if self.kind in ("assert_text","assert_window","assert_package","await_package") and not self.text:raise ValueError("Expected text required")
        if self.kind=="input" and not self.payload:raise ValueError("Input payload required")
        if self.kind=="wait" and not self.wait_ms:raise ValueError("Wait duration required")
        return self

class SessionRequest(BaseModel):
    device: Literal["phone","pc","mixed"]
    steps: list[Step] = Field(min_length=1,max_length=80)
    timeout_s: int = Field(default=120,ge=2,le=300)
    stop_on_error: bool = True
    # Exact repeated requests return the original receipt, never repeat taps.
    request_id: str | None = Field(default=None,min_length=8,max_length=100,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{7,99}\Z')

    @model_validator(mode="after")
    def check(self):
        if self.device=="mixed" and any(step.device is None for step in self.steps):
            raise ValueError("Mixed sessions require each step to name its device")
        if self.device!="mixed" and any(step.device not in (None,self.device) for step in self.steps):
            raise ValueError("Step device conflicts with session device")
        for step in self.steps:
            target=step.device or self.device
            if step.kind in ("assert_package","await_package") and target!="phone":
                raise ValueError("Android package assertion requires phone target")
        return self

_guard=threading.RLock()
_pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix="asterion-interaction")
_jobs: dict[str,dict] = {}
_cancels: dict[str,threading.Event] = {}

def update(key: str,**kw):
    with _guard:
        _jobs[key].update(kw)
        row=_jobs[key]
        row["updated_at"]=time.time()
        results=list(row.get("results",[]))
        safe={"state":row["state"],"current_step":row.get("current_step",0),
              "completed_steps":sum(bool(r.get("ok")) for r in results),
              "failed_steps":sum(not bool(r.get("ok")) for r in results),
              "elapsed_ms":row.get("elapsed_ms"),
              "failure_class":str(row.get("error") or "").split(":",1)[0][:60]}
    # Evidence recording is best-effort and stores only safe operation metrics.
    # It MUST NOT turn a successful user action into a failed control command.
    try:
        session_journal.progress(key,**safe)
    except Exception:
        try_record("control_failure",component="session_receipts",severity="warning",
                   state="failed",attributes={"reason":"receipt_write_failed"})

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
        if kind in ("assert_package","await_package"):
            # Foreground package check avoids image screenshots and model
            # decisions for each navigation or app switch.
            deadline=time.monotonic()+min(8.0,max(.1,step.wait_ms/1000 if step.wait_ms else 3.0))
            last=""
            while True:
                resp=client.get(base+"/ui",headers=headers);resp.raise_for_status()
                last=resp.json().get("foreground_package","")
                if last==step.text:
                    return {"expected_package":step.text,"observed_package":last,"verified":True}
                if kind=="assert_package" or time.monotonic()>=deadline:
                    raise AssertionError("Android package mismatch; expected "+step.text+" got "+str(last)[:100])
                time.sleep(.08)
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
    needs_phone=request.device=="phone" or any(step.device=="phone" for step in request.steps)
    pairing=load() if needs_phone else None
    if needs_phone and pairing is None:
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
                    observation=perform(step,step.device or request.device,client,
                        {"Authorization":"Bearer "+pairing["token"]} if pairing else None,
                        pairing["base_url"] if pairing else None)
                result={"index":i,"kind":step.kind,"device":step.device or request.device,"ok":True,
                        "elapsed_ms":round((time.perf_counter()-step_started)*1000,1),
                        "observation":observation}
            except Exception as e:
                result={"index":i,"kind":step.kind,"device":step.device or request.device,"ok":False,
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
    try:
        previous=session_journal.reserve_if_new(data.request_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    if previous is not None:
        return {"id":previous["id"],"state":previous["state"],
                "device":previous["device"],"steps_total":previous["steps_total"],
                "reused":True,"replay_allowed":False,
                "status_path":"/api/v1/sessions/"+previous["id"]}
    with _guard:
        if sum(1 for j in _jobs.values() if j["state"] in ("queued","running"))>=3:
            raise HTTPException(429,"Maximum concurrent control sessions reached")
        ident=uuid.uuid4().hex
        receipt,reused=session_journal.reserve(ident,data.device,len(data.steps),data.request_id)
        if reused:
            return {"id":receipt["id"],"state":receipt["state"],
                    "device":receipt["device"],"steps_total":receipt["steps_total"],
                    "reused":True,"replay_allowed":False,
                    "status_path":"/api/v1/sessions/"+receipt["id"]}
        _jobs[ident]={"id":ident,"state":"queued","device":data.device,
                      "steps_total":len(data.steps),"current_step":0,"results":[],
                      "error":None,"created_at":time.time(),"updated_at":time.time()}
        cancel=threading.Event()
        _cancels[ident]=cancel
    _pool.submit(worker,ident,data,cancel)
    try_record("session_created",component="interaction_sessions",state="queued",
               operation_id=ident,attributes={"stage":"execution","worker_limit":3})
    return {"id":ident,"state":"queued","device":data.device,
            "steps_total":len(data.steps),"reused":False,"replay_allowed":False,
            "status_path":"/api/v1/sessions/"+ident}

def status(key:str):
    with _guard:
        if key in _jobs:
            return _jobs[key].copy()
    persisted=session_journal.get(key)
    if persisted is not None:
        # Previous worker crashed or restarted. Its actions may have executed.
        # Never falsely present the old status as a live, re-runnable job.
        return persisted
    raise HTTPException(404,"Unknown control session")

def cancel(key:str):
    with _guard:
        if key not in _jobs:
            prior=session_journal.get(key)
            if prior is None:raise HTTPException(404,"Unknown control session")
            return {"ok":False,"state":prior["state"],"reason":"not_running_in_current_worker"}
        if _jobs[key]["state"] not in ("queued","running"):
            return {"ok":False,"state":_jobs[key]["state"]}
        _cancels[key].set()
    return {"ok":True,"state":"cancelling"}
)

    @model_validator(mode="after")
    def check(self):
        if self.device=="mixed" and any(step.device is None for step in self.steps):
            raise ValueError("Mixed sessions require each step to name its device")
        if self.device!="mixed" and any(step.device not in (None,self.device) for step in self.steps):
            raise ValueError("Step device conflicts with session device")
        for step in self.steps:
            target=step.device or self.device
            if step.kind in ("assert_package","await_package") and target!="phone":
                raise ValueError("Android package assertion requires phone target")
        return self

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
        if kind in ("assert_package","await_package"):
            # Foreground package check avoids image screenshots and model
            # decisions for each navigation or app switch.
            deadline=time.monotonic()+min(8.0,max(.1,step.wait_ms/1000 if step.wait_ms else 3.0))
            last=""
            while True:
                resp=client.get(base+"/ui",headers=headers);resp.raise_for_status()
                last=resp.json().get("foreground_package","")
                if last==step.text:
                    return {"expected_package":step.text,"observed_package":last,"verified":True}
                if kind=="assert_package" or time.monotonic()>=deadline:
                    raise AssertionError("Android package mismatch; expected "+step.text+" got "+str(last)[:100])
                time.sleep(.08)
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
    needs_phone=request.device=="phone" or any(step.device=="phone" for step in request.steps)
    pairing=load() if needs_phone else None
    if needs_phone and pairing is None:
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
                    observation=perform(step,step.device or request.device,client,
                        {"Authorization":"Bearer "+pairing["token"]} if pairing else None,
                        pairing["base_url"] if pairing else None)
                result={"index":i,"kind":step.kind,"device":step.device or request.device,"ok":True,
                        "elapsed_ms":round((time.perf_counter()-step_started)*1000,1),
                        "observation":observation}
            except Exception as e:
                result={"index":i,"kind":step.kind,"device":step.device or request.device,"ok":False,
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
