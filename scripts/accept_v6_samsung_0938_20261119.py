"""Read-only real-Samsung V6 acceptance, with optional one genuine AI job.

All observations use the already authenticated native WSS first. No pair reset,
Android permissions changes, package installs, VPN on/off commands, audio capture
or generic LAN fallback for the model. Never log prompts, outputs or secrets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asterion_remote import phone_bridge

def get(path:str)->dict:
    return phone_bridge.request(path,timeout=10.0).json()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--exercise-ai",action="store_true")
    args=parser.parse_args()
    evidence={"device_expected":"SM-S948B",
        "version_expected":"0.9.38","checked_at_unix_ms":round(time.time()*1000)}
    try:
        h=get("/health")
        evidence["phone"]={
            "device":h.get("device"),"android":h.get("android"),
            "version":h.get("control_version_name"),
            "version_code":h.get("control_version_code"),
            "expected_version_installed":h.get("control_version_name")=="0.9.38",
            "accessibility":h.get("accessible"),
            "battery_percent":(h.get("battery") or {}).get("percent"),
            "thermal_status":(h.get("thermals") or {}).get("status")}
    except Exception as exc:
        evidence["phone_error"]=type(exc).__name__
    try:
        evidence["wss"]=phone_bridge.probe_native_wss_roundtrip(timeout=8)
        evidence["network"]=get("/network/status")
    except Exception as exc:
        evidence["wss_error"]=type(exc).__name__
    try:
        a=phone_bridge.request_native_only("/ai/model/status",timeout=9).json()
        evidence["native_model"]={
            "bundled_real_gguf":a.get("model_bundled_in_apk"),
            "actual_native_library_loaded":a.get("native_library_loaded"),
            "model_ready":a.get("model_loaded"),
            "private_bytes":a.get("model_private_file_bytes"),
            "last_failure_code":a.get("last_failure_code"),
            "backend":a.get("inference_backend")}
    except Exception as exc:
        evidence["native_model_error"]=type(exc).__name__
    try:
        v=get("/voice/status")
        evidence["voice"]={k:v.get(k) for k in (
            "enabled","phase","always_listening_enabled",
            "ambient_recognizer_active","wake_word","recognized_wake_count",
            "ambient_recognizer_failures","recognizer_backend",
            "last_voice_dispatch")}
    except Exception as exc:
        evidence["voice_error"]=type(exc).__name__
    try:
        v=get("/diagnostics/vpn")
        evidence["vpn"]={k:v.get(k) for k in (
            "backend","active","state","configuration_present",
            "peer_reachability_verified","full_tunnel_owner_approved","error_code")}
    except Exception as exc:
        evidence["vpn_error"]=type(exc).__name__
    try:
        hist=get("/diagnostics/exit-history")
        evidence["recent_exits"]=[
            {"reason":x.get("reason_code"),"process":x.get("process"),
             "timestamp_ms":x.get("timestamp_ms")}
            for x in (hist.get("exits") or [])[:8]]
    except Exception as exc:
        evidence["exits_error"]=type(exc).__name__
    if args.exercise_ai and evidence.get("phone",{}).get("expected_version_installed"):
        id_="v6-0938-native-accept-"+str(round(time.time()))
        prompt="Respond using a single short sentence: what is 2 plus 2?"
        try:
            first=phone_bridge.request_native_only("/ai/jobs/submit","POST",
                {"request_id":id_,"prompt":prompt},timeout=10).json()
            state=first
            begin=time.monotonic()
            while time.monotonic()-begin<160:
                if state.get("state") in ("completed","failed","cancelled",
                                         "outcome_unknown"):break
                time.sleep(3)
                state=phone_bridge.request_native_only("/ai/jobs/status","POST",
                    {"request_id":id_},timeout=12).json()
            response=state.get("text") or ""
            evidence["ai_generation"]={
                "state":state.get("state"),"engine":state.get("engine"),
                "output_characters":len(response),
                "output_sha256":hashlib.sha256(response.encode("utf8")).hexdigest()
                    if response else "",
                "contains_arithmetic_answer":"4" in response,
                "latency_s":round(time.monotonic()-begin,2),
                "error_type":state.get("error_type")}
        except Exception as exc:
            evidence["ai_generation"]={"state":"unknown",
                                       "error_type":type(exc).__name__}
    print(json.dumps(evidence,sort_keys=True,separators=(",",":")))
    if evidence.get("phone",{}).get("device")!="SM-S948B":
        raise RuntimeError("No matching Samsung evidence")
    if args.exercise_ai and evidence.get("ai_generation",{}).get("state")!="completed":
        raise RuntimeError("Native model did not complete actual inference")
if __name__=="__main__":main()
