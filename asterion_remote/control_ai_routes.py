"""Authenticated source-stage API for independent local AI and cycle state.

This is an ADDITIVE Windows-side route set, not a replacement for the paired
Android cycle or Windows worker. Starting a cycle only creates a checkpoint;
it does not silently start a paid API, schedule background work or generate a
false "active overnight" status. Actual project progression requires a bound
and tested work executor (overnight_supervisor.advance_once).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .security import require_token
from .control_v2_routes import _owner_approval
from . import overnight_supervisor, development_cycle_driver, model_watch_service
from .local_model_provider import LocalModelConfig, LocalModelProvider

router = APIRouter(prefix="/api/v1/intelligence",
                   dependencies=[Depends(require_token)])


class CycleRequest(BaseModel):
    cycle_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{3,63}$")
    project: str = Field(min_length=3,max_length=70)
    spec_reference: str = Field(min_length=3,max_length=250)
    objective: str = Field(min_length=12,max_length=3000)
    provider: str = Field(default="pc_local",pattern=r"^(pc_local|phone_local|chatgpt)$")
    max_turns: int = Field(default=0,ge=0,le=100000)


@router.get("/model-watch/status")
def model_release_watch_status():
    return {"ok":True,**model_watch_service.status()}


@router.get("/model-watch/events")
def model_release_events(limit:int=30):
    try:return model_watch_service.events(limit)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.post("/model-watch/refresh")
def model_release_check_now(x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:return model_watch_service.scan_once(limit=20)
    except Exception as exc:
        raise HTTPException(503,"Model release metadata unavailable: "+
                            type(exc).__name__) from exc


@router.post("/model-watch/events/{event_id}/ack")
def model_release_ack(event_id:str,
                      x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:return model_watch_service.acknowledge(event_id)
    except KeyError as exc:raise HTTPException(404,"Event not found") from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.get("/autonomy/status")
def autonomous_cycle_worker_status():
    return {"ok":True,**development_cycle_driver.worker_status()}


@router.post("/cycles/{cycle_id}/advance")
def advance_development_cycle(cycle_id:str,
                              x_owner_approval:str|None=Header(default=None)):
    """Queue a REAL Git development turn, never claim it completed on ACK."""
    _owner_approval(x_owner_approval)
    try:
        prepared=development_cycle_driver.start()
        if not prepared.get("configured",False):
            raise HTTPException(503,"Owner-local model or Git workbench not configured")
        return development_cycle_driver.queue_turn(cycle_id)
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(404,"Development cycle not found") from exc
    except PermissionError as exc:
        raise HTTPException(403,type(exc).__name__) from exc
    except (ValueError,RuntimeError) as exc:
        raise HTTPException(409,type(exc).__name__) from exc


@router.get("/cycles")
def cycles(limit: int = 30):
    try:
        return {"ok":True,"items":overnight_supervisor.recent(limit),
                "kind":"continuous_project_development"}
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post("/cycles")
def create_cycle(body: CycleRequest,
                 x_owner_approval: str | None = Header(default=None)):
    _owner_approval(x_owner_approval)
    try:
        item = overnight_supervisor.create(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except Exception as exc:
        if type(exc).__name__=="IntegrityError":
            raise HTTPException(409,"Cycle ID already exists") from exc
        raise
    driver=development_cycle_driver.readiness()
    bound=driver.get("configured",False) and item["project"] in driver.get(
        "registered_projects",[])
    return {"ok":True,**item,
            "provider_executor_bound":bound,
            "automatic_turns_running":False,
            "next_step":"Owner-approved development cycle worker can execute source drafts"
                if bound else "Configure owner-local AI model and registered Git project"}


@router.get("/cycles/{cycle_id}")
def cycle_status(cycle_id: str):
    try:
        item=overnight_supervisor.status(cycle_id)
        recent=development_cycle_driver.worker_status()["recent_turns"]
        running=any(entry.get("cycle_id")==cycle_id and
                    entry.get("state")=="running" for entry in recent)
        return {"ok":True,**item,
                "automatic_turns_running":running}
    except KeyError as exc:
        raise HTTPException(404,"Cycle not found") from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


def _transition(cycle_id: str, fn):
    try:
        return {"ok":True,**fn(cycle_id)}
    except KeyError as exc:
        raise HTTPException(404,"Cycle not found") from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post("/cycles/{cycle_id}/pause")
def pause_cycle(cycle_id: str,
                x_owner_approval: str | None = Header(default=None)):
    _owner_approval(x_owner_approval)
    return _transition(cycle_id,overnight_supervisor.pause)


@router.post("/cycles/{cycle_id}/resume")
def resume_cycle(cycle_id: str,
                 x_owner_approval: str | None = Header(default=None)):
    _owner_approval(x_owner_approval)
    return _transition(cycle_id,overnight_supervisor.resume)


@router.post("/cycles/{cycle_id}/stop")
def stop_cycle(cycle_id: str,
               x_owner_approval: str | None = Header(default=None)):
    _owner_approval(x_owner_approval)
    return _transition(cycle_id,overnight_supervisor.stop)


class LocalInferenceRequest(BaseModel):
    prompt: str = Field(min_length=20,max_length=12000)
    request_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{7,99}$")
    max_tokens: int = Field(default=1024,ge=16,le=4096)


@router.post("/local-model/complete")
def local_complete(body:LocalInferenceRequest,
                   x_owner_approval:str|None=Header(default=None)):
    """Actual local-model inference if and only if the owner already serves one."""
    _owner_approval(x_owner_approval)
    endpoint=os.getenv("ASTERION_LOCAL_MODEL_ENDPOINT","")
    model=os.getenv("ASTERION_LOCAL_MODEL_ID","")
    if not endpoint or not model:
        raise HTTPException(503,"Local model not configured on this host")
    try:
        provider=LocalModelProvider(LocalModelConfig(
            endpoint=endpoint,model=model,max_tokens=body.max_tokens))
        result=provider(body.prompt,body.request_id)
        return {"ok":True,**result,"project_work_verified":False,
                "tool_execution_performed":False}
    except (ValueError,TypeError) as exc:
        raise HTTPException(422,type(exc).__name__) from exc
    except Exception as exc:
        # Never echo local prompt, model response, token, endpoint or URLs.
        raise HTTPException(503,"Local inference unavailable: "+
                            type(exc).__name__) from exc
