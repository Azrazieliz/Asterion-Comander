"""Asterion Control: private structured telemetry and crash-safe incident journal.

No global phone monitoring, privileged Android access, packet interception or AI.
Records approved, bounded metadata from Control and opted-in partner adapters.
The existing authenticated worker API is the only remote reader/writer.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_EVENT_CHANGED = threading.Condition()
_SAFE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,95}$")
_ALLOWED_FIELDS = {
    "stage", "state", "device", "device_role", "transport", "network_type",
    "status_code", "http_method", "endpoint_kind", "provider", "reason",
    "error_class", "exception_class", "worker_id", "job_id", "queue_depth",
    "active_workers", "worker_limit", "bytes_received", "bytes_written",
    "throughput_bps", "retry_count", "duration_ms", "elapsed_ms",
    "latency_ms", "stream_state", "component", "app_version", "version_code",
    "build_sha", "model_hash", "connection_epoch", "step_index",
    "verified", "dropped_events", "pid", "thread_id", "exit_code",
    "permission_state", "availability", "error_code", "file_sha256",
    "output_valid", "event_source", "recorded_utc",
}
_INCIDENT_KINDS = {
    "crash", "anr", "exception", "transport_error", "engine_failure",
    "http_failure", "worker_dead", "download_stalled", "app_exit",
    "control_failure", "security_failure",
}
_TERMINAL_FAILURES = {"error", "failed", "crashed", "timed_out", "outcome_unknown"}
_MAX_EVENT_BYTES = 8192
_DEFAULT_LIMIT = 20000
_DEFAULT_INCIDENT_LIMIT = 1000


def _state_root() -> Path:
    home = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return Path(os.environ.get("ASTERION_DIAGNOSTIC_ROOT", str(home / "AsterionControl" / "diagnostics")))


def _database_path() -> Path:
    root = _state_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / "events.sqlite3"


def _db():
    connection = sqlite3.connect(str(_database_path()), timeout=5, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS events(
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            recorded_utc_ms INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            operation_id TEXT NOT NULL,
            app TEXT NOT NULL,
            component TEXT NOT NULL,
            kind TEXT NOT NULL,
            state TEXT NOT NULL,
            severity TEXT NOT NULL,
            attributes_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id,seq);
        CREATE INDEX IF NOT EXISTS idx_events_app ON events(app,seq);
        CREATE TABLE IF NOT EXISTS incidents(
            incident_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            first_seq INTEGER NOT NULL,
            last_seq INTEGER NOT NULL,
            count INTEGER NOT NULL,
            app TEXT NOT NULL,
            kind TEXT NOT NULL,
            component TEXT NOT NULL,
            reason TEXT NOT NULL,
            first_seen_ms INTEGER NOT NULL,
            last_seen_ms INTEGER NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_incident_fingerprint ON incidents(fingerprint);
        CREATE TABLE IF NOT EXISTS incident_snapshots(
            incident_id TEXT PRIMARY KEY,
            captured_utc_ms INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            content_json TEXT NOT NULL
        );
    """)
    return connection


def _safe_id(value: Any, fallback: str = "unspecified") -> str:
    if not isinstance(value, str) or not _SAFE.fullmatch(value):
        return fallback
    return value


