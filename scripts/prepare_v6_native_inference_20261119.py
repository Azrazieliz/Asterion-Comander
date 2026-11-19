"""Acquire REAL sha-pinned phone GGUF + pinned llama.cpp and build JNI ARM64.

Only acts in this isolated canonical Windows source checkout (D: stage).
Uses no new provider account, no credential, no signing-key access, and never
touches the original installed production phone or Windows release.
The weights are a fast baseline, NOT evidence of advanced reasoning quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BRANCH="work/control-0927-overnight-cycles-20261111"
HF_REPO="tauqir02/Qwen3-0.6B-GGUF"
FILENAME="Qwen3-0.6B-Q4_K_M.gguf"
MODEL_URL=f"https://huggingface.co/{HF_REPO}/resolve/main/{FILENAME}"
EXPECTED_LENGTH=484220288
EXPECTED_HASH="373db06783953f0981572d008f183eb2167b93304f5adbf7c4ce6ed6a91ee437"
LLAMA_GIT="https://github.com/ggml-org/llama.cpp.git"
# Both the GGUF publisher and Android source explicitly identify this revision.
LLAMA_REV="4b77dee"
STAGE=ROOT/"_v6_native_model_stage"
MODEL=ROOT/"android/app/src/main/assets/models"/FILENAME
JNI=ROOT/"android/app/src/main/jniLibs/arm64-v8a/libasterion_llm.so"
LLAMA=STAGE/"llama.cpp"
BUILD=STAGE/"android_arm64_build"
REPORT=STAGE/"acquisition_report.json"
LOG=STAGE/"native_build.log"


def emit(phase:str,**data) -> None:
    STAGE.mkdir(parents=True,exist_ok=True)
    old={}
    if REPORT.exists():
        try: old=json.loads(REPORT.read_text("utf8"))
        except (ValueError,OSError): old={}
    old.update({"phase":phase,"updated_at_utc":datetime.now(timezone.utc).isoformat(),**data})
    part=REPORT.with_suffix(".new")
    part.write_text(json.dumps(old,indent=2,sort_keys=True),encoding="utf8")
    part.replace(REPORT)
    print(json.dumps({"phase":phase,**data},sort_keys=True),flush=True)


def sha_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as fd:
        for chunk in iter(lambda:fd.read(2*1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source():
    if os.name!="nt" or ROOT.drive.upper()!="D:" or not (ROOT/".git").is_dir():
        raise RuntimeError("Must use existing isolated D: Windows Git worktree")
    res=subprocess.run(["git","-C",str(ROOT),"branch","--show-current"],
                       capture_output=True,text=True,check=True,timeout=20)
    if res.stdout.strip()!=BRANCH: raise RuntimeError("Wrong Asterion branch")
    origin=subprocess.run(["git","-C",str(ROOT),"remote","get-url","origin"],
                          capture_output=True,text=True,check=True,timeout=20).stdout.strip().lower()
    if not origin.endswith(("azrazieliz/asterion-comander.git","azrazieliz/asterion-comander")):
        raise RuntimeError("Original repo is not the approved Asterion Control source")
    if shutil.disk_usage(STAGE.parent).free<5_000_000_000:
        raise RuntimeError("Insufficient independent D: staging free space")


def model_download():
    if MODEL.is_file() and MODEL.stat().st_size==EXPECTED_LENGTH and sha_file(MODEL)==EXPECTED_HASH:
        emit("model_sha_verified",model_bytes=EXPECTED_LENGTH,model_sha256=EXPECTED_HASH,already_present=True)
        return
    import httpx
    MODEL.parent.mkdir(parents=True,exist_ok=True)
    incomplete=STAGE/(FILENAME+".partial")
    offset=incomplete.stat().st_size if incomplete.exists() else 0
    if offset>EXPECTED_LENGTH: raise RuntimeError("Invalid existing staging partial length")
    emit("model_download_started",model_repo=HF_REPO,bytes_existing=offset,expected_bytes=EXPECTED_LENGTH)
    headers={"User-Agent":"AsterionControlV6VerifiedWeightInstaller/1.0"}
    if offset: headers["Range"]=f"bytes={offset}-"
    with httpx.Client(follow_redirects=True,timeout=httpx.Timeout(connect=30,read=90,write=90,pool=30),trust_env=True) as cli:
        with cli.stream("GET",MODEL_URL,headers=headers) as response:
            response.raise_for_status()
            if offset and response.status_code==206:
                declared=response.headers.get("Content-Range","")
                if not declared.startswith(f"bytes {offset}-"):
                    raise RuntimeError("Unsafe resume: HTTP content range mismatch")
                mode="ab"
            elif offset and response.status_code==200:
                mode="wb"
                offset=0
            elif offset:
                raise RuntimeError("Resume rejected by origin")
            else: mode="wb"
            seen=offset
            last=seen//(32*1024*1024)
            with incomplete.open(mode) as out:
                for chunk in response.iter_bytes(chunk_size=1024*1024):
                    if not chunk:continue
                    out.write(chunk)
                    seen+=len(chunk)
                    if seen>EXPECTED_LENGTH:raise RuntimeError("Downloaded model exceeds verified expected size")
                    this=seen//(32*1024*1024)
                    if this!=last:
                        last=this
                        emit("model_downloading",model_bytes_received=seen,expected_bytes=EXPECTED_LENGTH)
                out.flush();os.fsync(out.fileno())
    if incomplete.stat().st_size!=EXPECTED_LENGTH:
        raise RuntimeError(f"Incomplete GGUF bytes={incomplete.stat().st_size}")
    actual=sha_file(incomplete)
    if actual!=EXPECTED_HASH:raise RuntimeError("GGUF upstream SHA256 mismatch: refusing use")
    os.replace(incomplete,MODEL)
    emit("model_sha_verified",model_bytes=MODEL.stat().st_size,model_sha256=actual,
         source=MODEL_URL,already_present=False)


def cmd(label:str,args:list[str],cwd:Path,timeout:int=900)->None:
    LOG.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    with LOG.open("a",encoding="utf8") as log:
        log.write("\n=== "+label+" ===\n")
        log.flush()
        with subprocess.Popen(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT) as process:
            try:code=process.wait(timeout)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
                raise RuntimeError(label+" exceeded bounded timeout")
    emit(label+"_complete",exit_code=code,elapsed_s=round(time.monotonic()-start,1))
    if code!=0:raise RuntimeError(label+f" exited {code}; inspect isolated build log")


def fetch_runtime():
    origin=LLAMA/"include/llama.h"
    exists=(LLAMA/".git").is_dir()
    if exists:
        git=["git","-C",str(LLAMA)]
        probe=subprocess.run(git+["rev-parse","HEAD"],capture_output=True,text=True,
                             timeout=20,check=False)
        actual=probe.stdout.strip() if probe.returncode==0 else ""
        if actual.startswith(LLAMA_REV) and origin.is_file():
            emit("runtime_sha_verified",llama_commit=actual,already_present=True)
            return
        if actual:
            raise RuntimeError("A different runtime commit already occupies the pinned checkout")
    else:
        LLAMA.parent.mkdir(parents=True,exist_ok=True)
        cmd("llama_git_init",["git","init",str(LLAMA)],ROOT,60)
        cmd("llama_git_remote",["git","-C",str(LLAMA),"remote","add","origin",LLAMA_GIT],ROOT,30)
    # git fetch cannot resolve a short SHA as a remote ref. Fetch an immutable
    # 40-digit commit ID independently confirmed against GitHub's commit API.
    import httpx
    response=httpx.get("https://api.github.com/repos/ggml-org/llama.cpp/commits/"+LLAMA_REV,
                      headers={"Accept":"application/vnd.github+json",
                               "User-Agent":"AsterionControlV6PinnedNativeBuild"},
                      timeout=25,follow_redirects=True)
    response.raise_for_status()
    full=response.json().get("sha","")
    if len(full)!=40 or not full.startswith(LLAMA_REV):
        raise RuntimeError("Pinned upstream llama.cpp revision cannot be authenticated")
    emit("runtime_fetch_started",source=LLAMA_GIT,requested_commit=full)
    cmd("llama_git_fetch",["git","-C",str(LLAMA),"fetch","--depth","1","origin",full],ROOT,900)
    cmd("llama_git_checkout",["git","-C",str(LLAMA),"checkout","--detach","FETCH_HEAD"],ROOT,60)
    actual=subprocess.run(["git","-C",str(LLAMA),"rev-parse","HEAD"],capture_output=True,
                          text=True,check=True,timeout=30).stdout.strip()
    if actual!=full:raise RuntimeError("Runtime pinned full commit mismatch")
    if not origin.is_file():raise RuntimeError("Actual llama.cpp header absent")
    emit("runtime_sha_verified",llama_commit=actual,source=LLAMA_GIT,already_present=False)


def find_sdk_exe():
    sdk=Path(os.environ.get("ANDROID_HOME",Path.home()/"AppData/Local/Android/Sdk"))
    ndkroot=sdk/"ndk"
    cmakeroot=sdk/"cmake"
    ndks=sorted((p for p in ndkroot.iterdir() if (p/"build/cmake/android.toolchain.cmake").is_file()),reverse=True)
    cmakes=sorted((p for p in cmakeroot.iterdir() if (p/"bin/cmake.exe").is_file() and (p/"bin/ninja.exe").is_file()),reverse=True)
    if not ndks or not cmakes:raise RuntimeError("Existing original Android SDK NDK/CMake toolchain missing")
    return ndks[0],cmakes[0]/"bin/cmake.exe",cmakes[0]/"bin/ninja.exe"


def build_native():
    if not MODEL.is_file() or MODEL.stat().st_size!=EXPECTED_LENGTH or sha_file(MODEL)!=EXPECTED_HASH:
        raise RuntimeError("Cannot compile/promote native runtime without authentic GGUF")
    if not (LLAMA/"include/llama.h").is_file():
        raise RuntimeError("Pinned llama.cpp source missing")
    gitsha=subprocess.run(["git","-C",str(LLAMA),"rev-parse","HEAD"],capture_output=True,text=True,check=True,timeout=20).stdout.strip()
    if not gitsha.startswith(LLAMA_REV):raise RuntimeError("Unpinned llama.cpp build rejected")
    ndk,cmake,ninja=find_sdk_exe()
    cmake_args=[str(cmake),"-S",str(ROOT/"android/app/src/main/cpp"),"-B",str(BUILD),
        "-G","Ninja","-DCMAKE_TOOLCHAIN_FILE="+str(ndk/"build/cmake/android.toolchain.cmake"),
        "-DANDROID_ABI=arm64-v8a","-DANDROID_PLATFORM=android-29",
        "-DANDROID_STL=c++_static","-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_MAKE_PROGRAM="+str(ninja),
        "-DLLAMA_SOURCE_DIR="+str(LLAMA),"-DGGML_NATIVE=OFF",
        "-DGGML_OPENMP=OFF","-DLLAMA_CURL=OFF","-DGGML_VULKAN=OFF"]
    emit("arm64_configuring",ndk=ndk.name,cmake=str(cmake),runtime_commit=gitsha)
    cmd("arm64_cmake_configure",cmake_args,ROOT,300)
    emit("arm64_compiling",ndk=ndk.name)
    cmd("arm64_cmake_build",[str(cmake),"--build",str(BUILD),"--config","Release",
        "--target","asterion_llm","--parallel","4"],ROOT,1800)
    so_candidates=list(BUILD.rglob("libasterion_llm.so"))
    if len(so_candidates)!=1:raise RuntimeError("Expected one actually compiled native JNI shared library")
    so=so_candidates[0]
    with so.open("rb") as f: header=f.read(64)
    if len(header)<64 or header[:4]!=b"\x7fELF" or header[4]!=2 or struct.unpack_from("<H",header,18)[0]!=183:
        raise RuntimeError("Native artifact is not a genuine Android ARM64 ELF")
    if so.stat().st_size<100000:raise RuntimeError("Native library too small for real inference")
    JNI.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(so,JNI)
    if sha_file(so)!=sha_file(JNI):raise RuntimeError("Native .so copy checksum mismatch")
    emit("native_arm64_elf_verified",jni_bytes=JNI.stat().st_size,jni_sha256=sha_file(JNI),
         llama_commit=gitsha,model_sha256=EXPECTED_HASH)
    return


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage",choices=["all","model","runtime","native"],default="all")
    option=p.parse_args()
    verify_source()
    try:
        if option.stage in ("all","model"):model_download()
        if option.stage in ("all","runtime"):fetch_runtime()
        if option.stage in ("all","native"):build_native()
        emit("complete",completed_stages=option.stage,model_verified=MODEL.exists() and
             MODEL.stat().st_size==EXPECTED_LENGTH if MODEL.exists() else False,
             native_present=JNI.is_file())
    except Exception as err:
        emit("failed",failure_type=type(err).__name__,failure_reason=str(err)[:320])
        raise


if __name__=="__main__":
    main()
