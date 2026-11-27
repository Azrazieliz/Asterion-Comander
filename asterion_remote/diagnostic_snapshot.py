"""Single authenticated, bounded, non-invasive diagnostic evidence snapshot.

Cross-app events exist only where a partner explicitly opted in. This collector
uses the existing paired phone transport; it never restarts services, opens
another gateway, reads another app's private logs, or changes device state.
"""
from __future__ import annotations
import time
from typing import Any
from . import diagnostic_analysis
from . import phone_bridge
from .control_services import host_health


_GIB = 1024 ** 3

def _resource_pair(available, total):
    """Advisory absolute pressure bands, not workload admission or causation."""
    if (type(available) is not int or type(total) is not int or
            not 0 <= available <= total or total <= 0):
        return {"available": False, "reason": "missing_or_invalid_measurement"}
    band = ("critical" if available < _GIB else
            "low" if available < 2 * _GIB else "above_low_threshold")
    return {"available": True, "available_bytes": available,
            "total_bytes": total, "pressure_band": band}

def _resource_findings(scope, resource, observation, label=None):
    if not observation.get("available") or observation.get("pressure_band") not in {"critical", "low"}:
        return []
    row={"code": scope + "_" + resource + "_pressure",
         "severity": observation["pressure_band"], "scope": scope,
         "resource": resource, "available_bytes": observation["available_bytes"],
         "total_bytes": observation["total_bytes"],
         "root_cause_verified": False,
         "next_step": ("Review storage usage and approved cleanup; avoid new large writes."
                       if resource=="storage" else
                       "Review active workload and measured memory requirements before starting new work.")}
    if label is not None:
        row["volume"]=label
    return [row]

def _pc_resources():
    try:
        info=host_health()
        memory=info.get("memory") or {}
        ram=_resource_pair(memory.get("available"), memory.get("total"))
        findings=_resource_findings("pc","memory",ram)
        volumes=[]
        for index,disk in enumerate(info.get("disks") or []):
            if index>=32:
                break
            if not isinstance(disk,dict):
                continue
            mount=disk.get("mount")
            # Never include arbitrary folder names or network share paths.
            label=(mount[:2].upper() if isinstance(mount,str) and len(mount)==3
                   and mount[0].isascii() and mount[0].isalpha()
                   and mount[1:]==":\\"
                   else "/" if mount=="/" else f"volume-{index+1}")
            observation=_resource_pair(disk.get("free"),disk.get("total"))
            volumes.append({"volume":label,**observation})
            findings.extend(_resource_findings("pc","storage",observation,label))
        return {"observed":True,"sampled_at":info.get("sampled_at"),
                "memory":ram,"volumes":volumes,"findings":findings,
                "thresholds_bytes":{"critical_below":_GIB,"low_below":2*_GIB},
                "root_cause_verified":False}
    except Exception as exc:
        return {"observed":False,"reason":type(exc).__name__,"findings":[],
                "root_cause_verified":False}

