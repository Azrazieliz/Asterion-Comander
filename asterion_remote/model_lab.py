"""Model Laboratory: local model inventory, public release watch and evidence-based advice.

No model download, model replacement, paid endpoint, training, or cloud inference.
A newer upstream SHA is a candidate for *evaluation*, never an automatic upgrade.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime,timezone
from pathlib import Path

import httpx

_LOCK=threading.RLock()
_REPO=re.compile(r"^[A-Za-z0-9_.-]{2,90}/[A-Za-z0-9_.-]{2,110}$")
_APP=re.compile(r"^[a-z][a-z0-9_.-]{2,79}$")
_MAX=100


def _db():
    root=Path(os.getenv("ASTERION_MODEL_LAB_ROOT",str(
        Path(os.getenv("LOCALAPPDATA",str(Path.home())))/
        "AsterionControl"/"model-laboratory")))
    root.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(root/"models.sqlite3"),timeout=5,isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS watched(
      app TEXT NOT NULL,repo TEXT NOT NULL,
      installed_sha TEXT NOT NULL DEFAULT '',
      upstream_sha TEXT NOT NULL DEFAULT '',
      upstream_updated TEXT NOT NULL DEFAULT '',
      license TEXT NOT NULL DEFAULT 'unknown',
      size_bytes INTEGER,
      gated INTEGER NOT NULL DEFAULT 0,
      checked_at_ms INTEGER NOT NULL DEFAULT 0,
      error_code TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(app,repo));
    CREATE TABLE IF NOT EXISTS benchmarks(
      app TEXT NOT NULL,repo TEXT NOT NULL,sha TEXT NOT NULL,
      task_score REAL NOT NULL,latency_ms REAL NOT NULL,
      ram_mb REAL NOT NULL,thermal_ok INTEGER NOT NULL,
      verified INTEGER NOT NULL, evidence_sha256 TEXT NOT NULL,
      recorded_at_ms INTEGER NOT NULL,
      PRIMARY KEY(app,repo,sha));
    """)
    db.row_factory=sqlite3.Row
    return db


def _valid(app: str,repo:str):
    if not _APP.fullmatch(app) or not _REPO.fullmatch(repo):
        raise ValueError("invalid_app_or_model_repository")


def watch(app:str,repo:str,installed_sha:str="")->dict:
    _valid(app,repo)
    if installed_sha and not re.fullmatch("[0-9a-f]{7,64}",installed_sha):
        raise ValueError("invalid_installed_sha")
    with _LOCK:
        db=_db()
        try:
            db.execute("""INSERT INTO watched(app,repo,installed_sha)
                VALUES(?,?,?) ON CONFLICT(app,repo) DO UPDATE SET
                installed_sha=excluded.installed_sha""",(app,repo,installed_sha))
        finally:db.close()
    return {"ok":True,"app":app,"repo":repo,"installed_sha":installed_sha,
            "auto_replacement":False}


def unwatch(app:str,repo:str)->dict:
    _valid(app,repo)
    with _LOCK:
        db=_db()
        try:db.execute("DELETE FROM watched WHERE app=? AND repo=?",(app,repo))
        finally:db.close()
    return {"ok":True,"app":app,"repo":repo,"removed":True}


def list_models(app:str="")->dict:
    if app and not _APP.fullmatch(app):raise ValueError("invalid_app")
    with _LOCK:
        db=_db()
        try:
            rows=db.execute("SELECT * FROM watched"+(" WHERE app=?" if app else "")+
                " ORDER BY app,repo LIMIT ?",((app,_MAX) if app else (_MAX,))).fetchall()
            data=[dict(row) for row in rows]
        finally:db.close()
    for item in data:
        item["update_candidate"]=(bool(item["installed_sha"]) and
           bool(item["upstream_sha"]) and item["installed_sha"]!=item["upstream_sha"])
        item["auto_replacement"]=False
    return {"ok":True,"items":data,"count":len(data)}


def _summary(data:dict)->dict:
    # Explicit allowlist from the public model-hub metadata, no raw README/code.
    ident=data.get("id","")
    sha=data.get("sha","")
    if not isinstance(ident,str) or not _REPO.fullmatch(ident):
        raise ValueError("unexpected_remote_model_identity")
    if not isinstance(sha,str) or not re.fullmatch("[0-9a-f]{40,64}",sha):
        raise ValueError("missing_remote_revision")
    card=data.get("cardData") if isinstance(data.get("cardData"),dict) else {}
    license_=card.get("license","unknown")
    if not isinstance(license_,str) or not re.fullmatch(r"[A-Za-z0-9_.+-]{1,60}",license_):
        license_="unknown"
    return {"repo":ident,"upstream_sha":sha,
        "upstream_updated":str(data.get("lastModified",""))[:40],
        "license":license_,
        "gated":bool(data.get("gated",False)),
        "size_bytes":(data.get("safetensors") or {}).get("total")
            if isinstance(data.get("safetensors"),dict) else None}


