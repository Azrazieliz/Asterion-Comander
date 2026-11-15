"""Control Security Center: explicit Windows file guardian configuration/status.

Existing quarantine/restore continues through V2 API, unchanged.
A scan action is separately owner-approved; status is authenticated.
"""
from __future__ import annotations

from fastapi import APIRouter,Depends,Header,HTTPException
from .security import require_token
from .control_v2_routes import _owner_approval
from . import security_guardian

router=APIRouter(prefix="/api/v1/intelligence/security",
                 dependencies=[Depends(require_token)])


@router.get("/guardian/status")
def guardian_status():
    return {"ok":True,**security_guardian.status()}


@router.post("/guardian/scan")
def guardian_scan(x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:return security_guardian.scan_once()
    except PermissionError as exc:
        raise HTTPException(403,type(exc).__name__) from exc
    except (RuntimeError,ValueError) as exc:
        raise HTTPException(409,"Guardian configuration blocked: "+
                            type(exc).__name__) from exc