def _sanitize_attributes(value: Any) -> dict:
    """Allowlisted telemetry only. Reject URL/header/cookie/body/token/path contents."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, raw in value.items():
        if key not in _ALLOWED_FIELDS:
            continue
        if isinstance(raw, bool):
            result[key] = raw
        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
            if abs(raw) < 1e15:
                result[key] = raw
        elif isinstance(raw, str):
            # Field-specific freeform data is deliberately short and sanitized.
            if key in {"reason", "error_class", "exception_class", "stage"}:
                # Persist only short static diagnostic identifiers, not raw
                # exception messages/URLs that might contain owner credentials.
                value=raw.strip()
                result[key]=(value if _SAFE.fullmatch(value) and not
                    re.search(r"(?i)(?:password|bearer|token|secret|cookie|credential)",value)
                    else "redacted_non_identifier")
            elif _SAFE.fullmatch(raw):
                result[key] = raw
    return result


def record(
    kind: str, *,
    app: str = "asterion.control",
    component: str = "worker",
    state: str = "observed",
    severity: str = "info",
    session_id: str = "",
    trace_id: str = "",
    operation_id: str = "",
    attributes: dict | None = None,
    incident: bool = False,
) -> dict:
    kind = _safe_id(kind, "unknown")
    app = _safe_id(app, "unknown")
    component = _safe_id(component, "unknown")
    state = _safe_id(state, "unknown")
    severity = severity if severity in {"debug","info","warning","error","critical"} else "info"
    session_id = _safe_id(session_id)
    trace_id = _safe_id(trace_id)
    operation_id = _safe_id(operation_id)
    attrs = _sanitize_attributes(attributes)
    if len(json.dumps(attrs, ensure_ascii=True)) > _MAX_EVENT_BYTES:
        raise ValueError("Telemetry metadata too large")
    event_id = uuid.uuid4().hex
    timestamp = time.time_ns() // 1_000_000
    should_incident = incident or kind in _INCIDENT_KINDS or (severity in {"error", "critical"} and state in _TERMINAL_FAILURES)
    fingerprint = hashlib.sha256(f"{app}\n{component}\n{kind}\n{attrs.get('error_class','')}\n{attrs.get('error_code','')}\n{attrs.get('stage','')}".encode()).hexdigest()[:32]
    with _LOCK:
        con = _db()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                """INSERT INTO events(event_id,recorded_utc_ms,session_id,trace_id,
                   operation_id,app,component,kind,state,severity,attributes_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id,timestamp,session_id,trace_id,operation_id,app,component,kind,state,severity,
                 json.dumps(attrs,sort_keys=True,separators=(",",":"))),
            )
            seq = cur.lastrowid
            event_incident_id = None
            if should_incident:
                con.execute(
                    """INSERT INTO incidents(incident_id,fingerprint,first_seq,last_seq,
                       count,app,kind,component,reason,first_seen_ms,last_seen_ms)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(fingerprint) DO UPDATE SET
                       last_seq=excluded.last_seq,count=count+1,last_seen_ms=excluded.last_seen_ms""",
                    (uuid.uuid4().hex,fingerprint,seq,seq,1,app,kind,component,
                     attrs.get("reason",attrs.get("error_class",""))[:160],timestamp,timestamp),
                )
                event_incident_id=con.execute(
                    "SELECT incident_id FROM incidents WHERE fingerprint=?",
                    (fingerprint,)).fetchone()[0]
                if not con.execute(
                    "SELECT 1 FROM incident_snapshots WHERE incident_id=?",
                    (event_incident_id,)).fetchone():
                    # Immutable pre-failure window. Same-app, bounded to 30
                    # sanitized records from the last five minutes.
                    con.row_factory=sqlite3.Row
                    rows=con.execute(
                        """SELECT seq,event_id,recorded_utc_ms,session_id,trace_id,
                            operation_id,app,component,kind,state,severity,attributes_json
                            FROM events WHERE app=? AND recorded_utc_ms>=? AND seq<=?
                            ORDER BY seq DESC LIMIT 30""",
                        (app,timestamp-300000,seq)).fetchall()
                    snapshot_events=[]
                    for entry in reversed(rows):
                        row=dict(entry)
                        row["attributes"]=json.loads(row.pop("attributes_json"))
                        snapshot_events.append(row)
                    snapshot={
                        "schema_version":1,"incident_id":event_incident_id,
                        "fingerprint":fingerprint,"trigger_seq":seq,
                        "captured_utc_ms":timestamp,
                        "classification":"unresolved",
                        "scope":"redacted_control_instrumented_events",
                        "post_failure_capture":False,
                        "events":snapshot_events,
                    }
                    body=json.dumps(snapshot,sort_keys=True,separators=(",",":"))
                    signature=hashlib.sha256(body.encode("utf8")).hexdigest()
                    con.execute(
                        """INSERT INTO incident_snapshots(
                            incident_id,captured_utc_ms,sha256,content_json)
                            VALUES(?,?,?,?)""",
                        (event_incident_id,timestamp,signature,body))
            # Bounded local journal, deterministic oldest-first pruning.
            if seq % 128 == 0:
                con.execute("DELETE FROM events WHERE seq <= (SELECT COALESCE(MAX(seq),0)-? FROM events)",(_DEFAULT_LIMIT,))
                con.execute(
                    "DELETE FROM incidents WHERE last_seen_ms < (SELECT COALESCE(MAX(last_seen_ms),0) FROM incidents)-? AND incident_id NOT IN (SELECT incident_id FROM incidents ORDER BY last_seen_ms DESC LIMIT ?)",
                    (90*24*60*60*1000,_DEFAULT_INCIDENT_LIMIT),
                )
                con.execute("DELETE FROM incident_snapshots WHERE incident_id NOT IN (SELECT incident_id FROM incidents)")
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
    # Notify after SQLite COMMIT, never wake a subscriber on uncommitted data.
    # Subscribers always requery SQLite, so a missed notification cannot lose data.
    with _EVENT_CHANGED:
        _EVENT_CHANGED.notify_all()
    result={"ok":True,"event_id":event_id,"sequence":seq,"incident":should_incident}
    if should_incident:
        result["incident_id"]=event_incident_id
    return result


def _query(sql: str, args: tuple = ()) -> list[dict]:
    with _LOCK:
        con = _db()
        try:
            con.row_factory = sqlite3.Row
            rows = con.execute(sql,args).fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()


