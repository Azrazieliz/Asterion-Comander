"""Evidence-only triage of opted-in Asterion Control diagnostic events.

Never guesses an HTTP 403 cause, active queue ownership or a crash stack.
Reads only metadata already admitted by diagnostic_core; it neither launches
apps nor retrieves private content, credentials or arbitrary Android logs.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any

from . import diagnostic_core as core

_PENDING = {"created", "waiting", "queued", "runnable", "retry_wait", "paused"}
_RUNNING = {"running", "started", "connecting", "transferring"}
_SUCCESS = {"completed", "complete", "canceled", "cancelled", "stopped"}
_FAILURE = {"failed", "crashed", "timed_out", "blocked", "outcome_unknown", "error"}
_FAILURE_KINDS = {
    "crash", "anr", "exception", "transport_error", "engine_failure",
    "http_failure", "worker_dead", "download_stalled", "app_exit",
    "control_failure", "security_failure",
}
_STATES = _PENDING | _RUNNING | _SUCCESS | _FAILURE
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,95}$")


def _parameters(app: str, lookback_minutes: int, limit: int, stale_after_seconds: int) -> None:
    if app and (not isinstance(app, str) or not _IDENTIFIER.fullmatch(app)):
        raise ValueError("Invalid application identifier")
    if not isinstance(lookback_minutes, int) or not 1 <= lookback_minutes <= 10080:
        raise ValueError("Lookback must be 1..10080 minutes")
    if not isinstance(limit, int) or not 1 <= limit <= 3000:
        raise ValueError("Event limit must be 1..3000")
    if not isinstance(stale_after_seconds, int) or not 30 <= stale_after_seconds <= 86400:
        raise ValueError("Staleness threshold must be 30..86400 seconds")


def _observed_category(event: dict) -> str | None:
    """Classify *symptoms*, never unmeasured underlying causes."""
    kind = event["kind"]
    attrs = event["attributes"]
    if kind == "http_failure" and attrs.get("status_code") == 403:
        return "http_403_observed_not_root_cause"
    if kind in {"crash", "anr", "worker_dead", "download_stalled"}:
        return kind + "_reported"
    if kind == "http_failure":
        return "http_failure_reported"
    if kind in _FAILURE_KINDS:
        return kind + "_reported"
    if event["state"] in _FAILURE:
        return "failure_state_reported"
    return None


def inspect(*, app: str = "", lookback_minutes: int = 1440,
            limit: int = 1200, stale_after_seconds: int = 300,
            now_ms: int | None = None) -> dict[str, Any]:
    """Produce a bounded correlation snapshot with explicit evidence limits.

    An older 'queued' status does not prove a job remains queued right now;
    only a fresh engine state/heartbeat can establish current queue ownership.
    """
    _parameters(app, lookback_minutes, limit, stale_after_seconds)
    if now_ms is None:
        now_ms = time.time_ns() // 1_000_000
    if not isinstance(now_ms, int) or now_ms < 0:
        raise ValueError("Invalid observation time")
    cutoff = max(0, now_ms - lookback_minutes * 60000)
    filters = ["recorded_utc_ms>=?", "recorded_utc_ms<=?"]
    args: list[Any] = [cutoff, now_ms]
    if app:
        filters.append("app=?")
        args.append(app)
    query = (
        "SELECT seq,recorded_utc_ms,app,component,kind,state,severity,"
        "operation_id,trace_id,attributes_json FROM events WHERE "
        + " AND ".join(filters) + " ORDER BY seq DESC LIMIT ?"
    )
    rows = core._query(query, tuple(args + [limit]))
    # Results are a recent bounded observation window, NOT a complete job ledger.
    rows.reverse()
    operations: dict[tuple[str, str], dict] = {}
    symptoms: Counter[str] = Counter()
    components: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    notable: list[dict] = []
    observed_apps: set[str] = set()
    for row in rows:
        attrs = json.loads(row["attributes_json"])
        observed_apps.add(row["app"])
        components[row["component"]] += 1
        if "provider" in attrs:
            providers[str(attrs["provider"])] += 1
        event = {**row, "attributes": attrs}
        event.pop("attributes_json", None)
        symptom = _observed_category(event)
        if symptom:
            symptoms[symptom] += 1
            if len(notable) < 25:
                notable.append({
                    "sequence": row["seq"], "recorded_utc_ms": row["recorded_utc_ms"],
                    "app": row["app"], "component": row["component"],
                    "operation_id": row["operation_id"], "trace_id": row["trace_id"],
                    "kind": row["kind"], "state": row["state"],
                    "symptom": symptom,
                    "status_code": attrs.get("status_code"),
                    "error_code": attrs.get("error_code"),
                    "stage": attrs.get("stage"),
                })
        operation_id = row["operation_id"]
        if operation_id in {"", "unspecified"}:
            continue
        key = (row["app"], operation_id)
        item = operations.get(key)
        if item is None:
            item = {
                "app": row["app"], "operation_id": operation_id,
                "first_observed_ms": row["recorded_utc_ms"],
                "last_observed_ms": row["recorded_utc_ms"],
                "first_sequence": row["seq"], "last_sequence": row["seq"],
                "event_count": 0, "last_state": "unknown",
                "last_kind": row["kind"], "last_component": row["component"],
                "trace_id": row["trace_id"], "stage": None,
                "last_reported_queue_depth": None,
                "last_reported_active_workers": None,
                "last_reported_worker_limit": None,
                "reported_failure": False,
            }
            operations[key] = item
        item["event_count"] += 1
        item["last_observed_ms"] = row["recorded_utc_ms"]
        item["last_sequence"] = row["seq"]
        item["last_kind"] = row["kind"]
        item["last_component"] = row["component"]
        if row["trace_id"] != "unspecified":
            item["trace_id"] = row["trace_id"]
        if row["state"] in _STATES:
            item["last_state"] = row["state"]
        for name, field in (
            ("stage", "stage"),
            ("queue_depth", "last_reported_queue_depth"),
            ("active_workers", "last_reported_active_workers"),
            ("worker_limit", "last_reported_worker_limit"),
        ):
            if name in attrs:
                item[field] = attrs[name]
        if symptom:
            item["reported_failure"] = True

    items: list[dict] = []
    suspected_idle: list[dict] = []
    for item in operations.values():
        age_seconds = max(0, (now_ms - item["last_observed_ms"]) // 1000)
        state = item["last_state"]
        item["seconds_since_last_observation"] = age_seconds
        item["current_status_verified"] = False
        item["evidence"] = "bounded_historical_instrumented_events"
        item["review_reason"] = None
        if state in _PENDING | _RUNNING and age_seconds >= stale_after_seconds:
            item["review_reason"] = "stale_nonterminal_observation"
            # Counter snapshots are not real-time measurements and are not
            # enough to conclusively diagnose the queue's current state.
            suspected_idle.append({
                "app": item["app"], "operation_id": item["operation_id"],
                "last_state": state,
                "seconds_since_last_observation": age_seconds,
                "last_reported_queue_depth": item["last_reported_queue_depth"],
                "last_reported_active_workers": item["last_reported_active_workers"],
                "assessment": "fresh_engine_or_worker_snapshot_required",
            })
        elif state in _FAILURE:
            item["review_reason"] = "reported_failure_requires_causal_evidence"
        items.append(item)
    items.sort(key=lambda x: x["last_sequence"], reverse=True)
    suspected_idle.sort(key=lambda x: x["seconds_since_last_observation"], reverse=True)

    findings = []
    if symptoms.get("http_403_observed_not_root_cause"):
        findings.append({
            "code": "http_403",
            "confidence": "observed_http_status_only",
            "meaning": "403 observed; neither geography nor extractor failure is proven",
            "required_next_evidence": "request_stage_provider_response_classification",
        })
    if suspected_idle:
        findings.append({
            "code": "stale_operations",
            "confidence": "historical_observation_only",
            "meaning": "No recent journal update for nonterminal operations",
            "required_next_evidence": "current_queue_worker_and_operation_heartbeat",
        })
    if symptoms.get("crash_reported") or symptoms.get("anr_reported"):
        findings.append({
            "code": "crash_or_anr_reported",
            "confidence": "instrumented_report_only",
            "meaning": "A failure was recorded; root cause requires stack or tombstone",
            "required_next_evidence": "matching_stack_or_tombstone_build_sha",
        })
    return {
        "ok": True, "schema_version": 1,
        "snapshot_utc_ms": now_ms, "app_filter": app or None,
        "observed_apps": sorted(observed_apps),
        "lookback_minutes": lookback_minutes,
        "events_examined": len(rows), "events_limit": limit,
        "window_may_be_truncated": len(rows) == limit,
        "current_runtime_state_verified": False,
        "symptom_counts": dict(symptoms),
        "component_event_counts": dict(components.most_common(25)),
        "provider_event_counts": dict(providers.most_common(25)),
        "operations": items[:200],
        "operations_truncated": len(items) > 200,
        "needs_fresh_state": suspected_idle[:100],
        "notable_events": notable,
        "findings": findings,
        "limitations": [
            "Only opted-in sanitized events; uninstrumented failures are invisible",
            "No current phone/process/queue status is inferred from old events",
            "HTTP 403 alone cannot identify geo, authentication or extractor cause",
            "No real crash stack, HTTP body or private files are collected",
        ],
    }
