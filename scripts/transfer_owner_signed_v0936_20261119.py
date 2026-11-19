"""M13: transfer actual ORIGINAL-SIGNER Control 0.9.36 APK to paired Samsung.

File content goes strictly through existing Windows/Android native transfer API
on private LAN; the fallback GitHub bridge only carries this CONTROL command.
Never uploads APK bytes to GitHub, never uninstalls, re-signs, wipes Android,
changes pairing, installs without Android OS approval, or overwrites a different
owner artifact. End-to-end Android SHA256 receipt is mandatory.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"dist/Asterion-Control-v0.9.36-release.apk"
DEST=Path("D:/AsterionControlRelease/release-inbox/Asterion-Control-v0.9.36-release.apk")
REPORT=ROOT/"V6_SIGNED_PHONE_TRANSFER_20261119.json"
EXPECTED_SIZE=505146596
EXPECTED_SHA="dc4dc4537f0ef5965740c293f9cd3b6643731a91c7f4d6e95dcc5e2ae3d741a4"
EXPECTED_CERT="9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad"

def digest(path:Path):
    sha=hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda:file.read(4*1024*1024),b""):
            sha.update(chunk)
    return sha.hexdigest()

def record(state,**details):
    body={"state":state,"reported_unix_s":time.time(),
          "sha256":EXPECTED_SHA,"version_code":936,
          "owner_signer_preserved":True,**details}
    REPORT.write_text(json.dumps(body,indent=2,sort_keys=True),encoding="utf8")
    print(json.dumps(body,separators=(",",":")),flush=True)

def verify_apk():
    if os.name!="nt" or not SOURCE.is_file():
        raise RuntimeError("Original Windows signed release artifact unavailable")
    if SOURCE.stat().st_size!=EXPECTED_SIZE or digest(SOURCE)!=EXPECTED_SHA:
        raise RuntimeError("Actual original signed source APK hash/size mismatch")
    bt=Path(os.environ["LOCALAPPDATA"])/"Android/Sdk/build-tools"
    signer=None
    for ver in ("35.0.1","35.0.0","36.1.0","34.0.0"):
        candidate=bt/ver/"apksigner.bat"
        if candidate.is_file():signer=candidate;break
    if signer is None:raise RuntimeError("Original SDK signature verifier missing")
    result=subprocess.run([str(signer),"verify","--print-certs",str(SOURCE)],
        check=True,capture_output=True,text=True,timeout=90)
    certificate=""
    for row in result.stdout.splitlines():
        if row.startswith("Signer #1 certificate SHA-256 digest:"):
            certificate=row.split(":",1)[1].strip().lower()
    if certificate!=EXPECTED_CERT:raise RuntimeError("Owner signing certificate mismatch")
    manifest=ROOT/"dist/SHA256SUMS-v0.9.36.txt"
    if not manifest.is_file() or EXPECTED_SHA not in manifest.read_text("utf8"):
        raise RuntimeError("Release hash manifest unavailable")
    return certificate

def stage():
    DEST.parent.mkdir(parents=True,exist_ok=True)
    if DEST.is_file():
        if DEST.stat().st_size!=EXPECTED_SIZE or digest(DEST)!=EXPECTED_SHA:
            raise RuntimeError("Existing owner release inbox file differs; no overwrite")
        return
    tmp=DEST.with_suffix(".partial")
    if tmp.exists():raise RuntimeError("Existing partial release inbox file; no overwrite")
    with SOURCE.open("rb") as incoming,tmp.open("xb") as outgoing:
        shutil.copyfileobj(incoming,outgoing,length=2*1024*1024)
        outgoing.flush();os.fsync(outgoing.fileno())
    if tmp.stat().st_size!=EXPECTED_SIZE or digest(tmp)!=EXPECTED_SHA:
        raise RuntimeError("Owner release inbox staging checksum mismatch")
    tmp.replace(DEST)

def live_transfer():
    app=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    base=(app/"agent-host.txt").read_text("utf8").strip()
    token=(app/"control-token.txt").read_text("utf8").strip()
    if len(token)<32 or not base.startswith("http://"):
        raise RuntimeError("Original owner Windows Control API authorization missing")
    headers={"Authorization":"Bearer "+token}
    with httpx.Client(headers=headers,trust_env=False,follow_redirects=False,
                      timeout=httpx.Timeout(20,connect=6)) as client:
        phone=client.get(base+"/api/v1/phone/health")
        phone.raise_for_status()
        status=phone.json()
        net=status.get("remote_transport") or {}
        if not status.get("ok") or net.get("network")!="wifi":
            raise RuntimeError("Existing private Wi-Fi transfer transport not available")
        battery=status.get("battery") or {}
        temp=battery.get("temperature_c")
        if not battery.get("charging") and float(battery.get("percent",0))<20:
            raise RuntimeError("Samsung battery low and not charging; no long transfer")
        if isinstance(temp,(float,int)) and temp>45:
            raise RuntimeError("Samsung battery over 45 C; no long transfer")
        if int(status.get("storage_available",0))<2_000_000_000:
            raise RuntimeError("Samsung has insufficient free storage")
        record("validated_source_and_phone",
               size_bytes=EXPECTED_SIZE,
               phone_network="wifi",phone_charging=bool(battery.get("charging")),
               battery_percent=battery.get("percent"),phone_temperature_c=temp)
        submitted=client.post(base+"/api/v1/phone/transfers",
            json={"pc_path":str(DEST),"name":DEST.name})
        submitted.raise_for_status()
        task=submitted.json()
        key=task["id"]
        if not isinstance(key,str) or len(key)>80:
            raise RuntimeError("Invalid original Control transfer receipt")
        record("transfer_submitted",task_id=key)
        deadline=time.monotonic()+1200
        previous=-1
        while time.monotonic()<deadline:
            result=client.get(base+"/api/v1/phone/transfers/"+key)
            result.raise_for_status()
            row=result.json()
            n=row.get("bytes_sent",0)
            if isinstance(n,int) and (n-previous>25_000_000 or previous<0):
                previous=n
                record(row.get("state","unknown"),task_id=key,bytes_sent=n,
                       size_bytes=row.get("size",0))
            if row.get("state") in ("completed","failed","cancelled","outcome_unknown"):
                break
            time.sleep(.8)
        else:
            raise RuntimeError("Transfer completion not observed in bounded window")
        proof=row.get("result") or {}
        complete=row.get("state")=="completed" and proof.get("verified") is True and \
                 proof.get("sha256")==EXPECTED_SHA and proof.get("size")==EXPECTED_SIZE
        if not complete:
            record("failed_or_unverified",task_id=key,
                   worker_state=row.get("state"),error_code=str(row.get("error"))[:150])
            raise RuntimeError("Android committed SHA256 and size receipt missing")
        record("verified_on_android",task_id=key,
               size_bytes=EXPECTED_SIZE,
               android_uri=proof.get("android_uri"),
               android_path=proof.get("location"),
               install_requested=False,installed=False,
               android_system_install_permission_required=True)
        return True

if __name__=="__main__":
    try:
        verify_apk()
        stage()
        live_transfer()
    except Exception as error:
        record("blocked_or_failed",failure_type=type(error).__name__,
               failure_reason=str(error)[:200],
               installed=False)
        raise
