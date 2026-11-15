"""Live paired-phone model admission, no downloads, model loads or paid API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .security import require_token
from .native_routes import phone_status
from .model_admission import Candidate,assess

router=APIRouter(prefix="/api/v1/intelligence/models/capacity",
                 dependencies=[Depends(require_token)])


@router.get("/phone")
def phone_capacity():
    phone=phone_status()
    info=phone.get("info") if phone.get("reachable") else None
    if not isinstance(info,dict):
        return {"ok":False,"state":"PHONE_UNREACHABLE",
                "model_loaded":False,"phone_model_verified":False}
    return {"ok":True,"device":phone.get("device"),
            "android":info.get("android"),
            "memory_available":info.get("memory_available"),
            "memory_total":info.get("memory_total"),
            "storage_available":info.get("storage_available"),
            "battery":info.get("battery"),
            "thermals":info.get("thermals"),
            "model_loaded":False,"phone_model_verified":False}


class CandidateRequest(BaseModel):
    repository:str=Field(min_length=3,max_length=156)
    license_id:str=Field(min_length=3,max_length=32)
    weight_file_bytes:int=Field(ge=100_000_000,le=50_000_000_000)
    estimated_peak_ram_bytes:int|None=None
    expected_context_tokens:int=Field(default=4096,ge=256,le=65536)
    quantization:str="Q4_K_M"
    artifact_sha256:str=""
    original_author_verified:bool=False


@router.post("/phone/check")
def check_phone_candidate(body:CandidateRequest):
    phone=phone_status()
    try:
        return {"ok":True,**assess(phone,Candidate(**body.model_dump()))}
    except (ValueError,TypeError) as exc:
        raise HTTPException(422,type(exc).__name__) from exc
