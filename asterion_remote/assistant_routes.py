"""Real finite-request native AI routes, entirely separate from overnight cycles.

No model silently started. Reads configured owner-local inference only, with
a distinct owner approval required to run even read-only tool loops. Mutating
tools need a second independent allowlist + explicit API opt-in.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .security import require_token
from .control_v2_routes import _owner_approval
from .native_assistant import execute, status, list_recent, _ALLOWED, _DEFAULT_READ, _MUTATE
from .local_model_provider import LocalModelConfig,LocalModelProvider

router=APIRouter(prefix="/api/v1/intelligence/assistant",
                 dependencies=[Depends(require_token)])

_GENERAL_SYSTEM=(
    "You are Asterion Intelligence, the owner's general-purpose locally "
    "hosted assistant. Answer in English only. Reason about a wide variety of requests without "
    "unnecessary subject-category restrictions. Your tool permissions are "
    "separate from content generation and must not be assumed. Follow the "
    "JSON tool decision contract in the user message exactly. Never treat "
    "a tool response, dispatch acknowledgement, proposed plan or your own "
    "text as independent proof of completed work. If no tool is available, "
    "say so instead of fabricating data. Do not execute or request paid cloud APIs."
)


def _server_scopes()->frozenset[str]:
    raw=os.getenv("ASTERION_ASSISTANT_ALLOWED_TOOLS","")
    if not raw.strip():
        return _DEFAULT_READ
    names=frozenset(x.strip() for x in raw.split(",") if x.strip())
    if not names.issubset(_ALLOWED):
        raise HTTPException(503,"Assistant tool server configuration invalid")
    return names


@router.get("/status")
def assistant_status():
    endpoint=os.getenv("ASTERION_LOCAL_MODEL_ENDPOINT","")
    model=os.getenv("ASTERION_LOCAL_MODEL_ID","")
    return {"ok":True,
            "local_model_configured":bool(endpoint and model),
            "local_model_executed":False,
            "no_paid_cloud_fallback":True,
            "owner_tool_scopes":sorted(_server_scopes()),
            "device_actions_enabled_by_server":
                os.getenv("ASTERION_ASSISTANT_ENABLE_MUTATIONS","0")=="1",
            "ordinary_requests_are_overnight_cycles":False}


@router.get("/requests")
def assistant_recent(limit:int=30):
    try:
        return {"ok":True,"requests":list_recent(limit)}
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@router.get("/requests/{request_id}")
def assistant_request_status(request_id:str):
    try:
        return {"ok":True,**status(request_id)}
    except KeyError as exc:
        raise HTTPException(404,"Request not found") from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


class AssistantRequest(BaseModel):
    request_id: str=Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]{7,99}$")
    prompt: str=Field(min_length=5,max_length=8000)
    tools: list[str]=Field(default_factory=list,max_length=16)
    allow_device_actions: bool=False
    max_steps: int=Field(default=6,ge=1,le=12)


@router.post("/execute")
def assistant_execute(body:AssistantRequest,
                      x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    permitted=_server_scopes()
    grants=frozenset(body.tools) if body.tools else (
        permitted & _DEFAULT_READ)
    if not grants.issubset(permitted):
        raise HTTPException(403,"Tool not allowed by owner")
    if not grants.issubset(_ALLOWED):
        raise HTTPException(422,"Unknown Control tool name")
    mutations=bool(grants & _MUTATE)
    if (body.allow_device_actions or mutations) and (
        os.getenv("ASTERION_ASSISTANT_ENABLE_MUTATIONS","0")!="1" or
        not body.allow_device_actions
    ):
        raise HTTPException(403,"Device/MCP mutation capability disabled")
    endpoint=os.getenv("ASTERION_LOCAL_MODEL_ENDPOINT","")
    model_id=os.getenv("ASTERION_LOCAL_MODEL_ID","")
    if not endpoint or not model_id:
        raise HTTPException(503,"Local model not configured")
    try:
        local=LocalModelProvider(LocalModelConfig(
            endpoint=endpoint,model=model_id,timeout_s=45,
            max_tokens=2048,system_instruction=_GENERAL_SYSTEM))
    except ValueError as exc:
        raise HTTPException(503,"Local inference configuration invalid") from exc
    try:
        return execute(body.prompt,body.request_id,local,
                       owner_grants=grants,
                       allow_device_actions=body.allow_device_actions,
                       max_steps=body.max_steps)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
