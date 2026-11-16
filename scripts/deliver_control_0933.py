"""Deliver a validated owner-signed v0.9.33 APK through the EXISTING native link.

File bytes move Windows -> paired Samsung over private network with SHA-256
receipt; this does not install, uninstall, reset or alter Android permissions.
"""
from __future__ import annotations
import hashlib
import ipaddress
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/"dist"/"Asterion-Control-v0.9.33-release.apk"

def main():
    if not PACKAGE.is_file():
        raise RuntimeError("owner_signed_candidate_apk_not_built")
    size=PACKAGE.stat().st_size
    if not 20000<size<300000000:
        raise RuntimeError("invalid_release_apk_size")
    digest=hashlib.sha256()
    with PACKAGE.open("rb") as file:
        while data:=file.read(1024*1024):
            digest.update(data)
    expected=digest.hexdigest()
    expected_manifest=(ROOT/"dist"/"SHA256SUMS-v0.9.33.txt").read_text("utf8")
    if not expected_manifest.startswith(expected+"  "+PACKAGE.name):
        raise RuntimeError("owner_signed_release_manifest_mismatch")
    state=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
    base=(state/"agent-host.txt").read_text("utf8").strip()
    token=(state/"control-token.txt").read_text("utf8").strip()
    parsed=urlsplit(base)
    ip=ipaddress.ip_address(parsed.hostname or "")
    if parsed.scheme!="http" or parsed.port!=8911 or not (
       ip.is_private or ip.is_loopback):
        raise RuntimeError("not_existing_private_control_endpoint")
    with httpx.Client(timeout=httpx.Timeout(20,connect=4),trust_env=False,
                      follow_redirects=False,
                      headers={"Authorization":"Bearer "+token}) as client:
        initiated=client.post(base+"/api/v1/phone/transfers",
            json={"pc_path":str(PACKAGE),"name":PACKAGE.name})
        initiated.raise_for_status()
        job=initiated.json()["id"]
        start=time.monotonic()
        response=None
        while time.monotonic()-start<180:
            time.sleep(.25)
            probe=client.get(base+"/api/v1/phone/transfers/"+job)
            probe.raise_for_status()
            response=probe.json()
            if response.get("state") in {"completed","failed","cancelled"}:
                break
        if response is None or response.get("state")!="completed":
            raise RuntimeError("android_transfer_not_completed")
        verified=response.get("result") or {}
        if verified.get("sha256")!=expected:
            raise RuntimeError("android_committed_sha256_mismatch")
        print(json.dumps({
            "ok":True,"file":PACKAGE.name,"bytes":size,"sha256":expected,
            "android_location":verified.get("location"),
            "wifi_transfer_state":"completed",
            "android_checksum_verified":True,
            "android_installed":False,
            "owner_installer_approval_required":True,
            "existing_pairing_preserved":True,
        },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
