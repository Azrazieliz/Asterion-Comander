"""Zero-cost release monitor for the EXISTING Asterion Model Laboratory.

Reuses model_lab.watch/refresh/benchmark/recommendations. Never replaces,
downloads or loads models automatically. Stores durable one-time review
requests when a newer release is relevant to owner-installed model inventory.

The scheduled watcher is opt-in; all external calls are limited to public HF
metadata. Only independently verified model/latency/memory benchmarks can
trigger a recommendation to replace an installed model, never an automatic
installation.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from pathlib import Path

import httpx
from . import model_lab

_LOCK=threading.RLock()
_STOP=threading.Event()
_THREAD:threading.Thread|None=None


def _db():
    base=Path(os.getenv("ASTERION_MODEL_WATCH_ROOT",str(
        Path(os.getenv("LOCALAPPDATA",str(Path.home())))/
        "AsterionControl"/"model-watch"))).expanduser().resolve()
    base.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(base/"events.sqlite3"),timeout=8,isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS events(
        id TEXT PRIMARY KEY,app TEXT NOT NULL,repo TEXT NOT NULL,
        upstream_sha TEXT NOT NULL,verdict TEXT NOT NULL,
        created_ms INTEGER NOT NULL,acknowledged INTEGER NOT NULL DEFAULT 0
    )""")
    db.row_factory=sqlite3.Row
    return db


def events(limit:int=30)->dict:
    if not isinstance(limit,int) or not 1<=limit<=100:
        raise ValueError("invalid_event_limit")
    with _LOCK:
        db=_db()
        try:
            rows=[dict(row) for row in db.execute(
                """SELECT * FROM events ORDER BY created_ms DESC LIMIT ?""",
                (limit,))]
        finally:db.close()
    return {"ok":True,"items":rows,
            "automatic_model_replacements":0,
            "needs_owner_intervention":any(not x["acknowledged"] for x in rows)}


def acknowledge(ident:str)->dict:
    if not isinstance(ident,str) or len(ident)!=64 or any(
            c not in "0123456789abcdef" for c in ident):
        raise ValueError("invalid_model_event_id")
    with _LOCK:
        db=_db()
        try:
            updated=db.execute("UPDATE events SET acknowledged=1 WHERE id=?",
                               (ident,))
            if updated.rowcount!=1:
                raise KeyError(ident)
        finally:db.close()
    return {"ok":True,"acknowledged":True,"event_id":ident,
            "model_replaced":False}


def scan_once(client:httpx.Client|None=None, *,
              limit:int=20)->dict:
    """Perform REAL metadata checks for watched models, never weights fetch.

    Client injection is used for deterministic no-network integration tests.
    Public Hugging Face requests are bounded and occur only when invoked.
    """
    if not isinstance(limit,int) or not 1<=limit<=100:
        raise ValueError("invalid_model_watch_scan_limit")
    watched=model_lab.list_models()["items"][:limit]
    managed=client is None
    api=client if client is not None else httpx.Client(
        timeout=httpx.Timeout(8,connect=3),trust_env=False,
        follow_redirects=False)
    refreshed=[]
    emitted=0
    try:
        for item in watched:
            outcome=model_lab.refresh(item["app"],item["repo"],client=api)
            refreshed.append({
                "app":item["app"],"repo":item["repo"],
                "ok":outcome.get("ok",False),
                "update_candidate":outcome.get("update_candidate",False),
                "error_code":outcome.get("error_code","")
            })
            if not outcome.get("update_candidate"):
                continue
            score=model_lab.recommendations(item["app"])
            for result in score.get("items",[]):
                if result["repo"]!=item["repo"]:
                    continue
                verdict=result["verdict"]
                if verdict not in {
                    "benchmark_required","owner_review_recommended",
                    "reject_resource_regression","no_measured_improvement"
                }:
                    continue
                key="\0".join((
                    item["app"],item["repo"],
                    outcome["upstream_sha"],verdict))
                ident=hashlib.sha256(key.encode()).hexdigest()
                with _LOCK:
                    db=_db()
                    try:
                        added=db.execute("""INSERT OR IGNORE INTO events
                            (id,app,repo,upstream_sha,verdict,created_ms)
                            VALUES(?,?,?,?,?,?)""",
                            (ident,item["app"],item["repo"],
                             outcome["upstream_sha"],verdict,
                             time.time_ns()//1_000_000))
                        if added.rowcount==1:emitted+=1
                    finally:db.close()
    finally:
        if managed:api.close()
    return {"ok":True,"scanned":len(refreshed),
            "new_review_events":emitted,"results":refreshed,
            "models_replaced":0,"paid_api_used":False}


def _loop()->None:
    # The first scan is delayed. Don't start a surprise network operation at
    # Windows worker launch. Only the owner enables periodic public metadata.
    while not _STOP.wait(timeout=60):
        if _STOP.is_set():return
        try:scan_once(limit=30)
        except Exception:pass
        try:
            hours=int(os.getenv("ASTERION_MODEL_WATCH_HOURS","24"))
        except ValueError:hours=24
        _STOP.wait(timeout=max(4,min(168,hours))*3600)


def start()->dict:
    global _THREAD
    if os.getenv("ASTERION_MODEL_WATCH_ENABLED","0")!="1":
        return {"enabled":False,"worker_running":False}
    with _LOCK:
        if _THREAD is None or not _THREAD.is_alive():
            _STOP.clear()
            _THREAD=threading.Thread(
                target=_loop,name="asterion-model-release-watch",
                daemon=True)
            _THREAD.start()
        return {"enabled":True,"worker_running":True,
                "requires_paid_service":False,
                "automatic_model_replacement":False}


def stop()->None:
    global _THREAD
    _STOP.set()
    worker=_THREAD
    if worker:worker.join(timeout=3)
    if worker is None or not worker.is_alive():
        _THREAD=None


def status()->dict:
    return {"enabled":os.getenv("ASTERION_MODEL_WATCH_ENABLED","0")=="1",
            "worker_running":bool(_THREAD and _THREAD.is_alive()),
            "automatic_model_replacement":False,
            "requires_paid_service":False}
