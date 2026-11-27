"""Real, resumable offline-first evaluation of Asterion open-weight models.

Streams owner-provided locked HOLDOUT/STRESS JSONL cases to a genuine local
model provider. Does not generate fake successful cases, train on held-out
answers, install models, execute code from test data, or use paid APIs.

Supports millions of scenario records on disk with capped per-call batches;
only actual model responses and deterministic/external judgments are scored.
Results are SHA-bound to the immutable input dataset and model revision.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

_LOCK=threading.RLock()
_CASE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{3,99}$")
_MODEL=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,120}$")
_SHA=re.compile(r"^[0-9a-f]{64}$")
_MODES={"exact","contains","numeric","json_subset","external"}
_SPLITS={"holdout","stress"}
_MAX_FILE=1024*1024*1024
_MAX_LINE=24000


def _root()->Path:
    base=Path(os.getenv("ASTERION_MODEL_EVAL_ROOT",str(
        Path(os.getenv("LOCALAPPDATA",str(Path.home())))/
        "AsterionControl"/"model-evaluation"))).expanduser().resolve()
    base.mkdir(parents=True,exist_ok=True)
    return base


def _db()->sqlite3.Connection:
    path=_root()/"evaluation.sqlite3"
    db=sqlite3.connect(str(path),timeout=10,isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS evaluations(
      suite_sha256 TEXT NOT NULL,
      model_revision TEXT NOT NULL,
      case_id TEXT NOT NULL,
      category TEXT NOT NULL,
      split TEXT NOT NULL,
      mode TEXT NOT NULL,
      verdict TEXT NOT NULL,
      response_sha256 TEXT NOT NULL,
      evidence_sha256 TEXT NOT NULL,
      latency_ms REAL NOT NULL,
      scored_at_ms INTEGER NOT NULL,
      PRIMARY KEY(suite_sha256,model_revision,case_id))""")
    return db


def _dataset_path(file:str|Path)->Path:
    base=_root()
    path=Path(file).expanduser().resolve(strict=True)
    if not path.is_relative_to(base) or not path.is_file() or path.suffix!=".jsonl":
        raise ValueError("evaluation_dataset_must_be_in_owner_approved_root")
    if path.stat().st_size>_MAX_FILE:
        raise ValueError("evaluation_dataset_too_large")
    return path


def _read_cases(path:Path):
    seen=set()
    with path.open("r",encoding="utf-8") as source:
        for index,line in enumerate(source,1):
            if len(line)>_MAX_LINE:
                raise ValueError(f"evaluation_case_too_large_at_{index}")
            if not line.strip():
                continue
            try:
                case=json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid_jsonl_at_{index}") from exc
            if not isinstance(case,dict):
                raise ValueError(f"invalid_case_at_{index}")
            ident=case.get("id")
            if not isinstance(ident,str) or not _CASE.fullmatch(ident):
                raise ValueError(f"invalid_case_id_at_{index}")
            if ident in seen:
                raise ValueError("duplicate_case_id")
            seen.add(ident)
            split=case.get("split")
            category=case.get("category")
            mode=case.get("mode")
            prompt=case.get("prompt")
            if split not in _SPLITS or mode not in _MODES:
                raise ValueError("invalid_evaluation_split_or_mode")
            if not isinstance(category,str) or not _CASE.fullmatch(category):
                raise ValueError("invalid_evaluation_category")
            if not isinstance(prompt,str) or not 5<=len(prompt)<=12000:
                raise ValueError("invalid_case_prompt")
            if "expected" not in case:
                raise ValueError("case_requires_expected_answer")
            expected=case["expected"]
            if mode in {"exact","contains","numeric"}:
                if not isinstance(expected,str) or len(expected)>4000:
                    raise ValueError("invalid_expected_text")
            elif mode=="json_subset" and not isinstance(expected,dict):
                raise ValueError("expected_json_object_required")
            yield case


def inspect(file:str|Path)->dict:
    path=_dataset_path(file)
    sha=hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda:stream.read(1024*1024),b""):
            sha.update(part)
    categories={}
    splits={}
    total=0
    for case in _read_cases(path):
        total+=1
        category=case["category"]
        categories[category]=categories.get(category,0)+1
        split=case["split"]
        splits[split]=splits.get(split,0)+1
    if total==0:
        raise ValueError("empty_evaluation_dataset")
    return {"suite_sha256":sha.hexdigest(),"total_cases":total,
            "splits":splits,"categories":categories,
            "file_bytes":path.stat().st_size,"contains_training_cases":False}


def _subset(expected:dict,actual:dict)->bool:
    for key,value in expected.items():
        if key not in actual:
            return False
        observed=actual[key]
        if isinstance(value,dict):
            if not isinstance(observed,dict) or not _subset(value,observed):
                return False
        elif value!=observed:
            return False
    return True


def _score(case:dict,response:str,judge:Callable|None):
    mode=case["mode"]
    expected=case["expected"]
    if mode=="exact":
        success=response.strip()==expected.strip()
    elif mode=="contains":
        success=expected.casefold() in response.casefold()
    elif mode=="numeric":
        try:
            value=Decimal(response.strip())
            target=Decimal(expected.strip())
            tolerance=Decimal(str(case.get("tolerance","0")))
            if not all(x.is_finite() for x in (value,target,tolerance)) or tolerance<0:
                raise InvalidOperation()
            success=abs(value-target)<=tolerance
        except (InvalidOperation,TypeError):
            success=False
    elif mode=="json_subset":
        try:
            actual=json.loads(response)
            success=isinstance(actual,dict) and _subset(expected,actual)
        except (json.JSONDecodeError,ValueError):
            success=False
    else:
        if judge is None:
            return "unverified", ""
        outcome=judge(case,response)
        if not isinstance(outcome,dict) or type(outcome.get("passed")) is not bool:
            raise ValueError("external_judge_must_return_boolean_receipt")
        proof=outcome.get("evidence_sha256","")
        if not isinstance(proof,str) or not _SHA.fullmatch(proof):
            raise ValueError("external_judge_evidence_required")
        return ("passed" if outcome["passed"] else "failed"),proof
    return ("passed" if success else "failed"),""