def refresh(app:str,repo:str,*, client:httpx.Client|None=None)->dict:
    """Check one free public Hugging Face metadata endpoint. No downloads."""
    _valid(app,repo)
    owned=client is None
    api=client if client is not None else httpx.Client(
        timeout=httpx.Timeout(8,connect=3),trust_env=False,follow_redirects=False)
    try:
        response=api.get("https://huggingface.co/api/models/"+repo)
        response.raise_for_status()
        if len(response.content)>1_000_000:raise ValueError("oversized_metadata")
        summary=_summary(response.json())
        if summary["repo"]!=repo:raise ValueError("unexpected_remote_model_identity")
    except (httpx.HTTPError,ValueError,TypeError,KeyError) as exc:
        code=type(exc).__name__
        with _LOCK:
            db=_db()
            try:db.execute("""UPDATE watched SET checked_at_ms=?,error_code=?
                WHERE app=? AND repo=?""",(time.time_ns()//1000000,code,app,repo))
            finally:db.close()
        return {"ok":False,"app":app,"repo":repo,"error_code":code,
                "update_candidate":False}
    finally:
        if owned:api.close()
    with _LOCK:
        db=_db()
        try:
            cur=db.execute("""UPDATE watched SET upstream_sha=?,upstream_updated=?,
                license=?,size_bytes=?,gated=?,checked_at_ms=?,error_code=''
                WHERE app=? AND repo=?""",(
                summary["upstream_sha"],summary["upstream_updated"],
                summary["license"],summary["size_bytes"],
                int(summary["gated"]),time.time_ns()//1000000,app,repo))
            if cur.rowcount!=1:raise ValueError("repository_not_watched")
            item=dict(db.execute("SELECT * FROM watched WHERE app=? AND repo=?",
                (app,repo)).fetchone())
        finally:db.close()
    item["update_candidate"]=bool(item["installed_sha"]) and (
        item["installed_sha"]!=item["upstream_sha"])
    item["auto_replacement"]=False
    item["recommendation"]="evaluate" if item["update_candidate"] else "none"
    return {"ok":True,**item}


def benchmark(app:str,repo:str,sha:str,task_score:float,latency_ms:float,
              ram_mb:float,thermal_ok:bool,verified:bool,evidence_sha256:str)->dict:
    _valid(app,repo)
    if not re.fullmatch(r"[0-9a-f]{7,64}",sha) or not re.fullmatch(
        r"[0-9a-f]{64}",evidence_sha256):
        raise ValueError("benchmark_evidence_required")
    if not (0<=task_score<=1 and 0<latency_ms<1e7 and 0<ram_mb<1e7):
        raise ValueError("invalid_benchmark_metrics")
    with _LOCK:
        db=_db()
        try:db.execute("""INSERT INTO benchmarks VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(app,repo,sha) DO UPDATE SET task_score=excluded.task_score,
          latency_ms=excluded.latency_ms,ram_mb=excluded.ram_mb,
          thermal_ok=excluded.thermal_ok,verified=excluded.verified,
          evidence_sha256=excluded.evidence_sha256,
          recorded_at_ms=excluded.recorded_at_ms""",(
          app,repo,sha,task_score,latency_ms,ram_mb,int(thermal_ok),
          int(verified),evidence_sha256,time.time_ns()//1000000))
        finally:db.close()
    return {"ok":True,"app":app,"repo":repo,"sha":sha,
            "verified":verified,"model_replaced":False}


def recommendations(app:str)->dict:
    if not _APP.fullmatch(app):raise ValueError("invalid_app")
    with _LOCK:
        db=_db()
        try:
            watched=[dict(x) for x in db.execute("SELECT * FROM watched WHERE app=?",(app,))]
            benchmarks=[dict(x) for x in db.execute(
                "SELECT * FROM benchmarks WHERE app=?",(app,))]
        finally:db.close()
    by_key={(x["repo"],x["sha"]):x for x in benchmarks}
    findings=[]
    for row in watched:
        if not row["installed_sha"] or not row["upstream_sha"]:
            continue
        if row["installed_sha"]==row["upstream_sha"]:continue
        base=by_key.get((row["repo"],row["installed_sha"]))
        new=by_key.get((row["repo"],row["upstream_sha"]))
        if not base or not new or not (base["verified"] and new["verified"]):
            verdict="benchmark_required"
        elif not new["thermal_ok"] or new["ram_mb"]>base["ram_mb"]*1.25:
            verdict="reject_resource_regression"
        elif new["task_score"]>base["task_score"] and new["latency_ms"]<=base["latency_ms"]*1.25:
            verdict="owner_review_recommended"
        else:
            verdict="no_measured_improvement"
        findings.append({"repo":row["repo"],"candidate_sha":row["upstream_sha"],
            "installed_sha":row["installed_sha"],"verdict":verdict,
            "automatic_update":False,
            "needs_owner_approval":verdict=="owner_review_recommended"})
    return {"ok":True,"app":app,"items":findings}
