"""Read-only, redacted on-device incident/wake/VPN status via original WSS.

Never prints speech transcripts, saved credentials, usernames, app private data,
raw URL query strings or arbitrary log bodies. The original worker holds pairing.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from asterion_remote import phone_bridge

ROUTES=(
    "/voice/status",
    "/diagnostics/exit-history",
    "/diagnostics/logcat",
    "/diagnostics/vpn",
    "/network/status",
)
SAFE_VOICE={
    "enabled","phase","microphone_active","always_listening_enabled",
    "ambient_recognizer_active","wake_word","recognized_wake_count",
    "ambient_recognizer_failures","background_cpu_wake_held",
    "recognizer_backend","on_device_recognition",
    "android_system_recognition","updated_at_ms",
}
SAFE_VPN={
    "active","state","backend","configuration_present",
    "peer_reachability_verified","error_code",
}
SAFE_NET={"network","connected","validated","requires_home_wifi"}
LOG_PATTERNS={
    "fatal_exception": re.compile(r"FATAL EXCEPTION",re.I),
    "android_runtime": re.compile(r"AndroidRuntime",re.I),
    "anr": re.compile(r"\bANR\b|Application Not Responding",re.I),
    "native_crash": re.compile(r"SIGSEGV|SIGABRT|signal 11|signal 6",re.I),
    "webview_crash": re.compile(r"renderer process|RenderProcessGone",re.I),
    "low_memory": re.compile(r"low memory|OutOfMemoryError",re.I),
}
def redacted(route,value):
    if route=="/voice/status":
        return {k:value.get(k) for k in SAFE_VOICE if k in value}
    if route=="/diagnostics/vpn":
        return {k:value.get(k) for k in SAFE_VPN if k in value}
    if route=="/network/status":
        result={k:value.get(k) for k in SAFE_NET if k in value}
        link=value.get("direct_mcp") or {}
        result["native_wss_connected"]=link.get("connected") is True
        result["wss_phase"]=link.get("phase")
        return result
    if route=="/diagnostics/exit-history":
        return {"exits":[{
            "timestamp_ms":item.get("timestamp_ms"),
            "reason_code":item.get("reason_code"),
            "process":item.get("process"),
            "rss_kb":item.get("rss_kb"),
        } for item in value.get("exits",[])[:12] if isinstance(item,dict)]}
    # Logs may contain PII. ONLY output presence and count of safe categories.
    corpus=json.dumps(value,ensure_ascii=True)
    return {"logcat_scope":"own_process_only",
        "bytes_inspected":len(corpus),
        "signals":{name:len(expr.findall(corpus))
            for name,expr in LOG_PATTERNS.items()},
        "raw_logs_exported":False}

for route in ROUTES:
    try:
        response=phone_bridge.request(route,timeout=8)
        value=response.json()
        print(json.dumps({"route":route,"http_status":response.status_code,
            "redacted":redacted(route,value)},separators=(",",":")))
    except Exception as failure:
        print(json.dumps({"route":route,
            "error_type":type(failure).__name__},separators=(",",":")))
