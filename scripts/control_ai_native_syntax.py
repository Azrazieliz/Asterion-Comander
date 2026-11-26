"""Compile-check Control's current Android JNI inference implementation without APKs.

No model download, no signer or phone operations. Requires the previously
verified pinned llama.cpp checkout and existing Android NDK compiler.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_LLAMA_REV_PREFIX="4b77dee"


def run(llama_source: str, ndk_root: str) -> dict:
    llama=Path(llama_source).resolve(strict=True)
    ndk=Path(ndk_root).resolve(strict=True)
    source=ROOT/"android/app/src/main/cpp/on_device_llm.cpp"
    header=llama/"include/llama.h"
    ggml_header=llama/"ggml/include/ggml.h"
    compiler=ndk/"toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe"
    ndk_include=ndk/"toolchains/llvm/prebuilt/windows-x86_64/sysroot/usr/include"
    if not source.is_file() or not header.is_file() or not ggml_header.is_file() or not compiler.is_file():
        raise FileNotFoundError("original_native_source_or_pinned_llama_or_ndk_missing")
    commit=subprocess.run(["git","-C",str(llama),"rev-parse","HEAD"],
        capture_output=True,text=True,check=True,timeout=15).stdout.strip()
    if not re.fullmatch(r"[a-f0-9]{40}",commit) or not commit.startswith(EXPECTED_LLAMA_REV_PREFIX):
        raise ValueError("unexpected_llama_cpp_source_commit")
    argv=[str(compiler),"--target=aarch64-linux-android29",
          "-std=c++17","-fsyntax-only","-fno-exceptions",
          "-I"+str(llama/"include"),"-I"+str(llama/"ggml/include"),
          "-I"+str(ndk_include),
          str(source)]
    proc=subprocess.run(argv,capture_output=True,text=True,
        timeout=150,check=False)
    summary={"checked_source":str(source.relative_to(ROOT)),
        "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "llama_revision":commit,"compiler":compiler.name,
        "exit_code":proc.returncode,"diagnostic_tail":(proc.stdout+proc.stderr)[-3500:],
        "jni_source_compiled":False,"native_library_linked":False,
        "android_installed":False}
    if proc.returncode:
        raise RuntimeError(json.dumps(summary))
    summary["jni_source_compiled"]=True
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--llama-source",required=True)
    p.add_argument("--ndk",required=True)
    args=p.parse_args()
    try:print(json.dumps(run(args.llama_source,args.ndk),indent=2))
    except Exception as e:
        print(type(e).__name__+": "+str(e),file=sys.stderr)
        sys.exit(1)
