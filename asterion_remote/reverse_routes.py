"""Authenticated missing-source third-party binary analysis.

Operates on owner-approved Control roots only. Does not open private Android
app storage or execute downloaded files. Full JADX/Ghidra decompilation and
dynamic instrumentation are separate owner-approved tool operations.
"""
from __future__ import annotations

from fastapi import APIRouter,Depends,Header,HTTPException
from pydantic import BaseModel,Field
from .security import require_token
from .control_v2_routes import _owner_approval
from .reverse_lab import inspect

router=APIRouter(prefix="/api/v1/intelligence/reverse",
                 dependencies=[Depends(require_token)])


class AnalyzeFile(BaseModel):
    path:str=Field(min_length=1,max_length=2048)


@router.get("/status")
def reverse_status():
    return {"ok":True,"static_inspection_source_ready":True,
            "supported":["PE","ELF","DEX","APK","ZIP"],
            "full_decompilation_installed":False,
            "dynamic_instrumentation_installed":False,
            "owner_file_authorization_required":True,
            "original_binary_modified":False}


@router.post("/inspect")
def reverse_inspect(body:AnalyzeFile,
                    x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    from .app import safe_path
    try:
        return inspect(safe_path(body.path))
    except (PermissionError,ValueError) as exc:
        raise HTTPException(422,type(exc).__name__) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404,"Binary file not found") from exc
    except (OSError,RuntimeError) as exc:
        raise HTTPException(409,"Binary inspection incomplete: "+
                            type(exc).__name__) from exc
