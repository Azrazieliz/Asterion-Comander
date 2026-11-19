"""Acquire a SECOND, stronger *real* GGUF candidate for Android model testing.

The Qwen3-1.7B Q4_K_M is only staged (NOT silently bundled/deployed).
This preserves the already approved smaller default until actual on-phone
memory/speed/quality A/B tests select an acceptable signed release.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path
import httpx

from prepare_v6_native_inference_20261119 import ROOT, STAGE, verify_source

REPO="tauqir02/Qwen3-1.7B-GGUF"
NAME="Qwen3-1.7B-Q4_K_M.gguf"
EXPECTED=1282439552
SHA="b7a7dfc98e59b4ceb2abaa822c683ec9c2471ff4c54db7536eaa5008c38432af"
DEST=STAGE/"candidate_models"/NAME
PART=STAGE/"candidate_models"/(NAME+".partial")
REPORT=STAGE/"candidate_models"/"candidate_1p7b_report.json"
URL=f"https://huggingface.co/{REPO}/resolve/main/{NAME}"

def report(status,**data):
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    prior={}
    if REPORT.exists():
        try: prior=json.loads(REPORT.read_text("utf8"))
        except (ValueError,OSError): pass
    prior.update({"status":status,"updated_at":datetime.now(timezone.utc).isoformat(),**data})
    stage=REPORT.with_suffix(".new")
    stage.write_text(json.dumps(prior,sort_keys=True),encoding="utf8")
    stage.replace(REPORT)
    print(json.dumps({"status":status,**data},sort_keys=True),flush=True)

def sha_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for p in iter(lambda:f.read(4*1024*1024),b""):h.update(p)
    return h.hexdigest()

def main():
    verify_source()
    if DEST.exists() and DEST.stat().st_size==EXPECTED and sha_file(DEST)==SHA:
        report("verified",bytes=EXPECTED,sha256=SHA,already_present=True)
        return
    if PART.exists() and PART.stat().st_size>EXPECTED:
        raise RuntimeError("Invalid model staging length")
    offset=PART.stat().st_size if PART.exists() else 0
    headers={"User-Agent":"AsterionControlV6ModelLab/1.0"}
    if offset: headers["Range"]=f"bytes={offset}-"
    report("download_started",source=URL,bytes_received=offset,expected_bytes=EXPECTED)
    with httpx.Client(follow_redirects=True,timeout=httpx.Timeout(connect=25,read=100,write=100,pool=25)) as cli:
        with cli.stream("GET",URL,headers=headers) as response:
            response.raise_for_status()
            if offset and response.status_code==206:
                if not response.headers.get("Content-Range","").startswith(f"bytes {offset}-"):
                    raise RuntimeError("Unsafe resume: incorrect content range")
                mode="ab"
            elif offset and response.status_code==200:
                mode="wb";offset=0
            elif offset:raise RuntimeError("Model resume not accepted")
            else:mode="wb"
            seen=offset;previous=seen//(64*1024*1024)
            PART.parent.mkdir(parents=True,exist_ok=True)
            with PART.open(mode) as file:
                for chunk in response.iter_bytes(chunk_size=1024*1024):
                    if not chunk:continue
                    seen+=len(chunk)
                    if seen>EXPECTED:raise RuntimeError("Untrusted response exceeded expected size")
                    file.write(chunk)
                    checkpoint=seen//(64*1024*1024)
                    if checkpoint!=previous:
                        previous=checkpoint
                        report("downloading",bytes_received=seen,expected_bytes=EXPECTED)
                file.flush();os.fsync(file.fileno())
    if PART.stat().st_size!=EXPECTED:raise RuntimeError("Model incomplete")
    h=sha_file(PART)
    if h!=SHA:raise RuntimeError("Published model SHA256 mismatch")
    os.replace(PART,DEST)
    report("verified",bytes=DEST.stat().st_size,sha256=h,source=URL,
           approved_for_device_install=False,benchmark_required=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        report("failed",failure_class=type(exc).__name__,detail=str(exc)[:200])
        raise
