"""Authenticated Control diagnostic query and event ingestion API."""
from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field, ConfigDict
from .security import require_token
from . import diagnostic_core as core
from . import diagnostic_analysis
from . import diagnostic_snapshot

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


@router.get("/snapshot")
def snapshot(app: str = "", limit: int = 600, lookback_minutes: int = 1440,
             phone: bool = True):
    """One bounded read-only PC and paired Android diagnostic observation."""
    try:
        return diagnostic_snapshot.collect(
            app=app, limit=limit, lookback_minutes=lookback_minutes, phone=phone)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/triage")
def triage(app: str = "", lookback_minutes: int = 1440, limit: int = 1200,
           stale_after_seconds: int = 300):
    """Read-only diagnostic correlation, never a current device-health claim."""
    try:
        return diagnostic_analysis.inspect(
            app=app, lookback_minutes=lookback_minutes, limit=limit,
            stale_after_seconds=stale_after_seconds)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


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


def sse_message(event: str, value: dict, event_id: int | None = None) -> str:
    """Encode bounded event payload without unescaped SSE newlines."""
    if event not in {"ready","event","gap"}:
        raise ValueError("Unsupported SSE event kind")
    # No raw logs, URLs or user media; diagnostic_core already sanitizes metadata.
    body=json.dumps(value,ensure_ascii=True,separators=(",",":"),allow_nan=False)
    if len(body)>12000:
        raise ValueError("Diagnostic event too large")
    identity=(f"id: {event_id}\n" if event_id is not None else "")
    return identity+f"event: {event}\ndata: {body}\n\n"


@router.get("/stream")
async def live_events(request: Request, since: int | None = None,
                      app: str = "", trace_id: str = ""):
    """Authenticated bounded SSE; durable Last-Event-ID resume, no video polling."""
    cursor=since
    if cursor is None:
        last=request.headers.get("last-event-id","0")
        if not last.isascii() or not last.isdecimal() or len(last)>19:
            raise HTTPException(422,"Invalid resume event ID")
        cursor=int(last)
    if cursor<0 or cursor>=2**62:
        raise HTTPException(422,"Invalid cursor")
    if app and (len(app)>96 or core._safe_id(app)!=app):
        raise HTTPException(422,"Invalid app filter")
    if trace_id and (len(trace_id)>96 or core._safe_id(trace_id)!=trace_id):
        raise HTTPException(422,"Invalid trace ID")

    async def stream():
        nonlocal cursor
        yield sse_message("ready",{"schema_version":1,**core.bounds(),
                                    "app_filter":app or None,"trace_filter":trace_id or None})
        while not await request.is_disconnected():
            state=core.bounds()
            if cursor>0 and state["oldest_sequence"]>cursor+1:
                yield sse_message("gap",{"requested_after":cursor,
                       "oldest_retained":state["oldest_sequence"],
                       "dropped":state["oldest_sequence"]-cursor-1})
                cursor=state["oldest_sequence"]-1
            page=core.events(since=cursor,limit=100,app=app,trace_id=trace_id)
            if page["events"]:
                for event in page["events"]:
                    cursor=event["seq"]
                    yield sse_message("event",event,cursor)
                continue
            # On filtered streams a newer event for another app must not
            # produce a busy spin. Advance to latest cursor, then wait for
            # the next committed event. The core is a durable event ledger.
            cursor=max(cursor,state["latest_sequence"])
            changed=await asyncio.to_thread(core.wait_for_change,cursor,8.0)
            if not changed:
                yield ": keepalive\n\n"

    return StreamingResponse(stream(),media_type="text/event-stream",
        headers={"Cache-Control":"no-cache, no-store",
                 "X-Accel-Buffering":"no",
                 "X-Content-Type-Options":"nosniff",
                 "Connection":"keep-alive"})


@router.get("/incidents/{incident_id}/bundle")
def get_incident_bundle(incident_id: str):
    try:
        data=core.incident_bundle(incident_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(500,"Incident evidence integrity failure") from exc
    if data is None:
        raise HTTPException(404,"Incident not found")
    return data


@router.get("/incidents/{incident_id}/export")
def export_incident_bundle(incident_id: str):
    # Download only immutable, redacted evidence from the authenticated API.
    # Export digest is the content hash (not an unverified summary claim).
    result=get_incident_bundle(incident_id)
    body=json.dumps(result["evidence"],sort_keys=True,
                    separators=(",",":"),ensure_ascii=True).encode("utf8")
    from hashlib import sha256
    digest=sha256(body).hexdigest()
    if digest!=result["evidence_sha256"]:
        raise HTTPException(500,"Incident export checksum mismatch")
    return Response(content=body,media_type="application/json",headers={
        "Cache-Control":"no-store",
        "Content-Disposition":f'attachment; filename="asterion-incident-{incident_id}.json"',
        "X-Content-SHA256":digest,
        "X-Content-Type-Options":"nosniff",
    })


@router.get("/traces/{trace_id}")
def read_trace(trace_id: str, limit: int = 200):
    try:
        return core.trace_events(trace_id,limit)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
