"""Build and smoke-benchmark a pinned local 3B GGUF using original llama.cpp.

Diagnostic only, in independent Windows D: staging. No model server, Android
install, signing, owner files, paid API, provider code or production promotion.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

PINNED_LLAMA="4b77dee0524c64b8471869232e2958bd9589607d"
MODEL_SHA="8334b850b7bd46238c16b0c550df2138f0889bf433809008cc17a8b05761863e"
MODEL_BYTES=1915305312
BENCH_PROMPT=("You are Asterion Control. Explain step by step why a software "
"task is NOT complete when a compiler exits 0 but the installed phone has "
"not been checked. List two independent evidence receipts needed. "
"Give a precise answer in fewer than 90 words.")
ROOT=Path(__file__).resolve().parents[1]


def sha_file(path):
    d=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(2*1024*1024),b""):
            d.update(b)
    return d.hexdigest()


def checked_command(argv,*,timeout,log):
    started=time.monotonic()
    with Path(log).open("a",encoding="utf-8") as handle:
        handle.write("\nCOMMAND "+json.dumps(argv)+"\n")
        handle.flush()
        with subprocess.Popen(argv,stdout=handle,stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL) as process:
            try:code=process.wait(timeout)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
                raise RuntimeError("bounded_model_build_or_inference_timeout")
    if code:raise RuntimeError("model_command_failed_"+str(code)+
                              "_log="+str(log))
    return time.monotonic()-started


def execute(llama_source,model_file,stage):
    llama=Path(llama_source).resolve(strict=True)
    model=Path(model_file).resolve(strict=True)
    stage=Path(stage).resolve()
    if "Candidates" not in str(stage) and "ModelBench" not in str(stage):
        raise ValueError("isolated_model_benchmark_stage_required")
    if stage.exists() and any(stage.iterdir()):
        # Existing build cache is acceptable only when it is our own stage.
        if not (stage/"control-model-benchmark-owned.txt").is_file():
            raise ValueError("unowned_build_stage_not_reused")
    stage.mkdir(parents=True,exist_ok=True)
    (stage/"control-model-benchmark-owned.txt").write_text(
        "ASTERION CONTROL ISOLATED NON-PRODUCTION MODEL BENCHMARK\n",encoding="utf-8")
    if shutil.disk_usage(stage).free<4_000_000_000:
        raise RuntimeError("insufficient_staging_disk_for_native_model_build")
    ref=subprocess.run(["git","-C",str(llama),"rev-parse","HEAD"],
        capture_output=True,text=True,check=True,timeout=30).stdout.strip()
    if ref!=PINNED_LLAMA:raise ValueError("unverified_inference_runtime_commit")
    if model.stat().st_size!=MODEL_BYTES or sha_file(model)!=MODEL_SHA:
        raise ValueError("unverified_gguf_candidate")
    log=stage/"benchmark.log"
    build=stage/"llama-cpu-build"
    configure=["cmake","-S",str(llama),"-B",str(build),
        "-G","Visual Studio 18 2026","-A","x64",
        "-DCMAKE_BUILD_TYPE=Release","-DGGML_NATIVE=OFF",
        "-DGGML_OPENMP=OFF","-DGGML_CUDA=OFF",
        "-DGGML_VULKAN=OFF","-DLLAMA_BUILD_TESTS=OFF",
        "-DLLAMA_BUILD_SERVER=OFF","-DLLAMA_BUILD_EXAMPLES=ON",
        "-DLLAMA_CURL=OFF"]
    build_times={}
    build_times["configure_s"]=round(checked_command(configure,timeout=360,log=log),2)
    build_times["compile_s"]=round(checked_command(
        ["cmake","--build",str(build),"--config","Release","--target",
         "llama-cli","--parallel","1"],timeout=2400,log=log),2)
    cli=list(build.rglob("llama-cli.exe"))
    if len(cli)!=1:raise RuntimeError("expected_one_compiled_llama_cli")
    output=stage/"inference-output.txt"
    started=time.monotonic()
    result=subprocess.run([str(cli[0]),"-m",str(model),"-p",BENCH_PROMPT,
        "-n","128","-c","2048","-t","2","--temp","0"],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,
        timeout=600,check=False)
    duration=round(time.monotonic()-started,2)
    stdout=result.stdout[-80000:];stderr=result.stderr[-40000:]
    # No local prompts or extracted user data stored: only original fixture above.
    output.write_bytes(stdout)
    evidence={"candidate_gguf_sha256":MODEL_SHA,"candidate_bytes":MODEL_BYTES,
        "runtime_commit":ref,"compile":build_times,
        "inference_exit_code":result.returncode,
        "wall_time_s":duration,"generated_output_sha256":hashlib.sha256(stdout).hexdigest(),
        "generated_output_preview":stdout.decode("utf-8","replace")[-1400:],
        "inference_diagnostic_tail":stderr.decode("utf-8","replace")[-1400:],
        "source_only":True,"android_device_tested":False,
        "model_trained":False,"production_replaced":False}
    (stage/"benchmark.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    if result.returncode:
        raise RuntimeError("llama_inference_failed_exit_"+str(result.returncode))
    return evidence


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--llama-source",required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--stage",required=True)
    args=p.parse_args()
    try:print(json.dumps(execute(args.llama_source,args.model,args.stage),indent=2))
    except Exception as exc:
        print(type(exc).__name__+": "+str(exc),file=sys.stderr)
        sys.exit(1)
