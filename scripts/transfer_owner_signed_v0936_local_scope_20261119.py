"""Use EXISTING native Android Wi-Fi transfer engine for one owner-authorized APK.

The original public Windows REST API correctly limits arbitrary pc_path to C:
owner home. This dedicated Windows worker invocation does NOT relax that API
or open another endpoint: the allowed source is exactly the SHA-verified
owner-signed version 0.9.36 file in D: release-inbox, checked on every lookup.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx

from transfer_owner_signed_v0936_20261119 import (
    DEST, EXPECTED_SHA, EXPECTED_SIZE, record, stage, verify_apk,
)

PRODUCTION_ROOT=Path("D:/AsterionControlRelease")
if not PRODUCTION_ROOT.is_dir():
    raise RuntimeError("Original installed Windows Control worker not found")
sys.path.insert(0,str(PRODUCTION_ROOT))
from asterion_remote.native_transfer import (
    TransferRequest, start_transfer, transfer_status,
)


def approved_release_source(requested:str)->Path:
    path=Path(requested).expanduser().resolve(strict=True)
    exact=DEST.resolve(strict=True)
    if path!=exact or path.is_symlink():
        raise PermissionError("This command authorizes ONLY one signed release APK")
    if path.stat().st_size!=EXPECTED_SIZE:
        raise ValueError("Release APK changed size after verification")
    digest=hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda:file.read(4*1024*1024),b""):
            digest.update(chunk)
    if digest.hexdigest()!=EXPECTED_SHA:
        raise ValueError("Original-signer APK changed after verification")
    return path


def phone_guard():
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    base=(state/"agent-host.txt").read_text("utf8").strip()
    token=(state/"control-token.txt").read_text("utf8").strip()
    if not base.startswith("http://") or len(token)<32:
        raise RuntimeError("Original authenticated Control API unavailable")
    with httpx.Client(headers={"Authorization":"Bearer "+token},
                      trust_env=False,follow_redirects=False,timeout=12) as cli:
        response=cli.get(base+"/api/v1/phone/health")
        response.raise_for_status()
        status=response.json()
    net=status.get("remote_transport") or {}
    battery=status.get("battery") or {}
    temp=battery.get("temperature_c")
    if status.get("ok") is not True or net.get("network")!="wifi":
        raise RuntimeError("Original private Wi-Fi Android transfer is unavailable")
    if battery.get("charging") is not True and float(battery.get("percent") or 0)<20:
        raise RuntimeError("Battery below 20 percent and not charging")
    if isinstance(temp,(int,float)) and temp>45:
        raise RuntimeError("Phone battery temperature exceeds 45 degrees C")
    if int(status.get("storage_available") or 0)<2_000_000_000:
        raise RuntimeError("Insufficient actual Android storage")
    record("authorized_release_transfer_preflight",phone_network="wifi",
           phone_charging=bool(battery.get("charging")),
           phone_battery_percent=battery.get("percent"),
           phone_temperature_c=temp,
           source_bytes=EXPECTED_SIZE)
    return status


def transfer():
    verify_apk()
    stage()
    approved_release_source(str(DEST))
    phone_guard()
    request=TransferRequest(pc_path=str(DEST),name=DEST.name)
    # Reuses ORIGINAL production native_transfer._copy, including Android
    # commit-offset recovery, SHA256 verification and MediaStore receipt.
    # This local worker authorization is strictly narrower than the global
    # Windows REST safe_path policy, which remains unchanged.
    submission=start_transfer(request,approved_release_source)
    key=submission["id"]
    if not isinstance(key,str) or len(key)!=32:
        raise RuntimeError("Existing native transfer returned unexpected job ID")
    record("queued",transfer_id=key,source_bytes=EXPECTED_SIZE,
           original_transfer_engine=True)
    previous=-1
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        result=transfer_status(key)
        state=result.get("state","unknown")
        n=result.get("bytes_sent",0)
        if isinstance(n,int) and (n-previous>=20_000_000 or previous<0):
            previous=n
            record(state,transfer_id=key,bytes_sent=n,
                   expected_bytes=EXPECTED_SIZE)
        if state in ("completed","failed","cancelled","outcome_unknown"):
            break
        time.sleep(.8)
    else:
        raise RuntimeError("Native transfer did not reach a terminal state")
    receipt=result.get("result") or {}
    verified=(state=="completed" and receipt.get("verified") is True
              and receipt.get("sha256")==EXPECTED_SHA
              and receipt.get("size")==EXPECTED_SIZE)
    if not verified:
        record("not_accepted",transfer_id=key,worker_state=state,
               failure_class=str(result.get("error",""))[:100])
        raise RuntimeError("Genuine Android SHA256 receipt missing")
    record("verified_on_android",transfer_id=key,
           android_location=receipt.get("location"),
           android_uri=receipt.get("android_uri"),
           size_bytes=EXPECTED_SIZE,
           verified=True,installed=False,
           requires_android_package_installer_consent=True)
    return True


if __name__=="__main__":
    try:
        transfer()
    except Exception as error:
        record("blocked_or_failed",
               failure_type=type(error).__name__,
               failure_reason=str(error)[:200],
               installed=False)
        raise
