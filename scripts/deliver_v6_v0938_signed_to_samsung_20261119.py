"""Deliver the verified owner-signed APK using ORIGINAL Control private LAN transfer.

This is an explicit trusted Windows owner operation, NOT a generic file upload
API. Uses existing asterion_remote.native_transfer and its Android TransferStore
resume and SHA256 receipt. Do not install, uninstall, reset, re-pair or touch
any other application. The Android OS package installer must get owner approval.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from asterion_remote.native_transfer import (start_transfer,TransferRequest,
                                               transfer_status)
from fastapi import HTTPException

NAME="Asterion-Control-v0.9.38-release.apk"
APK=(ROOT/"dist"/NAME).resolve(strict=True)
SHA=(ROOT/"dist"/"SHA256SUMS-v0.9.38.txt").resolve(strict=True)
EXPECTED=(SHA.read_text("ascii").strip().split() or [""])[0].lower()
if len(EXPECTED)!=64 or any(c not in "0123456789abcdef" for c in EXPECTED):
    raise RuntimeError("Original signed build SHA256 receipt invalid")
if APK.name!=NAME or APK.stat().st_size<500_000_000 or APK.stat().st_size>700_000_000:
    raise RuntimeError("Unexpected source artifact, refusing transfer")
digest=hashlib.sha256()
with APK.open("rb") as file:
    for part in iter(lambda:file.read(1024*1024),b""):
        digest.update(part)
actual=digest.hexdigest()
if actual!=EXPECTED:
    raise RuntimeError("Signed release artifact digest mismatched")
def authorized_only_exact_release(requested:str)->Path:
    parsed=Path(requested).resolve(strict=True)
    if parsed!=APK or not parsed.is_file() or parsed.is_symlink():
        raise HTTPException(403,"Only this verified owner-signed APK is authorized")
    if parsed.stat().st_size!=APK.stat().st_size:
        raise HTTPException(409,"Signed APK changed during source authorization")
    return parsed
job=start_transfer(TransferRequest(pc_path=str(APK),name=NAME),
                   authorized_only_exact_release)
transfer_id=job["id"]
started=time.monotonic()
print(json.dumps({"state":"started","transport":"existing_private_wifi",
                  "sha256":EXPECTED,"bytes":APK.stat().st_size,
                  "id":transfer_id}),flush=True)
last_print=-1
while time.monotonic()-started<2400:
    result=transfer_status(transfer_id)
    state=result.get("state")
    sent=int(result.get("bytes_sent") or 0)
    total=int(result.get("size") or 0)
    done=int(100*sent/total) if total else 0
    if done//10!=last_print or state in ("completed","failed","cancelled","outcome_unknown"):
        print(json.dumps({"state":state,"percent":done,"sent_bytes":sent}),flush=True)
        last_print=done//10
    if state in ("completed","failed","cancelled","outcome_unknown"):
        break
    time.sleep(2)
else:
    raise RuntimeError("LAN transfer exceeded safe bounded owner session")
proof=result.get("result") or {}
completed=(result["state"]=="completed" and proof.get("sha256")==EXPECTED
           and proof.get("verified") is True
           and int(proof.get("size",-1))==APK.stat().st_size)
print(json.dumps({"state":result.get("state"),"verified":completed,
                  "sha256_matches_android":proof.get("sha256")==EXPECTED,
                  "bytes":sent,"android_location":proof.get("location"),
                  "elapsed_s":round(time.monotonic()-started,1),
                  "error_code":(result.get("error") or "").split(":",1)[0]}),flush=True)
if not completed:raise RuntimeError("Authenticated Android SHA receipt absent")
