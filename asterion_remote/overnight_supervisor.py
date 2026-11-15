"""Persistent, provider-neutral OVERNIGHT PROJECT DEVELOPMENT cycles.

A cycle is a sequence of substantial, verified project-work turns, not a UI
gesture or an ordinary finite task. This module has no background thread,
ChatGPT UI automation, paid API, shell execution or model download.

The caller must supply (1) an actual AI provider and (2) an owner-authorized
work executor returning independently checked evidence. Without both, a cycle
cannot claim to have advanced a project. Every uncertain submission is
fail-closed and is never silently replayed.

The existing Android ContinuationCycle remains a separate ChatGPT UI adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

_LOCK = threading.RLock()
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{3,63}$")
_PROJECT = re.compile(r"^[A-Za-z0-9_.-]{3,70}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_PROVIDER = {"phone_local", "pc_local", "chatgpt"}
_CYCLE_STATES = {
    "ready", "paused", "dispatch_uncertain", "awaiting_verification",
    "needs_review", "finished", "turn_limit_reached", "stopped",
}
_MAX_HISTORY = 50


def _now() -> int:
    return time.time_ns() // 1_000_000


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _root() -> Path:
    base = Path(os.getenv(
        "ASTERION_OVERNIGHT_ROOT",
        str(Path(os.getenv("LOCALAPPDATA", str(Path.home())))
            / "AsterionControl" / "overnight-cycles"),
    )).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(_root() / "cycles.sqlite3"),
                          timeout=8, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=8000")
    con.execute("PRAGMA synchronous=FULL")
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS cycles(
      id TEXT PRIMARY KEY,
      project TEXT NOT NULL,
      spec_ref TEXT NOT NULL,
      provider TEXT NOT NULL,
      objective TEXT NOT NULL,
      next_work TEXT NOT NULL,
      state TEXT NOT NULL,
      pause_requested INTEGER NOT NULL DEFAULT 0,
      stop_requested INTEGER NOT NULL DEFAULT 0,
      turn_index INTEGER NOT NULL DEFAULT 0,
      verified_turns INTEGER NOT NULL DEFAULT 0,
      max_turns INTEGER NOT NULL DEFAULT 0,
      created_ms INTEGER NOT NULL,
      updated_ms INTEGER NOT NULL,
      last_error_code TEXT NOT NULL DEFAULT '',
      completion_evidence_sha256 TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS turns(
      request_id TEXT PRIMARY KEY,
      cycle_id TEXT NOT NULL,
      turn_index INTEGER NOT NULL,
      state TEXT NOT NULL,
      prompt_sha256 TEXT NOT NULL,
      provider_receipt TEXT NOT NULL DEFAULT '',
      response_sha256 TEXT NOT NULL DEFAULT '',
      evidence_sha256 TEXT NOT NULL DEFAULT '',
      work_summary TEXT NOT NULL DEFAULT '',
      next_work TEXT NOT NULL DEFAULT '',
      acceptance_verified INTEGER NOT NULL DEFAULT 0,
      started_ms INTEGER NOT NULL,
      updated_ms INTEGER NOT NULL,
      UNIQUE(cycle_id,turn_index),
      FOREIGN KEY(cycle_id) REFERENCES cycles(id)
    );
    CREATE INDEX IF NOT EXISTS cycle_recent ON cycles(updated_ms DESC);
    """)
    return con


def _require_id(cycle_id: str) -> None:
    if not isinstance(cycle_id, str) or not _ID.fullmatch(cycle_id):
        raise ValueError("invalid_cycle_identifier")


def _public(row: sqlite3.Row) -> dict:
    return {
        "cycle_id": row["id"], "project": row["project"],
        "spec_reference": row["spec_ref"], "provider": row["provider"],
        "state": row["state"],
        "pause_requested": bool(row["pause_requested"]),
        "stop_requested": bool(row["stop_requested"]),
        "turn_index": row["turn_index"],
        "verified_turns": row["verified_turns"],
        "max_turns": row["max_turns"],
        "created_ms": row["created_ms"], "updated_ms": row["updated_ms"],
        "last_error_code": row["last_error_code"],
        "completion_evidence_sha256": row["completion_evidence_sha256"],
        "is_development_cycle": True,
        "is_normal_action": False,
        "is_bounded_task": False,
        "automatic_progress_verified": row["verified_turns"] > 0,
        "replay_allowed": row["state"] == "ready",
    }


