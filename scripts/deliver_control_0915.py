"""Send the already-built native Asterion Control APK to Samsung without ADB.

The payload moves PC -> native Android agent on private Wi-Fi and is verified
using Android's committed SHA256 receipt. This does not silently install it:
Android package installation requires a user-approved APK installer.
"""
from __future__ import annotations
import hashlib,json,os,shutil,time
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
original=root/"dist"/"Asterion-Control-v0.9.15-release.apk"
assert original.is_file(),"Verified original-signer v0.9.15 release is missing"
destination=Path.home()/"Downloads"/"Asterion-Control-v0.9.15-release.apk"
destination.parent.mkdir(parents=True,exist_ok=True)
if destination.exists():
    if hashlib.sha256(destination.read_bytes()).digest()!=hashlib.sha256(original.read_bytes()).digest():
        raise RuntimeError("Destination occupied by another APK; refusing overwrite")
else:shutil.copy2(original,destination)
expected=hashlib.sha256(destination.read_bytes()).hexdigest()
if expected!="d7149dbac5c30cabcb8f34e3df6e15de9088cbef82ca047526f4c683aed7ced4":
    raise RuntimeError("Release checksum mismatch; aborting transfer")
key=(Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl" / "control-token.txt").read_text("utf-8").strip()
t0=time.perf_counter()
with httpx.Client(timeout=15,trust_env=False,follow_redirects=False,
                  headers={"Authorization":"Bearer "+key}) as c:
    url=(Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl" / "agent-host.txt").read_text("utf-8").strip()
    init=c.post(url+"/api/v1/phone/transfers",json={"pc_path":str(destination),
                                                    "name":destination.name})
    init.raise_for_status()
    transfer=init.json()["id"]
    for attempt in range(300):
        result=c.get(url+"/api/v1/phone/transfers/"+transfer)
        result.raise_for_status()
        data=result.json()
        if data["state"] in ("completed","failed","cancelled"):
            break
        time.sleep(.1)
    proof=data.get("result") or {}
    out={"state":data["state"],"source_bytes":destination.stat().st_size,
         "transferred":data.get("bytes_sent"),
         "elapsed_ms":round((time.perf_counter()-t0)*1000,1),
         "checksum_match":proof.get("sha256")==expected,
         "android_path":proof.get("location"),"transport":"direct private Wi-Fi",
         "error":data.get("error")}
    print(json.dumps(out,separators=(",",":")),flush=True)
    if data["state"]!="completed" or proof.get("sha256")!=expected:
        raise RuntimeError("Native Android APK delivery verification failed")