def _phone() -> dict[str, Any]:
    paired = phone_bridge.load()
    if not paired:
        return {"paired": False, "reachable": False, "reason": "no_existing_pairing"}
    result: dict[str, Any] = {
        "paired": True, "reachable": False, "device": str(paired.get("device", "Android"))[:80],
        "own_process_journal": "unavailable", "own_process_exit_history": "unavailable",
    }
    try:
        info = phone_bridge.request("/health", timeout=4).json()
        if not isinstance(info, dict) or not info.get("ok"):
            raise ValueError("Invalid native health response")
        raw_transport=info.get("remote_transport") or {}
        if not isinstance(raw_transport,dict):
            raw_transport={}
        wss=raw_transport.get("direct_mcp") or {}
        if not isinstance(wss,dict):
            wss={}
        network=raw_transport.get("network")
        ram=_resource_pair(info.get("memory_available"),info.get("memory_total"))
        storage=_resource_pair(info.get("storage_available"),info.get("storage_total"))
        result.update({
            "reachable": True,
            "reachability_verified": True,
            "resources":{"memory":ram,"storage":storage,
                         "findings":_resource_findings("android","memory",ram)+
                                    _resource_findings("android","storage",storage)},
            "status_observation": "fresh_native_health_response",
            "capture": info.get("capture") is True,
            "accessibility": info.get("accessible") is True,
            "android": str(info.get("android", "unknown"))[:20],
            "transport": {
                "connected": raw_transport.get("connected") is True,
                "validated": raw_transport.get("validated") is True,
                "network": network if network in ("wifi","cellular","ethernet","vpn") else "unknown",
                "native_wss_connected": (wss.get("connected") if
                    wss.get("transport")=="direct_wss" and type(wss.get("connected")) is bool else None),
            },
        })
    except Exception as exc:
        result["reason"] = "native_health_" + type(exc).__name__
        # A previously paired device is not proven offline by a single timeout.
        result["reachability_verified"] = False
        return result
    try:
        # This native endpoint accepts POST but only reads the owner's private
        # bounded SQLite journal; it does not perform a device action.
        journal = phone_bridge.request(
            "/diagnostics/events", "POST", {"since": 0, "limit": 1}, timeout=4
        ).json()
        if journal.get("scope") != "asterion_control_process_only":
            raise ValueError("Unrecognized Android journal scope")
        latest = int(journal.get("latest_sequence", 0))
        page = phone_bridge.request(
            "/diagnostics/events", "POST",
            {"since": max(0, latest - 39), "limit": 40}, timeout=4
        ).json()
        if page.get("scope") != "asterion_control_process_only":
            raise ValueError("Unrecognized Android journal scope")
        events = page.get("events", [])
        if not isinstance(events, list):
            raise ValueError("Invalid native event list")
        result["own_process_journal"] = {
            "scope": "asterion_control_process_only", "latest_sequence": latest,
            "events_examined": len(events),
            "records": [{
                "seq": event.get("seq"),
                "kind": event.get("kind"),
                "stage": event.get("stage"),
                "state": event.get("state"),
                "reason_code": event.get("reason_code"),
            } for event in events if isinstance(event, dict)][-40:],
        }
    except Exception as exc:
        result["own_process_journal"] = {
            "available": False, "reason": type(exc).__name__,
        }
    try:
        exits = phone_bridge.request("/diagnostics/exit-history", timeout=4).json()
        if (not isinstance(exits, dict) or
                exits.get("scope") != "own_process_only"):
            raise ValueError("Unrecognized native exit-history scope")
        items = exits.get("exits", [])
        if not isinstance(items, list):
            raise ValueError("Invalid exit history")
        result["own_process_exit_history"] = {
            "scope": "own_process_only",
            "supported": exits.get("supported", True) is True,
            "records": [{
                "reason_code": e.get("reason_code"),
                "timestamp_ms": e.get("timestamp_ms"),
            } for e in items[:12] if isinstance(e, dict)],
        }
    except Exception as exc:
        result["own_process_exit_history"] = {
            "available": False, "reason": type(exc).__name__,
        }
    return result


def collect(*, app: str = "", phone: bool = True, limit: int = 600,
            lookback_minutes: int = 1440) -> dict[str, Any]:
    if type(phone) is not bool:
        raise ValueError("Invalid phone selection")
    snapshot_ms = time.time_ns() // 1_000_000
    triage = diagnostic_analysis.inspect(
        app=app, limit=limit, lookback_minutes=lookback_minutes,
        now_ms=snapshot_ms)
    result = {
        "ok": True, "schema_version": 1, "snapshot_utc_ms": snapshot_ms,
        "side_effects_performed": False, "source": "authenticated_paired_control",
        "pc_instrumented_events": triage,
        "pc_resources": _pc_resources(),
        "android": _phone() if phone else {
            "requested": False, "reachability_verified": False
        },
        "cross_app_private_logs_accessible": False,
        "root_cause_verified": False,
        "limitations": [
            "A single snapshot is not a continuous diagnostic stream",
            "Resource pressure bands are advisory, not workload admission or proof of root cause",
            "Only opted-in sanitized partner-app events can be correlated",
            "Phone native journal and exits cover Control itself, not other apps",
            "HTTP 403 and historical queued events alone do not prove a cause",
        ],
    }
    return result