def run_batch(file:str|Path,model_revision:str,provider:Callable,
              *,batch_limit:int=100,external_judge:Callable|None=None)->dict:
    """Execute at most batch_limit real model queries and persist their scores.

    No paid provider is instantiated here; supplied provider should be the
    already authorized local loopback model. A missing external verifier never
    results in a fake pass. One batch can be called repeatedly for 50k+ cases.
    """
    if not isinstance(model_revision,str) or not _MODEL.fullmatch(model_revision):
        raise ValueError("invalid_model_revision")
    if not isinstance(batch_limit,int) or not 1<=batch_limit<=500:
        raise ValueError("invalid_batch_limit")
    if not callable(provider):
        raise TypeError("real_model_provider_required")
    path=_dataset_path(file)
    report=inspect(path)
    suite=report["suite_sha256"]
    pending=[]
    with _LOCK:
        db=_db()
        try:
            prior={row[0] for row in db.execute(
                "SELECT case_id FROM evaluations WHERE suite_sha256=? AND model_revision=?",
                (suite,model_revision))}
        finally:db.close()
    for case in _read_cases(path):
        if case["id"] in prior:
            continue
        if case["mode"]=="external" and external_judge is None:
            continue
        pending.append(case)
        if len(pending)>=batch_limit:
            break
    # Freeze the selected cases against the admitted suite before inference.
    # Completed cases are committed individually; cancellation or process death
    # cannot discard earlier scores from a long-running batch.
    with path.open("rb") as source:
        if hashlib.file_digest(source,"sha256").hexdigest()!=suite:
            raise RuntimeError("evaluation_dataset_changed_before_run")
    with _LOCK:
        db=_db()
    try:
        for case in pending:
            ident="eval-"+hashlib.sha256(
                (suite+":"+model_revision+":"+case["id"]).encode()).hexdigest()[:40]
            began=time.perf_counter()
            try:
                output=provider(case["prompt"],ident)
                if not isinstance(output,dict) or not isinstance(
                    output.get("content"),str):
                    raise ValueError("actual_model_text_required")
                answer=output["content"]
                if len(answer)>500000:
                    raise ValueError("oversized_model_response")
                verdict,external_proof=_score(case,answer,external_judge)
                answer_sha=hashlib.sha256(answer.encode()).hexdigest()
                evidence=external_proof or hashlib.sha256(
                    (suite+case["id"]+answer_sha+verdict).encode()).hexdigest()
            except Exception:
                verdict="error"
                answer_sha=""
                evidence=""
            elapsed=round((time.perf_counter()-began)*1000,3)
            row=(suite,model_revision,case["id"],case["category"],
                 case["split"],case["mode"],verdict,answer_sha,
                 evidence,elapsed,time.time_ns()//1000000)
            # Autocommit + FULL synchronous WAL: no transaction is held during
            # generation, and a persisted score is available for a later batch.
            with _LOCK:
                db.execute("""INSERT OR IGNORE INTO evaluations
                    (suite_sha256,model_revision,case_id,category,split,mode,verdict,
                     response_sha256,evidence_sha256,latency_ms,scored_at_ms)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)""",row)
    finally:
        db.close()
    # The previously captured cases remain bound to the original hash; never
    # report completion of a different file if it changed during generation.
    with path.open("rb") as source:
        current=hashlib.file_digest(source,"sha256").hexdigest()
    if current!=suite:
        raise RuntimeError("evaluation_dataset_changed_during_run")
    return summary(path,model_revision)


def summary(file:str|Path,model_revision:str)->dict:
    if not isinstance(model_revision,str) or not _MODEL.fullmatch(model_revision):
        raise ValueError("invalid_model_revision")
    report=inspect(file)
    with _LOCK:
        db=_db()
        try:
            rows=[dict(zip(["category","verdict","count"],x))
                  for x in db.execute("""SELECT category,verdict,COUNT(*)
                      FROM evaluations WHERE suite_sha256=? AND model_revision=?
                      GROUP BY category,verdict ORDER BY category,verdict""",
                      (report["suite_sha256"],model_revision))]
        finally:db.close()
    passed=sum(x["count"] for x in rows if x["verdict"]=="passed")
    failed=sum(x["count"] for x in rows if x["verdict"]=="failed")
    errors=sum(x["count"] for x in rows if x["verdict"]=="error")
    assessed=passed+failed+errors
    return {"suite_sha256":report["suite_sha256"],"model_revision":model_revision,
            "total_cases":report["total_cases"],"assessed":assessed,
            "passed":passed,"failed":failed,"model_errors":errors,
            "remaining":report["total_cases"]-assessed,
            "verified_accuracy":round(passed/(passed+failed),5) if passed+failed else None,
            "categories":rows,
            "fully_evaluated":assessed==report["total_cases"],
            "model_weights_trained":False,
            "evaluations_are_real":True}
