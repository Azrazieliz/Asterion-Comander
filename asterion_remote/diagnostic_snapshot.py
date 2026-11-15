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
        result.update({
            "reachable": True,
            "status_observation": "fresh_native_health_response",
            "capture": info.get("capture") is True,
            "accessibility": info.get("accessible") is True,
            "android": str(info.get("android", "unknown"))[:20],
            "transport": {
                "connected": (info.get("remote_transport") or {}).get("connected") is True,
                "validated": (info.get("remote_transport") or {}).get("validated") is True,
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
        "android": _phone() if phone else {
            "requested": False, "reachability_verified": False
        },
        "cross_app_private_logs_accessible": False,
        "root_cause_verified": False,
        "limitations": [
            "A single snapshot is not a continuous diagnostic stream",
            "Only opted-in sanitized partner-app events can be correlated",
            "Phone native journal and exits cover Control itself, not other apps",
            "HTTP 403 and historical queued events alone do not prove a cause",
        ],
    }
    return result
