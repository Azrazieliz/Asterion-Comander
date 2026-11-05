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
original=root/"dist"/"Asterion-Control-v0.8.6-debug.apk"
assert original.is_file(),"Signed app release is missing"
destination=Path.home()/"Downloads"/"Asterion-Control-WiFi-Delivered-v0.8.6.apk"
destination.parent.mkdir(parents=True,exist_ok=True)
if destination.exists():
    if hashlib.sha256(destination.read_bytes()).digest()!=hashlib.sha256(original.read_bytes()).digest():
        raise RuntimeError("Destination occupied by another APK; refusing overwrite")
else:shutil.copy2(original,destination)
expected=hashlib.sha256(destination.read_bytes()).hexdigest()
key=(Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl" / "control-token.txt").read_text("utf-8").strip()
t0=time.perf_counter()
with httpx.Client(timeout=15,trust_env=False,follow_redirects=False,
                  headers={"Authorization":"Bearer "+key}) as c:
    url="http://192.168.1.133:8911"
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
