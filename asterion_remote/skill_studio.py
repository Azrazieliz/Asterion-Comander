"""Asterion Skill Studio: signed-by-content skill library using existing Control steps.

A skill is a validated *deterministic* workflow. An owner-approved skill can be
executed via the existing session engine; no arbitrary shell/Python eval, no
automatic activation of model-generated commands, no fake tool invocations.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from pydantic import ValidationError

from .interaction_sessions import SessionRequest

_LOCK=threading.RLock()
_ID=re.compile(r"^[a-z][a-z0-9_:-]{3,71}$")
_SHA=re.compile(r"^[0-9a-f]{64}$")
_LIMIT=100


def _db():
    root=Path(os.getenv("ASTERION_SKILL_STUDIO_ROOT",str(
        Path(os.getenv("LOCALAPPDATA",str(Path.home())))/
        "AsterionControl"/"skill-studio")))
    root.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(root/"skills.sqlite3"),timeout=5,isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("""CREATE TABLE IF NOT EXISTS skills(
      id TEXT PRIMARY KEY,version INTEGER NOT NULL,
      sha256 TEXT NOT NULL, definition TEXT NOT NULL,
      state TEXT NOT NULL,
      created_ms INTEGER NOT NULL,approved_ms INTEGER NOT NULL DEFAULT 0,
      executions INTEGER NOT NULL DEFAULT 0)""")
    db.row_factory=sqlite3.Row
    return db


def _canonical(doc:dict)->str:
    return json.dumps(doc,sort_keys=True,separators=(",",":"),ensure_ascii=True)


def _valid_id(skill_id:str):
    if not isinstance(skill_id,str) or not _ID.fullmatch(skill_id):
        raise ValueError("invalid_skill_identifier")


def create(skill_id:str, description:str, device:str,
           steps:list[dict],timeout_s:int=120)->dict:
    _valid_id(skill_id)
    if not isinstance(description,str) or not 4<=len(description)<=180:
        raise ValueError("invalid_skill_description")
    if not isinstance(steps,list) or not 1<=len(steps)<=80:
        raise ValueError("invalid_skill_steps")
    try:
        req=SessionRequest(device=device,steps=steps,timeout_s=timeout_s)
    except ValidationError as exc:
        raise ValueError("invalid_native_workflow") from exc
    clean=req.model_dump(mode="json",exclude_none=True)
    # Skills may operate across both owner devices, but only previously
    # supported step types. Free-text inputs are stored locally, never exported
    # to a model registry or UI index.
    doc={"schema_version":1,"description":description,**clean}
    serialized=_canonical(doc)
    if len(serialized)>32_000:raise ValueError("skill_definition_too_large")
    digest=hashlib.sha256(serialized.encode("utf8")).hexdigest()
    with _LOCK:
        db=_db()
        try:
            old=db.execute("SELECT version FROM skills WHERE id=?",(skill_id,)).fetchone()
            ver=old["version"]+1 if old else 1
            db.execute("""INSERT INTO skills(id,version,sha256,definition,state,
              created_ms,approved_ms,executions) VALUES(?,?,?,?,?,?,0,0)
              ON CONFLICT(id) DO UPDATE SET version=excluded.version,
              sha256=excluded.sha256,definition=excluded.definition,
              state='draft',created_ms=excluded.created_ms,approved_ms=0""",
              (skill_id,ver,digest,serialized,"draft",time.time_ns()//1000000))
        finally:db.close()
    return {"ok":True,"id":skill_id,"version":ver,
            "sha256":digest,"state":"draft","owner_approval_required":True}


def index(limit:int=40)->dict:
    if not 1<=limit<=_LIMIT:raise ValueError("invalid_limit")
    with _LOCK:
        db=_db()
        try:
            rows=db.execute("""SELECT id,version,sha256,state,created_ms,
                approved_ms,executions FROM skills ORDER BY created_ms DESC LIMIT ?""",
                (limit,)).fetchall()
            items=[dict(x) for x in rows]
        finally:db.close()
    return {"ok":True,"items":items}


def details(skill_id:str)->dict:
    _valid_id(skill_id)
    with _LOCK:
        db=_db()
        try:
            x=db.execute("SELECT * FROM skills WHERE id=?",(skill_id,)).fetchone()
            if not x:raise KeyError(skill_id)
            row=dict(x)
        finally:db.close()
    row["definition"]=json.loads(row["definition"])
    return {"ok":True,**row}


def approve(skill_id:str,expected_sha256:str)->dict:
    """Requires an owner-authorized authenticated Control operation."""
    _valid_id(skill_id)
    if not _SHA.fullmatch(expected_sha256):raise ValueError("invalid_sha256")
    with _LOCK:
        db=_db()
        try:
            entry=db.execute("SELECT sha256 FROM skills WHERE id=?",
                             (skill_id,)).fetchone()
            if not entry:raise KeyError(skill_id)
            if entry["sha256"]!=expected_sha256:
                raise ValueError("definition_changed_before_approval")
            db.execute("""UPDATE skills SET state='approved',approved_ms=?
              WHERE id=?""",(time.time_ns()//1000000,skill_id))
        finally:db.close()
    return {"ok":True,"id":skill_id,"state":"approved",
            "sha256":expected_sha256}


def revoke(skill_id:str)->dict:
    _valid_id(skill_id)
    with _LOCK:
        db=_db()
        try:
            updated=db.execute("UPDATE skills SET state='revoked' WHERE id=?",
                               (skill_id,))
            if updated.rowcount==0:raise KeyError(skill_id)
        finally:db.close()
    return {"ok":True,"id":skill_id,"state":"revoked"}


def execute(skill_id:str,expected_sha256:str,request_id:str)->dict:
    """Submit a locally approved, frozen workflow; return real session receipt."""
    _valid_id(skill_id)
    if not _SHA.fullmatch(expected_sha256):raise ValueError("invalid_sha256")
    entry=details(skill_id)
    if entry["state"]!="approved" or entry["sha256"]!=expected_sha256:
        raise PermissionError("skill_not_approved_or_changed")
    request=entry["definition"]
    from .interaction_sessions import start
    # The same request ID must preserve the prior execution across retries.
    session=SessionRequest(device=request["device"],
        steps=request["steps"],timeout_s=request["timeout_s"],
        stop_on_error=request.get("stop_on_error",True),
        request_id=request_id)
    result=start(session)
    if not result.get("reused",False):
        with _LOCK:
            db=_db()
            try:db.execute("UPDATE skills SET executions=executions+1 WHERE id=?",
                           (skill_id,))
            finally:db.close()
    return {"ok":True,"skill":skill_id,"sha256":expected_sha256,
            "session":result,"verification":"session_outcome_pending"}
