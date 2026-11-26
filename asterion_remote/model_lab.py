"""Model Laboratory: local model inventory, public release watch and evidence-based advice.

No model download, model replacement, paid endpoint, training, or cloud inference.
A newer upstream SHA is a candidate for *evaluation*, never an automatic upgrade.
"""
from __future__ import annotations

import json
import math
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
        try:db.execute("""INSERT INTO benchmarks(app,repo,sha,task_score,latency_ms,ram_mb,thermal_ok,verified,evidence_sha256,recorded_at_ms) VALUES(?,?,?,?,?,?,?,?,?,?)
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


# Owner-tailored Control AI: experimental candidates live in this existing
# Model Laboratory database, not a second registry or automatic model picker.
_CANDIDATE_ID=re.compile(r"^[a-z][a-z0-9_.-]{3,95}$")
_DIGEST=re.compile(r"^[0-9a-f]{64}$")
_REVISION=re.compile(r"^[0-9a-f]{40,64}$")
_ARCHITECTURES={"dense","moe","hybrid","ssm","recurrent","unknown"}
_BACKENDS={"android_cpu","android_gpu","android_npu","windows_cpu","windows_gpu"}
_MAX_BYTES=2**47  # input bounds are for integer integrity, not model tier selection

def _candidate_db():
    db=_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS model_candidate_experiments (
      id TEXT PRIMARY KEY, app TEXT NOT NULL, repo TEXT NOT NULL,
      revision TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
      architecture TEXT NOT NULL, parameters_total_b REAL NOT NULL,
      parameters_active_b REAL, artifact_bytes INTEGER NOT NULL,
      license TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'staged',
      created_ms INTEGER NOT NULL, UNIQUE(app,repo,revision,artifact_sha256));
    CREATE TABLE IF NOT EXISTS model_adaptation_experiments(
      id TEXT PRIMARY KEY,base_candidate_id TEXT NOT NULL,
      adapter_sha256 TEXT NOT NULL,training_record_sha256 TEXT NOT NULL,
      evaluation_record_sha256 TEXT NOT NULL,weights_changed INTEGER NOT NULL,
      created_ms INTEGER NOT NULL,
      FOREIGN KEY(base_candidate_id) REFERENCES model_candidate_experiments(id));
    CREATE TABLE IF NOT EXISTS model_candidate_probes (
      candidate_id TEXT NOT NULL, device TEXT NOT NULL,
      backend TEXT NOT NULL, context_tokens INTEGER NOT NULL,
      weight_resident_bytes INTEGER NOT NULL,
      kv_cache_bytes INTEGER NOT NULL,
      scratch_bytes INTEGER NOT NULL,
      process_overhead_bytes INTEGER NOT NULL,
      system_headroom_bytes INTEGER NOT NULL,
      measured_free_bytes INTEGER NOT NULL,
      peak_pss_bytes INTEGER NOT NULL, prefill_tokens_s REAL NOT NULL,
      decode_tokens_s REAL NOT NULL, thermal_state INTEGER NOT NULL,
      elapsed_s REAL NOT NULL, evidence_sha256 TEXT NOT NULL,
      verified INTEGER NOT NULL DEFAULT 0,
      created_ms INTEGER NOT NULL,
      PRIMARY KEY(candidate_id,device,backend,context_tokens,evidence_sha256),
      FOREIGN KEY(candidate_id) REFERENCES model_candidate_experiments(id));
    """)
    db.execute("PRAGMA foreign_keys=ON")
    return db

