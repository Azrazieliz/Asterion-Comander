"""Temporary owner-signed APK delivery on the EXISTING private-LAN Control API.

Not a new file server, cloud relay, public feed, or broad download facility.
No credentials in the URL or on GitHub; only the already-paired Samsung's
current exact private IP may fetch this single SHA-pinned APK. The owner
Windows service can activate a short-lived availability marker locally.
The Android OS Package Installer still requires its normal user approval.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import time
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from .phone_bridge import load as registered_phone

router=APIRouter()
APK=Path("D:/AsterionControlV6M0_20261119/dist/Asterion-Control-v0.9.38-release.apk")
EXPECTED_SIZE=505163972
EXPECTED_SHA="31c10e86409c9183fa952c5079401eadddc879bed28f8f3c74c4f45de2440f7a"
NAME="Asterion-Control-v0.9.38-release.apk"
STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"/"owner-apk-delivery-v0938.enabled"
MAX_LIFETIME_S=900
_checked_fingerprint:tuple[int,int]|None=None

def file_verified()->Path:
    global _checked_fingerprint
    path=APK.resolve(strict=True)
    if path!=APK or not path.is_file() or path.is_symlink():
        raise HTTPException(503,"Pinned owner APK unavailable")
    stats=path.stat()
    if stats.st_size!=EXPECTED_SIZE:
        raise HTTPException(503,"Pinned APK size mismatch")
    identity=(stats.st_size,stats.st_mtime_ns)
    if _checked_fingerprint!=identity:
        digest=hashlib.sha256()
        with path.open("rb") as source:
            while chunk:=source.read(1024*1024):
                digest.update(chunk)
        if not hmac.compare_digest(digest.hexdigest(),EXPECTED_SHA):
            raise HTTPException(503,"Pinned APK checksum mismatch")
        _checked_fingerprint=identity
    return path

def paired_phone_only(request:Request)->None:
    # The original private Windows listener receives the Samsung's direct
    # LAN client, not a proxy: any X-Forwarded-For header is ignored.
    phone=registered_phone()
    if not phone or request.client is None:
        raise HTTPException(403,"No authenticated phone pairing")
    from urllib.parse import urlsplit
    expected=urlsplit(phone["base_url"]).hostname or ""
    try:
        address=ipaddress.ip_address(expected)
    except ValueError:
        raise HTTPException(403,"Unverifiable phone address")
    if not (address.is_private or address in ipaddress.ip_network("100.64.0.0/10")):
        raise HTTPException(403,"Phone is not on a private route")
    if not hmac.compare_digest(request.client.host.encode("utf8"),
                               expected.encode("utf8")):
        raise HTTPException(403,"Not the paired Samsung private-LAN address")

def active()->bool:
    try:
        value=STATE.read_text("ascii").strip()
        now=time.time()
        issued=float(value)
        return 0<=now-issued<=MAX_LIFETIME_S
    except (ValueError,OSError):
        return False

@router.get("/api/v1/owner-release/v0.9.38.apk",include_in_schema=False)
def exact_owner_release(request:Request):
    paired_phone_only(request)
    if not active():
        raise HTTPException(404,"Owner release delivery is not active")
    path=file_verified()
    return FileResponse(path,media_type="application/vnd.android.package-archive",
        filename=NAME,headers={"Cache-Control":"private, no-store",
            "X-Content-Type-Options":"nosniff",
            "X-Asterion-Pinned-SHA256":EXPECTED_SHA})
