"""Authenticated Asterion Control V2 services (Windows side, additive).

Existing control, pairing, WSS and Android endpoints remain unchanged.
No remote client may enable VPN or change Android policy through these routes.
Owner-approval secret is distinct from the regular paired bearer.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .security import require_token
from . import security_scanner,model_lab,skill_studio
from .bridge_worker_lock import WorkerAlreadyRunning

router=APIRouter(prefix="/api/v1/v2",dependencies=[Depends(require_token)])


def _owner_approval(value: str | None):
    expected=os.getenv("ASTERION_OWNER_APPROVAL_SECRET","")
    # On Windows, the owner must explicitly configure a second credential
    # before any privileged quarantine or skill activation is possible.
    if len(expected)<32 or not value or not hmac.compare_digest(
            value.encode("utf8"),expected.encode("utf8")):
        raise HTTPException(403,"Separate owner approval required")


def _authorized_path(value:str)->Path:
    # Reuse existing Control's configured roots, symlink checks and policy.
    from .app import safe_path, ROOT
    candidate=Path(value).expanduser()
    if not candidate.is_absolute():candidate=ROOT/candidate
    if candidate.is_symlink():raise ValueError("symlink_target_rejected")
    return safe_path(value)


def _vault()->Path:
    root=Path(os.getenv("ASTERION_QUARANTINE_ROOT",str(
        Path(os.getenv("LOCALAPPDATA",str(Path.home())))/
        "AsterionControl"/"quarantine-v2")))
    root.mkdir(parents=True,exist_ok=True)
    return root


class ScanRequest(BaseModel):
    path:str=Field(min_length=1,max_length=2048)
    profile:str=Field(default="auto",pattern="^(auto|quick|standard|deep)$")


@router.post("/security/scan")
def security_scan(body:ScanRequest):
    try:
        return security_scanner.scan(_authorized_path(body.path),level=body.profile)
    except (ValueError,OSError) as exc:
        raise HTTPException(422,type(exc).__name__) from exc


class QuarantineRequest(BaseModel):
    path:str=Field(min_length=1,max_length=2048)
    file_sha256:str=Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/security/quarantine")
def security_quarantine(body:QuarantineRequest,
                        x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:
        return security_scanner.quarantine(_authorized_path(body.path),_vault(),
                                           body.file_sha256)
    except (ValueError,OSError,WorkerAlreadyRunning) as exc:
        raise HTTPException(409,type(exc).__name__) from exc


class RestoreRequest(BaseModel):
    quarantine_id:str=Field(pattern=r"^[0-9a-f]{32}$")


@router.post("/security/quarantine/restore")
def security_restore(body:RestoreRequest,
                     x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:
        # The vault only holds files that were previously authorized by
        # safe_path; restore forbids replacing any existing destination.
        return security_scanner.restore(body.quarantine_id,_vault(),authorize=lambda p:_authorized_path(str(p)))
    except FileNotFoundError as exc:
        raise HTTPException(404,"Quarantine item not found") from exc
    except (ValueError,OSError,WorkerAlreadyRunning) as exc:
        raise HTTPException(409,type(exc).__name__) from exc


@router.get("/security/quarantine")
def security_quarantine_inventory(limit:int=50):
    try:return security_scanner.inventory(_vault(),limit)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


class ModelWatch(BaseModel):
    app:str=Field(min_length=3,max_length=80)
    repo:str=Field(min_length=5,max_length=201)
    installed_sha:str=""


@router.get("/models")
def models(app:str=""):
    try:return model_lab.list_models(app)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.get("/models/candidates")
def model_candidates(app:str=""):
    # Read-only view of the original laboratory, including immutable adapter
    # lineage. Metadata never grants deployment or execution permission.
    try:return model_lab.candidate_matrix(app)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.post("/models/watch")
def model_watch(body:ModelWatch):
    try:return model_lab.watch(body.app,body.repo,body.installed_sha)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.post("/models/refresh")
def model_refresh(body:ModelWatch):
    try:return model_lab.refresh(body.app,body.repo)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.get("/models/recommendations/{app}")
def model_recommendations(app:str):
    try:return model_lab.recommendations(app)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


class ModelBenchmark(BaseModel):
    app:str
    repo:str
    sha:str
    task_score:float=Field(ge=0,le=1)
    latency_ms:float=Field(gt=0)
    ram_mb:float=Field(gt=0)
    thermal_ok:bool
    verified:bool
    evidence_sha256:str


@router.post("/models/benchmark")
def model_benchmark(body:ModelBenchmark):
    try:return model_lab.benchmark(**body.model_dump())
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


class SkillCreate(BaseModel):
    id:str=Field(min_length=4,max_length=72)
    description:str=Field(min_length=4,max_length=180)
    device:str
    steps:list[dict]=Field(min_length=1,max_length=80)
    timeout_s:int=Field(default=120,ge=2,le=300)


@router.post("/skills")
def create_skill(body:SkillCreate):
    try:return skill_studio.create(body.id,body.description,body.device,
                                   body.steps,body.timeout_s)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.get("/skills")
def list_skills(limit:int=40):
    try:return skill_studio.index(limit)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.get("/skills/{skill_id}")
def get_skill(skill_id:str):
    try:return skill_studio.details(skill_id)
    except KeyError as exc:raise HTTPException(404,"Skill not found") from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.get("/skills/{skill_id}/versions")
def skill_versions(skill_id:str):
    try:return skill_studio.versions(skill_id)
    except KeyError as exc:raise HTTPException(404,"Skill not found") from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


class SkillRollback(BaseModel):
    version:int=Field(ge=1)
    current_sha256:str=Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/skills/{skill_id}/rollback")
def rollback_skill(skill_id:str,body:SkillRollback,x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:return skill_studio.rollback(skill_id,body.version,body.current_sha256)
    except KeyError as exc:raise HTTPException(404,"Skill version not found") from exc
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc


class SkillApproval(BaseModel):
    sha256:str=Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/skills/{skill_id}/approve")
def approve_skill(skill_id:str,body:SkillApproval,
                  x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:return skill_studio.approve(skill_id,body.sha256)
    except KeyError as exc:raise HTTPException(404,"Skill not found") from exc
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc


@router.post("/skills/{skill_id}/revoke")
def revoke_skill(skill_id:str,x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:return skill_studio.revoke(skill_id)
    except KeyError as exc:raise HTTPException(404,"Skill not found") from exc


class SkillExecution(BaseModel):
    sha256:str=Field(pattern=r"^[0-9a-f]{64}$")
    request_id:str=Field(min_length=8,max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,99}$")


@router.post("/skills/{skill_id}/run")
def execute_skill(skill_id:str,body:SkillExecution):
    try:return skill_studio.execute(skill_id,body.sha256,body.request_id)
    except KeyError as exc:raise HTTPException(404,"Skill not found") from exc
    except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
