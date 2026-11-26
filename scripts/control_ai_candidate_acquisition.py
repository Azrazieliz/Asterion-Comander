"""Staged, immutable-HF-revision GGUF acquisition for Control Model Lab.

Downloads only explicitly reviewed GGUF data; never executes model-repo code,
touches APK assets/production model storage, starts an AI server or deploys.
The owner-provided exact SHA/byte size must match. Interrupted partial files
are resumable only through verified HTTP byte ranges.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import urllib.request

REPO=re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REVISION=re.compile(r"^[0-9a-f]{40}$")
FILENAME=re.compile(r"^[A-Za-z0-9_.-]+\\.gguf$")
SHA=re.compile(r"^[0-9a-f]{64}$")
BLOCK=2*1024*1024


def digest(path):
    value=hashlib.sha256()
    with Path(path).open("rb") as src:
        while True:
            part=src.read(BLOCK)
            if not part:break
            value.update(part)
    return value.hexdigest()


def stage(*,repo,revision,filename,sha256,bytes_expected,output_dir):
    if not (REPO.fullmatch(repo) and REVISION.fullmatch(revision)
            and FILENAME.fullmatch(filename) and SHA.fullmatch(sha256)):
        raise ValueError("invalid_immutable_model_identity")
    if not isinstance(bytes_expected,int) or not 50_000_000<=bytes_expected<=8_000_000_000:
        raise ValueError("invalid_model_size")
    dest=Path(output_dir).expanduser().resolve()
    if "candidates" not in dest.name.casefold() and not any(
            "candidates" in p.name.casefold() for p in dest.parents):
        raise ValueError("isolated_candidate_root_required")
    dest.mkdir(parents=True,exist_ok=True)
    final=dest/filename
    partial=dest/(filename+".partial")
    for path in (final,partial):
        if path.is_symlink():
            raise ValueError("symlink_candidate_forbidden")
    if final.exists():
        if final.stat().st_size!=bytes_expected or digest(final)!=sha256:
            raise ValueError("existing_candidate_checksum_conflict")
        return {"verified":True,"downloaded":False,"sha256":sha256,
                "bytes":bytes_expected,"candidate_path":str(final),
                "released":False,"device_verified":False}
    offset=partial.stat().st_size if partial.exists() else 0
    if offset>bytes_expected:
        raise ValueError("partial_larger_than_expected")
    remaining=bytes_expected-offset
    if shutil.disk_usage(dest).free<remaining+256*1024*1024:
        raise RuntimeError("insufficient_disk_for_immutable_candidate")
    url=("https://huggingface.co/"+repo+"/resolve/"+revision+"/"+
         filename+"?download=true")
    headers={"User-Agent":"Asterion-Control-ModelLab/1.0",
             "Accept-Encoding":"identity"}
    if offset:
        headers["Range"]=f"bytes={offset}-"
    request=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(request,timeout=40) as response:
        if response.url.startswith("http://"):
            raise ValueError("insecure_hf_redirect")
        status=getattr(response,"status",None)
        if offset and status==206:
            if not response.headers.get("Content-Range","").startswith(
                    f"bytes {offset}-"):
                raise RuntimeError("invalid_resume_range")
            mode="ab"
        elif status==200:
            mode="wb"  # server ignored Range: restart OWN partial from first byte
            offset=0
        else:
            raise RuntimeError("unsupported_model_http_response")
        total=offset
        with partial.open(mode) as out:
            while True:
                block=response.read(BLOCK)
                if not block:break
                total+=len(block)
                if total>bytes_expected:
                    raise ValueError("candidate_download_exceeded_pinned_size")
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
    if partial.stat().st_size!=bytes_expected:
        raise RuntimeError("incomplete_candidate_download_retained_for_resume")
    actual=digest(partial)
    if actual!=sha256:
        raise ValueError("candidate_sha256_mismatch_partial_quarantined")
    os.replace(partial,final)
    evidence={"schema_version":1,"repo":repo,"revision":revision,
              "filename":filename,"sha256":actual,"bytes":bytes_expected,
              "candidate_path":str(final),"evaluated":False,
              "released":False,"device_verified":False,
              "production_replaced":False,"weight_adapted":False}
    manifest=dest/(filename+".candidate.json")
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8"))!=evidence:
            raise ValueError("candidate_metadata_conflict")
    else:
        with manifest.open("x",encoding="utf-8") as out:
            json.dump(evidence,out,indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
    return {"verified":True,"downloaded":True,**evidence}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--revision",required=True)
    p.add_argument("--filename",required=True)
    p.add_argument("--sha256",required=True)
    p.add_argument("--bytes",type=int,required=True)
    p.add_argument("--output-dir",required=True)
    args=p.parse_args()
    print(json.dumps(stage(repo=args.repo,revision=args.revision,
        filename=args.filename,sha256=args.sha256,bytes_expected=args.bytes,
        output_dir=args.output_dir),indent=2))


if __name__=="__main__":
    main()
