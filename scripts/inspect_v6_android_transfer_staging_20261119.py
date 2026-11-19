"""Non-destructive probe for the 505 MB APK that failed at MediaStore publish.

Calls the existing Android idempotent /transfer/start for the same exact signed
APK identity. NEVER sends file bytes, cancels a transfer or opens an installer.
Only returns accepted identity/resume bytes, not bearer, host or raw errors.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asterion_remote.phone_bridge import load
NAME="Asterion-Control-v0.9.38-release.apk"
EXPECTED="31c10e86409c9183fa952c5079401eadddc879bed28f8f3c74c4f45de2440f7a"
SIZE=505163972
paired=load()
if not paired:raise RuntimeError("Private original Samsung pairing unavailable")
with httpx.Client(timeout=httpx.Timeout(12,connect=5),trust_env=False,
                  follow_redirects=False) as client:
    r=client.post(paired["base_url"]+"/transfer/start",
       json={"name":NAME,"size":SIZE,"sha256":EXPECTED},
       headers={"Authorization":"Bearer "+paired["token"]})
    if r.status_code!=200:
        print(json.dumps({"http_status":r.status_code,"android_refused":True,
                          "body_type":"json" if r.headers.get("content-type","").startswith("application/json") else "other"}))
        raise RuntimeError("Real Android transfer ledger read failed")
    j=r.json()
    safe={"id":j.get("id"),"resumed":j.get("resumed"),
          "received":j.get("received"),"expected_bytes":SIZE,
          "matches_exact_sha":j.get("sha256")==EXPECTED,
          "full_staging_present":j.get("received")==SIZE,
          "safe_to_retry_finish":j.get("received")==SIZE and j.get("resumed") is True
              and j.get("sha256")==EXPECTED}
    print(json.dumps(safe,separators=(",",":")))
    if not safe["matches_exact_sha"]:raise RuntimeError("Wrong Android transfer identity")
