"""Phone-native LLM memory/power admission before loading weights.

Takes ACTUAL paired phone-health observations and owner-verified model manifest
metadata. Never downloads a model or pretends a paper context window can fit
on the owner's Android hardware. No paid cloud or silent model replacement.

A successful assessment means only *safe enough to attempt a measured test*,
not that inference works, the model is trained, or application quality passes.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_MIN_OS_RESERVE = 1_000_000_000
_MIN_AVAILABLE = 1_000_000_000
_LICENSES = {"apache-2.0", "mit", "bsd-3-clause", "bsd-2-clause"}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]{2,155}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Candidate:
    repository: str
    license_id: str
    weight_file_bytes: int
    estimated_peak_ram_bytes: int | None = None
    expected_context_tokens: int = 4096
    quantization: str = "Q4_K_M"
    artifact_sha256: str = ""
    original_author_verified: bool = False


def _read_number(row: dict, key: str) -> int | None:
    value = row.get(key)
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return int(value)


def assess(phone_status: dict, candidate: Candidate) -> dict:
    if not isinstance(candidate,Candidate):
        raise TypeError("candidate_manifest_required")
    if not isinstance(candidate.repository,str) or not _ID.fullmatch(
            candidate.repository):
        raise ValueError("invalid_model_repository")
    if not isinstance(candidate.weight_file_bytes,int) or not (
            100_000_000 <= candidate.weight_file_bytes <= 50_000_000_000):
        raise ValueError("invalid_model_file_size")
    if (candidate.estimated_peak_ram_bytes is not None and
        (not isinstance(candidate.estimated_peak_ram_bytes,int) or
         candidate.estimated_peak_ram_bytes<candidate.weight_file_bytes)):
        raise ValueError("invalid_peak_ram_budget")
    if not isinstance(candidate.expected_context_tokens,int) or not (
            256<=candidate.expected_context_tokens<=65536):
        raise ValueError("invalid_test_context")
    if not isinstance(phone_status,dict):
        raise ValueError("live_phone_status_required")
    health=phone_status.get("info",{}) if phone_status.get("reachable") else {}
    if not isinstance(health,dict):
        health={}
    memory_free=_read_number(health,"memory_available")
    memory_total=_read_number(health,"memory_total")
    storage_free=_read_number(health,"storage_available")
    battery=health.get("battery",{})
    thermal=health.get("thermals",{})
    thermal_status=_read_number(thermal,"status") if isinstance(thermal,dict) else None
    battery_percent=_read_number(battery,"percent") if isinstance(battery,dict) else None
    charging=battery.get("charging",False) if isinstance(battery,dict) else False
    reasons=[]
    warnings=[]
    if not phone_status.get("paired") or not phone_status.get("reachable"):
        reasons.append("paired_phone_unreachable")
    if memory_free is None or memory_total is None or storage_free is None:
        reasons.append("live_resource_observations_missing")
    if candidate.license_id.lower() not in _LICENSES:
        reasons.append("model_license_requires_owner_review")
    if not candidate.original_author_verified:
        reasons.append("model_author_not_verified")
    if not isinstance(candidate.artifact_sha256,str) or not _HASH.fullmatch(
            candidate.artifact_sha256):
        reasons.append("model_artifact_hash_not_supplied")
    available=0
    if memory_free is not None and memory_total is not None:
        reserve=max(_MIN_OS_RESERVE,int(memory_total*0.09))
        available=max(0,memory_free-reserve)
        # Weight size is a hard *lower* bound. KV/state and native buffers
        # can require substantially more than GGUF file bytes.
        if available < candidate.weight_file_bytes:
            reasons.append("weights_exceed_free_memory_after_os_reserve")
        elif candidate.estimated_peak_ram_bytes is None:
            warnings.append("quantized_runtime_peak_memory_not_measured")
        elif candidate.estimated_peak_ram_bytes > available:
            reasons.append("estimated_runtime_peak_exceeds_available_ram")
    if storage_free is not None and storage_free < (
            candidate.weight_file_bytes*2 + 512_000_000):
        reasons.append("insufficient_storage_for_staged_model_and_rollback")
    if thermal_status is None:
        warnings.append("android_thermal_status_unknown")
    elif thermal_status >= 4:
        reasons.append("android_thermal_critical")
    elif thermal_status >= 2:
        warnings.append("android_thermal_pressure_present")
    if (battery_percent is not None and battery_percent < 20 and not charging):
        reasons.append("battery_too_low_for_model_load")
    if candidate.expected_context_tokens>8192:
        warnings.append("large_context_requires_real_kv_cache_measurement")
    eligible=not reasons and candidate.estimated_peak_ram_bytes is not None
    return {
        "repository":candidate.repository,
        "candidate_for_device_test":eligible,
        "status":"READY_FOR_CONTROLLED_BENCHMARK" if eligible else
                 "NOT_ADMITTED_OR_UNMEASURED",
        "blockers":reasons,"warnings":warnings,
        "memory_available_bytes":memory_free,
        "memory_reserve_bytes":max(_MIN_OS_RESERVE,int(memory_total*0.09))
            if memory_total is not None else None,
        "model_runtime_budget_bytes":available,
        "weight_file_bytes":candidate.weight_file_bytes,
        "estimated_peak_bytes":candidate.estimated_peak_ram_bytes,
        "observed_device":health.get("device",""),
        "model_downloaded":False,
        "model_loaded":False,
        "model_trained":False,
        "inference_device_benchmarked":False,
        "free_cloud_required":False,
    }
