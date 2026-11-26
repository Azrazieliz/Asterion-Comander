"""Dependency-aware persistent tasks for the existing Control overnight supervisor.

Shares the supervisor's SQLite database, not a new scheduler. A task cannot
silently become accepted: source_tested is distinct from device_verified.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from . import overnight_supervisor

_ID = re.compile(r"^[a-z][a-z0-9_-]{3,79}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _database():
    db = overnight_supervisor._db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS dev_backlog(
          task_id TEXT PRIMARY KEY,
          cycle_id TEXT NOT NULL,
          priority INTEGER NOT NULL,
          component TEXT NOT NULL,
          goal TEXT NOT NULL,
          target_path TEXT NOT NULL,
          dependencies TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending',
          attempt INTEGER NOT NULL DEFAULT 0,
          evidence_sha256 TEXT NOT NULL DEFAULT '',
          candidate_commit TEXT NOT NULL DEFAULT '',
          verification_level TEXT NOT NULL DEFAULT '',
          last_error TEXT NOT NULL DEFAULT '',
          updated_ms INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS dev_backlog_cycle
            ON dev_backlog(cycle_id,priority,task_id);
    """)
    db.row_factory = sqlite3.Row
    return db


def _check_id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid_development_task_id")


def seed(cycle_id, tasks):
    """Idempotent initial import; never resets previously claimed/completed work."""
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("nonempty_task_list_required")
    ids = set()
    for item in tasks:
        _check_id(item["id"])
        if item["id"] in ids:
            raise ValueError("duplicate_task_in_manifest")
        ids.add(item["id"])
        if not isinstance(item.get("priority"), int) or not 0 <= item["priority"] <= 9:
            raise ValueError("invalid_priority")
        if not isinstance(item.get("goal"), str) or not 12 <= len(item["goal"]) <= 2000:
            raise ValueError("invalid_goal")
        if not isinstance(item.get("component"), str) or not 2 <= len(item["component"]) <= 80:
            raise ValueError("invalid_component")
        path = item.get("target_path")
        if (not isinstance(path, str) or len(path)>240 or
                not (path.startswith("asterion_remote/") or path.startswith("android/") or
                     path.startswith("scripts/") or path.startswith("tests/")) or
                "\\" in path or ".." in path.split("/") or path.startswith("/")):
            raise ValueError("target_not_in_isolated_source_allowlist")
        deps=item.get("depends_on", [])
        if not isinstance(deps,list) or len(set(deps))!=len(deps):
            raise ValueError("invalid_task_dependencies")
        for dependency in deps:
            _check_id(dependency)
            if dependency==item["id"]:
                raise ValueError("self_dependency")
        if item.get("verification_level") not in (None,"source_tested","device_verified"):
            raise ValueError("invalid_requested_verification")
    db=_database()
    try:
        with db:
            if not db.execute("SELECT id FROM cycles WHERE id=?", (cycle_id,)).fetchone():
                raise ValueError("cycle_not_initialized")
            stamp=time.time_ns()//1_000_000
            for item in tasks:
                deps=item.get("depends_on",[])
                db.execute("""INSERT OR IGNORE INTO dev_backlog
                  (task_id,cycle_id,priority,component,goal,target_path,
                   dependencies,updated_ms) VALUES(?,?,?,?,?,?,?,?)""",
                   (item["id"],cycle_id,item["priority"],item["component"],
                    item["goal"],item["target_path"],json.dumps(deps),stamp))
            for item in tasks:
                current=db.execute("SELECT cycle_id,goal,target_path,dependencies FROM dev_backlog WHERE task_id=?",
                                   (item["id"],)).fetchone()
                if (current["cycle_id"]!=cycle_id or current["goal"]!=item["goal"] or
                        current["target_path"]!=item["target_path"] or
                        json.loads(current["dependencies"])!=item.get("depends_on",[])):
                    raise ValueError("attempted_change_to_existing_task")
    finally:
        db.close()
    return snapshot(cycle_id)


def snapshot(cycle_id):
    db=_database()
    try:
        rows=[dict(r) for r in db.execute(
            "SELECT * FROM dev_backlog WHERE cycle_id=? ORDER BY priority,task_id",
            (cycle_id,))]
    finally:
        db.close()
    for row in rows:
        row["dependencies"]=json.loads(row["dependencies"])
    return rows


def claim(cycle_id):
    """Choose lowest priority number with all dependencies source-verified.

    Transactional reservation prevents double execution. A crashed claim stays
    claimed for explicit reconciliation; never silently repeat an uncertain edit.
    """
    db=_database()
    try:
        db.execute("BEGIN IMMEDIATE")
        rows=[dict(r) for r in db.execute(
            "SELECT * FROM dev_backlog WHERE cycle_id=? ORDER BY priority,task_id",
            (cycle_id,))]
        done={r["task_id"] for r in rows if r["state"] in
              ("source_tested","device_verified")}
        chosen=next((r for r in rows if r["state"]=="pending"
                     and set(json.loads(r["dependencies"])) <= done),None)
        if chosen is None:
            db.execute("COMMIT")
            return None
        db.execute("""UPDATE dev_backlog SET state='claimed',attempt=attempt+1,
            updated_ms=? WHERE task_id=? AND state='pending'""",
            (time.time_ns()//1_000_000,chosen["task_id"]))
        db.execute("COMMIT")
        chosen["state"]="claimed"
        chosen["attempt"]+=1
        chosen["dependencies"]=json.loads(chosen["dependencies"])
        return chosen
    except BaseException:
        db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def record(task_id, *, evidence_sha256, candidate_commit, verification_level):
    _check_id(task_id)
    if not _HASH.fullmatch(evidence_sha256) or not _COMMIT.fullmatch(candidate_commit):
        raise ValueError("invalid_independent_source_receipt")
    if verification_level != "source_tested":
        raise ValueError("device_acceptance_requires_separate_verifier")
    db=_database()
    try:
        with db:
            changed=db.execute("""UPDATE dev_backlog SET state='source_tested',
                verification_level=?,evidence_sha256=?,candidate_commit=?,
                updated_ms=?,last_error=''
                WHERE task_id=? AND state='claimed'""",
                (verification_level,evidence_sha256,candidate_commit,
                 time.time_ns()//1_000_000,task_id))
            if changed.rowcount!=1:
                raise RuntimeError("task_not_claimed")
    finally:
        db.close()
    return True


def block(task_id, reason):
    _check_id(task_id)
    if not isinstance(reason,str) or not 3 <= len(reason) <= 150:
        raise ValueError("invalid_block_reason")
    db=_database()
    try:
        with db:
            db.execute("""UPDATE dev_backlog SET state='needs_review',
                last_error=?,updated_ms=? WHERE task_id=? AND state='claimed'""",
                (reason,time.time_ns()//1_000_000,task_id))
    finally:
        db.close()