def create(cycle_id: str, project: str, spec_reference: str,
           objective: str, *, provider: str = "pc_local",
           max_turns: int = 0) -> dict:
    """Register an explicitly authorized project cycle. Does NOT run it."""
    _require_id(cycle_id)
    if not _PROJECT.fullmatch(project):
        raise ValueError("invalid_project")
    if not isinstance(spec_reference, str) or not 3 <= len(spec_reference) <= 250:
        raise ValueError("invalid_spec_reference")
    if not isinstance(objective, str) or not 12 <= len(objective) <= 3000:
        raise ValueError("invalid_objective")
    if provider not in _ALLOWED_PROVIDER:
        raise ValueError("unsupported_provider")
    if not isinstance(max_turns, int) or not 0 <= max_turns <= 100000:
        raise ValueError("invalid_turn_limit")
    stamp = _now()
    with _LOCK:
        con = _db()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("""INSERT INTO cycles
                (id,project,spec_ref,provider,objective,next_work,state,
                 created_ms,updated_ms,max_turns)
                VALUES(?,?,?,?,?,?, 'ready',?,?,?)""",
                (cycle_id, project, spec_reference, provider, objective,
                 objective, stamp, stamp, max_turns))
            row = con.execute("SELECT * FROM cycles WHERE id=?",
                              (cycle_id,)).fetchone()
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
    return _public(row)


def status(cycle_id: str) -> dict:
    _require_id(cycle_id)
    with _LOCK:
        con = _db()
        try:
            row = con.execute("SELECT * FROM cycles WHERE id=?",
                              (cycle_id,)).fetchone()
            if row is None:
                raise KeyError(cycle_id)
            result = _public(row)
            receipt = con.execute(
                """SELECT request_id,state,provider_receipt,response_sha256,
                    evidence_sha256,work_summary,acceptance_verified,started_ms,
                    updated_ms FROM turns WHERE cycle_id=?
                    ORDER BY turn_index DESC LIMIT 1""", (cycle_id,)
            ).fetchone()
            result["last_turn"] = dict(receipt) if receipt else None
            return result
        finally:
            con.close()


def recent(limit: int = 30) -> list[dict]:
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("invalid_limit")
    with _LOCK:
        con = _db()
        try:
            return [_public(row) for row in con.execute(
                "SELECT * FROM cycles ORDER BY updated_ms DESC LIMIT ?",
                (limit,))]
        finally:
            con.close()


def pause(cycle_id: str) -> dict:
    """Stop NEXT turns immediately; do not interrupt an uncertain in-flight send."""
    _require_id(cycle_id)
    with _LOCK:
        con = _db()
        try:
            con.execute("""UPDATE cycles SET pause_requested=1,
                state=CASE WHEN state='ready' THEN 'paused' ELSE state END,
                updated_ms=? WHERE id=? AND
                state NOT IN ('finished','stopped','turn_limit_reached')""",
                (_now(), cycle_id))
        finally:
            con.close()
    return status(cycle_id)


def resume(cycle_id: str) -> dict:
    """Resume an owner-paused cycle without replaying pending sends."""
    _require_id(cycle_id)
    with _LOCK:
        con = _db()
        try:
            con.execute("""UPDATE cycles SET pause_requested=0,
                state=CASE WHEN state='paused' THEN 'ready' ELSE state END,
                updated_ms=?
                WHERE id=? AND stop_requested=0 AND
                state NOT IN ('finished','stopped','turn_limit_reached')""",
                (_now(), cycle_id))
        finally:
            con.close()
    return status(cycle_id)


def stop(cycle_id: str) -> dict:
    """Request stop without deleting evidence of an in-flight operation."""
    _require_id(cycle_id)
    with _LOCK:
        con = _db()
        try:
            con.execute("""UPDATE cycles SET stop_requested=1,
                state=CASE WHEN state IN ('ready','paused')
                   THEN 'stopped' ELSE state END,
                updated_ms=? WHERE id=? AND
                state NOT IN ('finished','stopped','turn_limit_reached')""",
                (_now(), cycle_id))
        finally:
            con.close()
    return status(cycle_id)