def register_candidate(candidate_id:str,app:str,repo:str,revision:str,
                       artifact_sha256:str,architecture:str,
                       parameters_total_b:float,parameters_active_b:float|None,
                       artifact_bytes:int,license:str)->dict:
    """Register any parameter tier; no implication of phone compatibility."""
    _valid(app,repo)
    if (not _CANDIDATE_ID.fullmatch(candidate_id) or
        not _REVISION.fullmatch(revision) or
        not _DIGEST.fullmatch(artifact_sha256) or
        architecture not in _ARCHITECTURES or
        not isinstance(artifact_bytes,int) or
        not 1_000_000<=artifact_bytes<=_MAX_BYTES or
        not isinstance(parameters_total_b,(int,float)) or
        not math.isfinite(parameters_total_b) or parameters_total_b<=0 or
        parameters_total_b>10000 or
        (parameters_active_b is not None and
         (not isinstance(parameters_active_b,(int,float)) or
          not math.isfinite(parameters_active_b) or
          parameters_active_b<=0 or parameters_active_b>parameters_total_b)) or
        not isinstance(license,str) or
        not re.fullmatch(r"[A-Za-z0-9_.+-]{2,60}",license)):
        raise ValueError("invalid_candidate_provenance_or_structure")
    db=_candidate_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM model_candidate_experiments WHERE id=?",
                       (candidate_id,)).fetchone()
        proposed=(app,repo,revision,artifact_sha256,architecture,
                  float(parameters_total_b),float(parameters_active_b) if
                  parameters_active_b is not None else None,artifact_bytes,license)
        if row:
            actual=tuple(row[k] for k in ("app","repo","revision","artifact_sha256",
                    "architecture","parameters_total_b","parameters_active_b",
                    "artifact_bytes","license"))
            if actual!=proposed:
                raise ValueError("candidate_identity_cannot_be_rewritten")
        else:
            db.execute("""INSERT INTO model_candidate_experiments
                (id,app,repo,revision,artifact_sha256,architecture,
                 parameters_total_b,parameters_active_b,artifact_bytes,license,created_ms)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (candidate_id,*proposed,time.time_ns()//1_000_000))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    finally:
        db.close()
    return {"id":candidate_id,"registered":True,
            "performance_qualified":False,"approved_for_phone":False,
            "automatically_promoted":False}

def record_candidate_probe(candidate_id:str,device:str,backend:str,
                           context_tokens:int,*,weight_resident_bytes:int,
                           kv_cache_bytes:int,scratch_bytes:int,
                           process_overhead_bytes:int,system_headroom_bytes:int,
                           measured_free_bytes:int,peak_pss_bytes:int,
                           prefill_tokens_s:float,decode_tokens_s:float,
                           thermal_state:int,elapsed_s:float,
                           evidence_sha256:str,verified:bool)->dict:
    """Store externally sourced measurements; never infer certification from speed."""
    if (not _CANDIDATE_ID.fullmatch(candidate_id) or
        not isinstance(device,str) or
        not re.fullmatch(r"[A-Za-z0-9_.-]{3,90}",device) or
        backend not in _BACKENDS or
        not type(context_tokens) is int or not 256<=context_tokens<=2**22 or
        not _DIGEST.fullmatch(evidence_sha256) or type(verified) is not bool or
        type(thermal_state) is not int or not 0<=thermal_state<=9):
        raise ValueError("invalid_candidate_probe_identity")
    sizes=(weight_resident_bytes,kv_cache_bytes,scratch_bytes,
           process_overhead_bytes,system_headroom_bytes,measured_free_bytes,peak_pss_bytes)
    if any(type(n) is not int or n<0 or n>_MAX_BYTES for n in sizes) or weight_resident_bytes==0:
        raise ValueError("invalid_resource_ledger")
    rates=(prefill_tokens_s,decode_tokens_s,elapsed_s)
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in rates) or elapsed_s==0:
        raise ValueError("invalid_measured_latency")
    admission=sum(sizes[:5])
    # This is a measurement-based conservative admission heuristic, NOT proof
    # of Android memory availability. PSS and measured free have different roles.
    would_fit=admission<=measured_free_bytes
    db=_candidate_db()
    try:
        with db:
            if not db.execute("SELECT id FROM model_candidate_experiments WHERE id=?",
                              (candidate_id,)).fetchone():
                raise ValueError("candidate_not_registered")
            db.execute("""INSERT OR IGNORE INTO model_candidate_probes
                (candidate_id,device,backend,context_tokens,
                 weight_resident_bytes,kv_cache_bytes,scratch_bytes,process_overhead_bytes,
                 system_headroom_bytes,measured_free_bytes,peak_pss_bytes,
                 prefill_tokens_s,decode_tokens_s,thermal_state,elapsed_s,
                 evidence_sha256,verified,created_ms)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (candidate_id,device,backend,context_tokens,*sizes,
                 float(prefill_tokens_s),float(decode_tokens_s),thermal_state,
                 float(elapsed_s),evidence_sha256,int(verified),time.time_ns()//1_000_000))
    finally: db.close()
    return {"candidate_id":candidate_id,"admission_ledger_bytes":admission,
            "headroom_observed_bytes":measured_free_bytes,
            "admission_estimate_fits":would_fit,
            "receipt_verified":verified,
            "reasoning_quality_verified":False,
            "owner_workflow_certified":False,"promoted":False}

def candidate_matrix(app:str="")->dict:
    if app and not _APP.fullmatch(app):raise ValueError("invalid_app")
    db=_candidate_db()
    try:
        rows=[dict(r) for r in db.execute(
            "SELECT * FROM model_candidate_experiments"+
            (" WHERE app=?" if app else "")+
            " ORDER BY created_ms,id LIMIT 500",(app,) if app else ())]
        for row in rows:
            row["probes"]=[dict(r) for r in db.execute(
                "SELECT * FROM model_candidate_probes WHERE candidate_id=? "
                "ORDER BY created_ms DESC LIMIT 40",(row["id"],))]
            row["adaptations"]=[dict(r) for r in db.execute(
                "SELECT * FROM model_adaptation_experiments WHERE base_candidate_id=? ORDER BY created_ms,id",
                (row["id"],))]
            row["phone_qualified"]=False
            row["reasoning_quality_certified"]=False
            row["no_automatic_model_selection"]=True
    finally:db.close()
    return {"candidates":rows,"count":len(rows),"phone_certification_open":True}


def register_adaptation(adaptation_id:str,base_candidate_id:str,*,
                        adapter_sha256:str,training_record_sha256:str,
                        evaluation_record_sha256:str,weights_changed:bool)->dict:
    """Link an adapter experiment to a real full-weight candidate in the SAME lab.

    Adapter bytes are never misrepresented as total model residency. Evidence
    is immutable and says nothing about promotion or owner-workflow quality.
    """
    if (not _CANDIDATE_ID.fullmatch(adaptation_id) or
        not _CANDIDATE_ID.fullmatch(base_candidate_id) or
        any(not isinstance(x,str) or not _DIGEST.fullmatch(x) for x in (
            adapter_sha256,training_record_sha256,evaluation_record_sha256)) or
        type(weights_changed) is not bool):
        raise ValueError('invalid_adaptation_lineage')
    db=_candidate_db()
    try:
        db.execute('''CREATE TABLE IF NOT EXISTS model_adaptation_experiments(
            id TEXT PRIMARY KEY,base_candidate_id TEXT NOT NULL,
            adapter_sha256 TEXT NOT NULL,training_record_sha256 TEXT NOT NULL,
            evaluation_record_sha256 TEXT NOT NULL,weights_changed INTEGER NOT NULL,
            created_ms INTEGER NOT NULL,
            FOREIGN KEY(base_candidate_id) REFERENCES model_candidate_experiments(id))''')
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT id FROM model_candidate_experiments WHERE id=?',
                          (base_candidate_id,)).fetchone():raise ValueError('base_candidate_not_registered')
        proposed=(base_candidate_id,adapter_sha256,training_record_sha256,
                  evaluation_record_sha256,int(weights_changed))
        existing=db.execute('SELECT * FROM model_adaptation_experiments WHERE id=?',(adaptation_id,)).fetchone()
        if existing:
            if tuple(existing[k] for k in ('base_candidate_id','adapter_sha256',
                'training_record_sha256','evaluation_record_sha256','weights_changed'))!=proposed:
                raise ValueError('adaptation_identity_cannot_be_rewritten')
        else:db.execute('INSERT INTO model_adaptation_experiments VALUES(?,?,?,?,?,?,?)',
                        (adaptation_id,*proposed,time.time_ns()//1_000_000))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK');raise
    finally:db.close()
    return {'id':adaptation_id,'base_candidate_id':base_candidate_id,
            'adapter_sha256':adapter_sha256,'training_record_sha256':training_record_sha256,
            'evaluation_record_sha256':evaluation_record_sha256,'weights_changed_recorded':weights_changed,
            'owner_behavior_certified':False,'phone_qualified':False,'automatically_promoted':False}
