"""Real opt-in automatic developer loop for persistent Asterion project cycles.

Unlike prior placeholder status APIs, this driver joins a REAL local inference
provider, a source-aware Git workbench, and a durable cycle ledger.

No model/server/owner-approved Git project configuration => NO dispatch and
no fake advancement. No paid cloud. Git drafts are independently SHA verified,
but functional acceptance requires separate trusted checks; never falsely
declare project complete from syntactic source edits.

Owner must enable ASTERION_DEV_CYCLE_ENABLED=1 and provide:
  ASTERION_DEV_PROJECT_REGISTRY=<absolute path to owner-controlled JSON>
  ASTERION_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:<port>/v1/chat/completions
  ASTERION_LOCAL_MODEL_ID=<actual local model id>

Registry example:
{
  "schema":1,"projects":[{
    "name":"AsterionControl","repository":"D:/AsterionControlUpgrade20261115",
    "base_ref":"refs/remotes/origin/work/control-ai-core-20261115",
    "allowed_prefixes":["asterion_remote","tests","docs"],
    "focus_paths":["asterion_remote/native_assistant.py"],
    "push_to_origin":false
  }]
}
The registry is NEVER created, enabled or modified automatically. For fully
unattended cycle processing additionally opt in ASTERION_DEV_AUTORUN=1.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable

from . import overnight_supervisor as ledger
from .development_workbench import GitProject, apply_verified_draft, project_context
from .local_model_provider import LocalModelConfig,LocalModelProvider

_LOCK=threading.RLock()
_RUNS: dict[str,dict]={}
_PENDING:set[str]=set()
_SIGNAL=threading.Event()
_STOP=threading.Event()
_WORKER:threading.Thread|None=None
_MAX_RUNS=40
_SYSTEM=(
    "You are Asterion's locally hosted DEVELOPMENT AGENT, working on "
    "the owner's explicitly authorized Git repository. Respond ONLY with "
    "a JSON object: {\"schema\":1,\"edits\":[{\"path\":\"approved/file.py\","
    "\"expected_sha256\":\"64hex\",\"replace\":{\"old\":\"exact text\","
    "\"new\":\"replacement text\"}}],\"next_work\":\"specific next task\"}. "
    "For a missing file use expected_sha256:\"\" and create:\"new source text\" "
    "instead of replace. You may ONLY edit owner-approved files included "
    "in the tool-provided source context or add files under approved roots. "
    "Make conservative, real incremental improvements. Never invent source "
    "contents, file hashes, test results, device installations or commits. "
    "Your JSON is reviewed against the actual Git bytes before any change. "
    "Do not set done:true: syntactic drafts never prove project completion."
)


def _enabled() -> bool:
    return os.environ.get("ASTERION_DEV_CYCLE_ENABLED","0")=="1"


def _read_registry() -> dict[str,tuple[GitProject,tuple[str,...]]]:
    if not _enabled():
        raise RuntimeError("owner_development_cycle_runtime_disabled")
    location=os.getenv("ASTERION_DEV_PROJECT_REGISTRY","")
    if not location:
        raise RuntimeError("owner_project_registry_not_configured")
    file=Path(location).expanduser()
    if not file.is_absolute() or not file.is_file() or file.stat().st_size>32000:
        raise RuntimeError("owner_project_registry_unavailable")
    data=json.loads(file.read_text("utf-8"))
    if not isinstance(data,dict) or data.get("schema")!=1:
        raise ValueError("invalid_owner_project_registry_schema")
    entries=data.get("projects")
    if not isinstance(entries,list) or not 1<=len(entries)<=20:
        raise ValueError("invalid_owner_project_count")
    out={}
    for item in entries:
        if not isinstance(item,dict) or not isinstance(item.get("focus_paths"),list):
            raise ValueError("invalid_owner_project_entry")
        paths=item["focus_paths"]
        if not 1<=len(paths)<=8 or any(not isinstance(p,str) for p in paths):
            raise ValueError("invalid_project_source_focus")
        policy=GitProject(
            name=item["name"],repository=Path(item["repository"]),
            base_ref=item["base_ref"],
            allowed_prefixes=tuple(item["allowed_prefixes"]),
            push_to_origin=item.get("push_to_origin",False))
        if type(policy.push_to_origin) is not bool:
            raise ValueError("owner_push_approval_must_be_boolean")
        if policy.name in out:
            raise ValueError("duplicate_owner_project_registry_entry")
        out[policy.name]=(policy,tuple(paths))
    return out


def _model() -> LocalModelProvider:
    endpoint=os.getenv("ASTERION_LOCAL_MODEL_ENDPOINT","")
    model_id=os.getenv("ASTERION_LOCAL_MODEL_ID","")
    if not endpoint or not model_id:
        raise RuntimeError("actual_local_development_model_not_configured")
    return LocalModelProvider(LocalModelConfig(
        endpoint=endpoint,model=model_id,max_tokens=4096,
        timeout_s=120,temperature=0.1,system_instruction=_SYSTEM))


def readiness() -> dict:
    if not _enabled():
        return {"configured":False,"state":"OWNER_DISABLED",
                "automatic_progress_claimed":False}
    try:
        registry=_read_registry()
        _model()
    except Exception as exc:
        return {"configured":False,"state":"CONFIGURATION_BLOCKED",
                "reason_code":type(exc).__name__,
                "automatic_progress_claimed":False}
    return {"configured":True,"state":"READY_NOT_RUNNING",
            "registered_projects":list(registry),
            "auto_run_enabled":os.environ.get(
                "ASTERION_DEV_AUTORUN","0")=="1",
            "automatic_progress_claimed":False}


def advance_project(cycle_id:str, *,
                    provider:Callable|None=None,
                    git_executor:Callable|None=None) -> dict:
    """One actual substantive source-draft cycle turn.

    Provider and executor injection is for controlled unit tests. Production
    always uses the fixed local model and real Git checker. A failed model,
    Git error or uncertain external push leaves the durable cycle in review.
    """
    registry=_read_registry()
    status=ledger.status(cycle_id)
    if status["state"]!="ready":
        raise RuntimeError("cycle_not_ready_"+status["state"])
    if status["provider"]!="pc_local":
        raise RuntimeError("only_local_pc_cycles_supported_by_git_driver")
    if status["project"] not in registry:
        raise PermissionError("cycle_project_not_owner_registered")
    policy,focus=registry[status["project"]]
    actual_provider=provider if provider is not None else _model()
    actual_executor=git_executor if git_executor is not None else apply_verified_draft
    # Read actual source with SHA pins BEFORE reserving a turn. A failed
    # read/unauthorized root cannot generate an uncertain submitted cycle.
    source=project_context(policy,cycle_id,focus)

    def get_completion(prompt:str,ident:str)->dict:
        combined=(prompt+"\n\nVERIFIED SOURCE SNAPSHOT:\n"+source)
        return actual_provider(combined,ident)

    def commit_work(content:str,cycle:str,ident:str)->dict:
        result=actual_executor(policy,content,cycle,ident)
        # Only real Git workbench verification may feed these ledger fields.
        return {key:result[key] for key in (
            "evidence_sha256","work_summary","next_work","done",
            "acceptance_verified")}

    return ledger.advance_once(cycle_id,get_completion,commit_work)


def _record(cycle_id:str,details:dict)->None:
    with _LOCK:
        _RUNS[cycle_id]={"cycle_id":cycle_id,**details}
        if len(_RUNS)>_MAX_RUNS:
            for key in list(_RUNS)[:len(_RUNS)-_MAX_RUNS]:
                del _RUNS[key]


def queue_turn(cycle_id:str)->dict:
    if not readiness()["configured"]:
        raise RuntimeError("local_cycle_driver_not_configured")
    state=ledger.status(cycle_id)
    if state["state"]!="ready":
        raise RuntimeError("cycle_not_ready_"+state["state"])
    with _LOCK:
        if cycle_id in _PENDING:
            return {"ok":True,"cycle_id":cycle_id,
                    "state":"already_queued","completed":False}
        if len(_PENDING)>=20:
            raise RuntimeError("cycle_worker_queue_full")
        _PENDING.add(cycle_id)
        _record(cycle_id,{"state":"queued","updated_ms":
                          time.time_ns()//1_000_000})
    _SIGNAL.set()
    return {"ok":True,"cycle_id":cycle_id,
            "state":"queued","completed":False}


def worker_status()->dict:
    with _LOCK:
        return {"runtime_config":readiness(),
                "worker_thread_alive":bool(_WORKER and _WORKER.is_alive()),
                "pending_cycle_ids":sorted(_PENDING),
                "recent_turns":list(_RUNS.values())[-20:],
                "android_app_deployed":False,
                "is_production_claim":False}


def _one_cycle(cycle_id:str)->None:
    _record(cycle_id,{"state":"running","started_ms":
                      time.time_ns()//1_000_000})
    try:
        result=advance_project(cycle_id)
        _record(cycle_id,{"state":result["state"],
                          "verified_turns":result["verified_turns"],
                          "last_error_code":result["last_error_code"],
                          "updated_ms":time.time_ns()//1_000_000})
    except Exception as exc:
        _record(cycle_id,{"state":"blocked",
                          "reason_code":type(exc).__name__,
                          "updated_ms":time.time_ns()//1_000_000})
    finally:
        with _LOCK:
            _PENDING.discard(cycle_id)


def _loop()->None:
    while not _STOP.is_set():
        with _LOCK:
            queue=list(_PENDING)
        if (not queue and os.getenv("ASTERION_DEV_AUTORUN","0")=="1"
                and readiness()["configured"]):
            try:
                registry=_read_registry()
                for state in ledger.recent(100):
                    if (state["state"]=="ready" and
                        state["project"] in registry and
                        state["provider"]=="pc_local"):
                        queue.append(state["cycle_id"])
            except Exception:
                pass
        for ident in queue:
            if _STOP.is_set():break
            _one_cycle(ident)
        _SIGNAL.wait(timeout=5)
        _SIGNAL.clear()


def start()->dict:
    """Startup is inert unless owner explicitly enabled driver + registry."""
    global _WORKER
    r=readiness()
    if not r["configured"]:
        return r
    with _LOCK:
        if _WORKER is not None and _WORKER.is_alive():
            return worker_status()
        _STOP.clear()
        _WORKER=threading.Thread(
            target=_loop,daemon=True,name="asterion-dev-cycle-worker")
        _WORKER.start()
    return {"configured":True,"state":"WORKER_STARTED",
            "autorun":os.getenv("ASTERION_DEV_AUTORUN","0")=="1"}


def stop(wait_s:float=3)->None:
    global _WORKER
    _STOP.set()
    _SIGNAL.set()
    thread=_WORKER
    if thread:
        thread.join(timeout=wait_s)
    if thread is None or not thread.is_alive():
        _WORKER=None