def _prompt(row: sqlite3.Row, n: int, request_id: str,
            previous_summary: str = "", previous_evidence: str = "") -> str:
    return (
        "ASTERION CONTINUOUS PROJECT DEVELOPMENT TURN\n"
        f"Cycle: {row['id']}\nRequest ID: {request_id}\n"
        f"Project: {row['project']}\nSpecification: {row['spec_ref']}\n"
        f"Verified turns already completed: {row['verified_turns']}\n"
        f"Original objective: {row['objective']}\n"
        f"Latest verified work: {previous_summary or 'none'}\n"
        f"Latest verified evidence SHA-256: {previous_evidence or 'none'}\n"
        f"Next substantial project work: {row['next_work']}\n"
        "This is an overnight DEVELOPMENT turn, not a normal UI action.\n"
        "Inspect exact source and previous checkpoints; perform real approved "
        "implementation, diagnosis and verification using actual tools. "
        "Do not claim success from a generated answer, command ACK or duration. "
        "Provide source/test/device evidence. Never imply an APK was built or "
        "installed unless independently verified. If blocked, report the blocker "
        "and preserve exact next-work instructions. Do not duplicate uncertain "
        "external submissions."
    )


def claim(cycle_id: str) -> dict:
    """Durably reserve ONE turn before any provider/tool call.

    An uncertain caller crash after claiming prevents automatic re-submission.
    """
    _require_id(cycle_id)
    with _LOCK:
        con = _db()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM cycles WHERE id=?",
                              (cycle_id,)).fetchone()
            if row is None:
                raise KeyError(cycle_id)
            if row["state"] != "ready":
                raise RuntimeError("cycle_not_ready_" + row["state"])
            number = row["turn_index"] + 1
            if row["max_turns"] and number > row["max_turns"]:
                raise RuntimeError("cycle_turn_limit_reached")
            ident = f"{cycle_id}-turn-{number}"
            previous = con.execute("""SELECT work_summary,evidence_sha256 FROM turns
                WHERE cycle_id=? AND state='verified'
                ORDER BY turn_index DESC LIMIT 1""", (cycle_id,)).fetchone()
            prompt = _prompt(row, number, ident,
                             previous['work_summary'] if previous else '',
                             previous['evidence_sha256'] if previous else '')
            now = _now()
            con.execute("""INSERT INTO turns
                (request_id,cycle_id,turn_index,state,prompt_sha256,started_ms,updated_ms)
                VALUES(?,?,?,'dispatch_uncertain',?,?,?)""",
                (ident, cycle_id, number, _digest(prompt), now, now))
            con.execute("""UPDATE cycles SET state='dispatch_uncertain',
                turn_index=?,updated_ms=?,last_error_code=''
                WHERE id=? AND state='ready'""", (number, now, cycle_id))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
    return {"cycle_id":cycle_id, "turn_index":number, "request_id":ident,
            "provider":row["provider"], "prompt":prompt,
            "prompt_sha256":_digest(prompt), "replay_allowed":False,
            "state":"dispatch_uncertain"}


def response(cycle_id: str, request_id: str, *, provider_receipt: str,
             content: str) -> dict:
    """Record an actual provider's uniquely identified response, not its content."""
    _require_id(cycle_id)
    if not isinstance(request_id,str) or len(request_id) > 100:
        raise ValueError("invalid_request_id")
    if not isinstance(provider_receipt,str) or not 8 <= len(provider_receipt) <= 200:
        raise ValueError("invalid_provider_receipt")
    if not isinstance(content,str) or not 1 <= len(content) <= 500000:
        raise ValueError("invalid_provider_response")
    sha = _digest(content)
    with _LOCK:
        con = _db()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur=con.execute("""UPDATE turns SET state='awaiting_verification',
                 provider_receipt=?,response_sha256=?,updated_ms=?
                 WHERE cycle_id=? AND request_id=? AND state='dispatch_uncertain'""",
                 (provider_receipt, sha, _now(), cycle_id, request_id))
            if cur.rowcount != 1:
                raise RuntimeError("no_matching_uncertain_turn")
            con.execute("""UPDATE cycles SET state='awaiting_verification',
                 updated_ms=? WHERE id=? AND state='dispatch_uncertain'""",
                 (_now(), cycle_id))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
    return {"cycle_id":cycle_id, "request_id":request_id,
            "state":"awaiting_verification", "response_sha256":sha,
            "project_work_verified":False, "replay_allowed":False}


def review(cycle_id: str, *, error_code: str = "UncertainExternalOperation") -> dict:
    _require_id(cycle_id)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}",error_code):
        raise ValueError("invalid_error_code")
    with _LOCK:
        con=_db()
        try:
            con.execute("""UPDATE cycles SET state='needs_review',
                updated_ms=?,last_error_code=?
                WHERE id=? AND state IN ('dispatch_uncertain','awaiting_verification')""",
                (_now(), error_code, cycle_id))
        finally:
            con.close()
    return status(cycle_id)


