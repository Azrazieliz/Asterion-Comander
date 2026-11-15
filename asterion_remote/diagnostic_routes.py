"""Authenticated Control diagnostic query and event ingestion API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from .security import require_token
from . import diagnostic_core as core

router = APIRouter(prefix="/api/v1/diagnostics",dependencies=[Depends(require_token)])


class DiagnosticEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1,max_length=96,pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")
    app: str = Field(default="asterion.control",max_length=96)
    component: str = Field(default="worker",max_length=96)
    state: str = Field(default="observed",max_length=96)
    severity: str = Field(default="info",max_length=10)
    session_id: str = Field(default="",max_length=96)
    trace_id: str = Field(default="",max_length=96)
    operation_id: str = Field(default="",max_length=96)
    attributes: dict = Field(default_factory=dict)
    incident: bool = False


@router.get("/health")
def health():
    return core.health()


@router.get("/events")
def events(since: int = 0, limit: int = 100, app: str = "", trace_id: str = ""):
    try:
        return core.events(since=since,limit=limit,app=app,trace_id=trace_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@router.get("/incidents")
def incidents(limit: int = 100, app: str = ""):
    try:
        return core.incidents(limit=limit,app=app)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post("/events")
def submit_event(event: DiagnosticEvent):
    try:
        return core.record(**event.model_dump())
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
