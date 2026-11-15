"""Crash-safe deterministic native session receipts and replay protection.

The journal never persists input text, screenshots, filenames, authorization
headers or freeform UI observations. Following a worker restart, an in-flight
command is flagged OUTCOME_UNKNOWN; mutating operations are NEVER replayed.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path

_GUARD = threading.RLock()
_EPOCH = uuid.uuid4().hex
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,99}$")
_TERMINAL = {"completed", "cancelled", "failed", "timed_out", "outcome_unknown"}


def _db_path() -> Path:
    default = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AsterionControl" / "diagnostics"
    path = Path(os.getenv("ASTERION_DIAGNOSTIC_ROOT", str(default)))
    path.mkdir(parents=True, exist_ok=True)
    return path / "sessions.sqlite3"


def _connection():
    db = sqlite3.connect(str(_db_path()), timeout=5, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id TEXT PRIMARY KEY,
        client_request_id TEXT UNIQUE,
        worker_epoch TEXT NOT NULL,
        device TEXT NOT NULL,
        state TEXT NOT NULL,
        steps_total INTEGER NOT NULL,
        current_step INTEGER NOT NULL,
        completed_steps INTEGER NOT NULL,
        failed_steps INTEGER NOT NULL,
        created_at_ms INTEGER NOT NULL,
        updated_at_ms INTEGER NOT NULL,
        elapsed_ms REAL,
        failure_class TEXT NOT NULL DEFAULT ''
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_session_recent ON sessions(updated_at_ms)")
    return db


def _public(row: sqlite3.Row) -> dict:
    state = row["state"]
    if state not in _TERMINAL and row["worker_epoch"] != _EPOCH:
        state = "outcome_unknown"
    return {
        "id": row["id"],
        "client_request_id": row["client_request_id"],
        "device": row["device"],
        "state": state,
        "steps_total": row["steps_total"],
        "current_step": row["current_step"],
        "completed_steps": row["completed_steps"],
        "failed_steps": row["failed_steps"],
        "created_at_ms": row["created_at_ms"],
        "updated_at_ms": row["updated_at_ms"],
        "elapsed_ms": row["elapsed_ms"],
        "failure_class": row["failure_class"],
        "source": "durable_worker_receipt",
        "inputs_persisted": False,
        "replay_allowed": False,
    }


def _row(db, clause, key):
    db.row_factory = sqlite3.Row
    value = db.execute("SELECT * FROM sessions WHERE "+clause, (key,)).fetchone()
    return _public(value) if value else None


def reserve(ident: str, device: str, steps_total: int, request_id: str | None = None) -> tuple[dict, bool]:
    """Atomically reserve a unique request, returning prior receipt on replay."""
    if not _SAFE.fullmatch(ident):
        raise ValueError("Invalid internal session ID")
    if request_id is not None and not _SAFE.fullmatch(request_id):
        raise ValueError("Invalid caller idempotency key")
    if device not in {"phone", "pc", "mixed"} or not 1 <= steps_total <= 80:
        raise ValueError("Invalid requested session")
    now = time.time_ns() // 1_000_000
    with _GUARD:
        db = _connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            if request_id:
                old = _row(db, "client_request_id=?", request_id)
                if old:
                    db.execute("COMMIT")
                    return old, True
            db.execute("""INSERT INTO sessions(id,client_request_id,worker_epoch,device,state,
                steps_total,current_step,completed_steps,failed_steps,created_at_ms,updated_at_ms)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (ident,request_id,_EPOCH,device,"queued",steps_total,0,0,0,now,now))
            result = _row(db, "id=?", ident)
            db.execute("COMMIT")
            return result, False
        except BaseException:
            db.execute("ROLLBACK")
            raise
        finally:
            db.close()


def progress(ident: str, *, state: str, current_step: int = 0,
             completed_steps: int = 0, failed_steps: int = 0,
             elapsed_ms: float | None = None, failure_class: str = "") -> dict:
    if state not in {"queued","running","cancelling",*_TERMINAL}:
        raise ValueError("Unsupported session state")
    if not _SAFE.fullmatch(ident):
        raise ValueError("Invalid session ID")
    if not re.fullmatch(r"[A-Za-z0-9_]{0,64}", failure_class):
        failure_class = "RedactedFailure"
    with _GUARD:
        db = _connection()
        try:
            now=time.time_ns() // 1_000_000
            db.execute("""UPDATE sessions SET state=?,current_step=?,completed_steps=?,
                failed_steps=?,elapsed_ms=?,failure_class=?,updated_at_ms=?
                WHERE id=? AND worker_epoch=?""",
                (state,current_step,completed_steps,failed_steps,elapsed_ms,failure_class,
                 now,ident,_EPOCH))
            result = _row(db, "id=?", ident)
            if result is None:
                raise KeyError(ident)
            return result
        finally:
            db.close()


def get(ident: str) -> dict | None:
    if not _SAFE.fullmatch(ident):
        return None
    with _GUARD:
        db=_connection()
        try:
            return _row(db,"id=?",ident)
        finally:
            db.close()


def recent(limit: int = 30) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("Invalid receipt count")
    with _GUARD:
        db=_connection()
        try:
            db.row_factory=sqlite3.Row
            rows=db.execute("SELECT * FROM sessions ORDER BY updated_at_ms DESC LIMIT ?",(limit,))
            return [_public(row) for row in rows]
        finally:
            db.close()


def reserve_if_new(request_id: str | None) -> dict | None:
    if not request_id:
        return None
    if not _SAFE.fullmatch(request_id):
        raise ValueError("Invalid idempotency key")
    with _GUARD:
        db=_connection()
        try:
            return _row(db,"client_request_id=?",request_id)
        finally:
            db.close()