def verify(cycle_id: str, request_id: str, *,
           evidence_sha256: str, work_summary: str,
           next_work: str, done: bool = False,
           acceptance_verified: bool = False) -> dict:
    """Trusted work verifier confirms actual project progress.

    This cannot validate evidence itself. Only an authorized executor should
    call it after checking real tests/artifacts; its hash is a provenance token,
    not an automatic claim that external work succeeded.
    """
    _require_id(cycle_id)
    if not isinstance(request_id,str) or not request_id.startswith(cycle_id+"-turn-"):
        raise ValueError("invalid_request_id")
    if not isinstance(evidence_sha256,str) or not _HASH.fullmatch(evidence_sha256):
        raise ValueError("actual_work_evidence_required")
    if not isinstance(work_summary,str) or not 10 <= len(work_summary) <= 1000:
        raise ValueError("work_summary_required")
    if not isinstance(next_work,str) or not 3 <= len(next_work) <= 3000:
        raise ValueError("next_work_required")
    if done and not acceptance_verified:
        raise ValueError("completion_requires_independent_acceptance")
    now = _now()
    with _LOCK:
        con=_db()
        try:
            con.execute("BEGIN IMMEDIATE")
            row=con.execute("SELECT * FROM cycles WHERE id=?",
                            (cycle_id,)).fetchone()
            if row is None:raise KeyError(cycle_id)
            if row["state"] != "awaiting_verification":
                raise RuntimeError("cycle_not_waiting_for_verification")
            match=con.execute("""UPDATE turns SET state='verified',
                evidence_sha256=?,work_summary=?,next_work=?,
                acceptance_verified=?,updated_ms=?
                WHERE cycle_id=? AND request_id=? AND state='awaiting_verification'""",
                (evidence_sha256,work_summary,next_work,
                 int(acceptance_verified),now,cycle_id,request_id))
            if match.rowcount!=1:
                raise RuntimeError("no_matching_turn_to_verify")
            reached_limit=(row["max_turns"]>0 and
                           row["turn_index"] >= row["max_turns"])
            new_state=("stopped" if row["stop_requested"] else
                       "finished" if done else
                       "turn_limit_reached" if reached_limit else
                       "paused" if row["pause_requested"] else "ready")
            con.execute("""UPDATE cycles SET state=?,next_work=?,verified_turns=verified_turns+1,
                updated_ms=?,completion_evidence_sha256=?
                WHERE id=? AND state='awaiting_verification'""",
                (new_state,next_work,now,evidence_sha256 if done else "",cycle_id))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
    result = status(cycle_id)
    result["project_work_verified"] = True
    result["scope_completed"] = bool(done and not result["stop_requested"])
    result["turn_limit_reached"] = reached_limit and not done
    return result


def advance_once(cycle_id: str,
                 provider: Callable[[str,str],dict],
                 executor: Callable[[str,str,str],dict] | None = None) -> dict:
    """Run one owner-authorized development turn using injected real adapters.

    Provider(prompt,request_id) -> {message_id,content}. Executor(content,
    cycle_id,request_id) -> {evidence_sha256,work_summary,next_work,
    done?,acceptance_verified?}. Neither adapter is silently simulated here.
    No executor: the cycle correctly stops at awaiting_verification.
    """
    turn = claim(cycle_id)
    ident=turn["request_id"]
    try:
        output=provider(turn["prompt"],ident)
        if not isinstance(output,dict):
            raise TypeError("provider_did_not_return_receipt")
        provider_id=output["message_id"]
        body=output["content"]
        response(cycle_id,ident,provider_receipt=provider_id,content=body)
    except Exception as exc:
        return review(cycle_id,error_code=type(exc).__name__)
    if executor is None:
        return status(cycle_id)
    try:
        outcome=executor(body,cycle_id,ident)
        if not isinstance(outcome,dict):
            raise TypeError("executor_did_not_return_receipt")
        return verify(cycle_id,ident,**outcome)
    except Exception as exc:
        return review(cycle_id,error_code=type(exc).__name__)


def advance_until_blocked(cycle_id: str,
                          provider: Callable[[str,str],dict],
                          executor: Callable[[str,str,str],dict],
                          *, max_turns_per_call: int = 10) -> dict:
    """Run bounded actual provider/executor turns, never a fake time-based cycle."""
    if not isinstance(max_turns_per_call,int) or not 1<=max_turns_per_call<=10:
        raise ValueError("invalid_turn_batch_limit")
    current=status(cycle_id)
    for _ in range(max_turns_per_call):
        if current["state"]!="ready":
            break
        current=advance_once(cycle_id,provider,executor)
    return current