def events(*, since: int = 0, limit: int = 100, app: str = "", trace_id: str = "") -> dict:
    if not (0 <= since < 2**62 and 1 <= limit <= 500):
        raise ValueError("Invalid event pagination")
    filters = ["seq > ?"]
    args: list[Any] = [since]
    if app:
        filters.append("app = ?")
        args.append(_safe_id(app))
    if trace_id:
        filters.append("trace_id = ?")
        args.append(_safe_id(trace_id))
    rows = _query(
        "SELECT * FROM events WHERE " + " AND ".join(filters) + " ORDER BY seq ASC LIMIT ?", tuple(args+[limit])
    )
    for row in rows:
        row["attributes"] = json.loads(row.pop("attributes_json"))
    return {"ok":True,"events":rows,"next_sequence":rows[-1]["seq"] if rows else since}


def incidents(*, limit: int = 100, app: str = "") -> dict:
    if not 1 <= limit <= 500:
        raise ValueError("Invalid incident pagination")
    q = "SELECT * FROM incidents"
    args: list[Any] = []
    if app:
        q += " WHERE app = ?"
        args.append(_safe_id(app))
    rows = _query(q+" ORDER BY last_seen_ms DESC LIMIT ?",tuple(args+[limit]))
    return {"ok":True,"incidents":rows}




def incident_bundle(incident_id: str) -> dict | None:
    """Retrieve the exact immutable, sanitized evidence captured at first trigger."""
    if not isinstance(incident_id,str) or not re.fullmatch(r"[0-9a-f]{32}",incident_id):
        raise ValueError("Invalid incident identifier")
    rows=_query(
        """SELECT s.sha256,s.content_json,
            i.count,i.first_seen_ms,i.last_seen_ms
            FROM incident_snapshots s JOIN incidents i
            ON s.incident_id=i.incident_id
            WHERE s.incident_id=?""",(incident_id,))
    if not rows:
        return None
    saved=rows[0]
    raw=saved["content_json"]
    actual=hashlib.sha256(raw.encode("utf8")).hexdigest()
    if actual!=saved["sha256"]:
        raise RuntimeError("Incident evidence integrity check failed")
    evidence=json.loads(raw)
    # Preserve immutable contents and hash; aggregate count is separate metadata.
    return {"ok":True,"evidence_sha256":actual,"evidence":evidence,
            "occurrences":saved["count"],
            "first_seen_ms":saved["first_seen_ms"],
            "last_seen_ms":saved["last_seen_ms"],
            "immutable_snapshot":True,"redacted":True}


def trace_events(trace_id: str, limit: int = 500) -> dict:
    """A paginated, bounded evidence-backed operation graph (not inferred)."""
    if not isinstance(trace_id,str) or _safe_id(trace_id)!=trace_id or trace_id=="unspecified":
        raise ValueError("Invalid trace identifier")
    if not 1 <= limit <= 500:
        raise ValueError("Invalid trace limit")
    return events(since=0,limit=limit,trace_id=trace_id)

def health() -> dict:
    rows = _query("SELECT COUNT(*) AS n,COALESCE(MAX(seq),0) AS latest FROM events")
    issues = _query("SELECT COUNT(*) AS n FROM incidents")
    return {"ok":True,"schema_version":1,"journal":"durable_sqlite","engine_adapters":"opt_in",
            "event_count":rows[0]["n"],"latest_sequence":rows[0]["latest"],
            "incident_fingerprint_count":issues[0]["n"],
            "global_logcat":False,"arbitrary_app_private_memory":False,
            "vpn_enabled":False,"security_level":"existing_pairing"}




def bounds() -> dict:
    """Durable cursor range and retention state for streaming subscribers."""
    rows = _query("SELECT COALESCE(MIN(seq),0) AS oldest, COALESCE(MAX(seq),0) AS latest, COUNT(*) AS total FROM events")
    return {"oldest_sequence":rows[0]["oldest"],"latest_sequence":rows[0]["latest"],
            "retained_events":rows[0]["total"]}


def wait_for_change(since: int, timeout: float = 10.0) -> bool:
    """Wait for new committed events without periodically opening a database."""
    if not isinstance(since,int) or since<0 or not 0<timeout<=20:
        raise ValueError("Invalid wait cursor or deadline")
    if bounds()["latest_sequence"]>since:
        return True
    until=time.monotonic()+timeout
    # Lock/condition order never conflicts with record(): record acquires
    # _EVENT_CHANGED only after closing _db and releasing _LOCK.
    with _EVENT_CHANGED:
        while True:
            remaining=until-time.monotonic()
            if remaining<=0:
                return bounds()["latest_sequence"]>since
            _EVENT_CHANGED.wait(timeout=remaining)
            if bounds()["latest_sequence"]>since:
                return True

def try_record(kind: str, **kwargs):
    """Best-effort observability NEVER prevents remote control from functioning."""
    try:
        return record(kind,**kwargs)
    except Exception:
        return None
