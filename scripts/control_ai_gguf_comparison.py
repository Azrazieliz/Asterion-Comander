"""Run licensed GGUF architecture and precision comparisons on the current CPU host.

The input revisions, byte identities, actual tensor representation, native executable
hashes and raw measurements travel with each report. Admission decisions describe
this process host only. No Android or accelerator performance is inferred.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

from scripts.control_ai_adaptation import file_hash
from scripts.control_ai_evidence_corpus import build

# Only public, identified upstream derivatives. Never load repository code.
CANDIDATES = {
    "olmo7": ("allenai/Olmo-3-7B-Think", "bartowski/allenai_Olmo-3-7B-Think-GGUF"),
    "granite8": ("ibm-granite/granite-3.3-8b-instruct", "ibm-granite/granite-3.3-8b-instruct-GGUF"),
    "nemo12": ("mistralai/Mistral-Nemo-Instruct-2407", "bartowski/Mistral-Nemo-Instruct-2407-GGUF"),
    "phi14": ("microsoft/Phi-4-reasoning-plus", "bartowski/microsoft_Phi-4-reasoning-plus-GGUF"),
    "olmo32": ("allenai/Olmo-3-32B-Think", "bartowski/allenai_Olmo-3-32B-Think-GGUF"),
    "granite-h": ("ibm-granite/granite-4.0-h-tiny", "ibm-granite/granite-4.0-h-tiny-GGUF"),
    "rwkv7": ("fla-hub/rwkv7-1.5B-world", "mradermacher/rwkv7-1.5B-world-GGUF"),
}
PINNED_RUNTIME = "4b77dee0524c64b8471869232e2958bd9589607d"


def files_for(siblings, precision):
    pattern = re.compile(r"[.-]" + precision + r"(?P<shard>-\d{5}-of-\d{5})?\.gguf$", re.I)
    files = sorted((x for x in siblings if pattern.search(x.rfilename)), key=lambda x: x.rfilename)
    if not files:
        return []
    singleton = [x for x in files if not pattern.search(x.rfilename).group("shard")]
    if singleton:
        if len(singleton) != 1:
            raise ValueError("ambiguous GGUF variant")
        return singleton
    expected = [f"-{i:05d}-of-{len(files):05d}" for i in range(1, len(files)+1)]
    if [pattern.search(x.rfilename).group("shard") for x in files] != expected:
        raise ValueError("incomplete GGUF shard set")
    return files


def tensor_info(paths):
    from gguf import GGUFReader
    rows = []
    for path in paths:
        reader = GGUFReader(path)
        for t in reader.tensors:
            rows.append({"name": t.name, "type": t.tensor_type.name,
                         "elements": int(t.n_elements), "bytes": int(t.n_bytes)})
        del reader
    total = sum(t["elements"] for t in rows)
    size = sum(t["bytes"] for t in rows)
    return {"parameters_stored": total, "tensor_bytes": size, "measured_bits_per_weight": 8*size/total,
            "tensors": rows}


def run_tool(args, output, label):
    import psutil
    started = time.monotonic()
    with (output/(label+".stdout")).open("w") as stdout, (output/(label+".stderr")).open("w") as stderr:
        proc = subprocess.Popen([str(v) for v in args], stdout=stdout, stderr=stderr)
        monitor = psutil.Process(proc.pid)
        peak = 0
        try:
            while proc.poll() is None:
                try:
                    peak = max(peak, monitor.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                if time.monotonic()-started > 420:
                    raise TimeoutError(label+" exceeded 420 seconds")
                time.sleep(0.05)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
    if proc.returncode:
        tail = (output/(label+".stderr")).read_text(errors="replace")[-1400:]
        raise RuntimeError(f"{label} exit {proc.returncode}: {tail}")
    return {"wall_s": time.monotonic()-started, "sampled_peak_rss_bytes":peak}


def measure(paths, binaries, out, label, corpus):
    bench = run_tool([binaries/"llama-bench","-m",paths[0],"-ngl","0","-p","64","-n","16",
                      "-t","4","-r","2","-o","json"], out, label+"-bench")
    values = json.loads((out/(label+"-bench.stdout")).read_text())
    if len(values) < 2 or any(v["avg_ts"] <= 0 for v in values):
        raise ValueError("missing native throughput measurement")
    likelihood = run_tool([binaries/"llama-perplexity","-m",paths[0],"-f",corpus,"-c","64","-b","64",
                           "-ub","64","-ngl","0","-t","4","--chunks","3"], out, label+"-likelihood")
    logs = "".join((out/(label+"-likelihood."+ext)).read_text(errors="replace") for ext in ("stdout","stderr"))
    hit = re.search(r"Final estimate: PPL = ([\d.]+)", logs)
    if not hit or not math.isfinite(float(hit.group(1))):
        raise ValueError("native perplexity unavailable")
    return {"bench": bench, "throughput": values, "likelihood": likelihood,
            "ppl": float(hit.group(1)), "file_bytes": sum(p.stat().st_size for p in paths),
            "sha256": {p.name:file_hash(p) for p in paths}, **tensor_info(paths)}


def mixed_types(tensors):
    # Preserve the output head and then attention projections nearest each end.
    # This is an explicit calibration hypothesis, not a blanket Q12 type.
    matrices = [t for t in tensors if t["name"].endswith(".weight") and t["type"] in ("F16","BF16")]
    def order(t):
        n=t["name"]
        return (0 if n=="output.weight" else 1 if ".attn_" in n else 2, n)
    target = sum(t["elements"] for t in tensors) * (12 - 8.5)/(16 - 8.5)
    retained, used = [], 0
    for t in sorted(matrices,key=order):
        if abs(target-used-t["elements"]) < abs(target-used):
            retained.append(t["name"])
            used += t["elements"]
    return retained


def run(args):
    from huggingface_hub import HfApi, hf_hub_download
    import psutil
    root=args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    api=HfApi(token=False)
    base_name, packed_name=CANDIDATES[args.candidate]
    base=api.model_info(base_name,revision=args.base_revision)
    hub=api.model_info(packed_name,revision=args.gguf_revision,files_metadata=True)
    licenses=[(m.card_data or {}).get("license") for m in (base,hub)]
    if any(x not in {"mit","apache-2.0"} for x in licenses if x) or not any(licenses):
        raise ValueError("public model license unavailable or outside this experiment")
    cache=root.parent/("input-"+args.candidate)
    base_config=Path(hf_hub_download(base_name,"config.json",revision=base.sha,token=False))
    config=json.loads(base_config.read_text())
    report={"candidate":args.candidate, "base_repo":base_name,"inspected_base_revision":base.sha,
        "converted_repo":packed_name,"gguf_revision":hub.sha,"licenses":licenses,
        "base_config":config, "base_config_sha256":file_hash(base_config),
        "host":platform.platform(),"runtime_revision":PINNED_RUNTIME,
        "tools_sha256":{n:file_hash(args.bin/n) for n in ("llama-bench","llama-perplexity","llama-quantize")},
        "device_verified":False,"profiles":{}}
    corpus=root/"workload.txt"
    corpus.write_text("\n".join(row["messages"][0]["content"] for row in build()[2])+"\n",encoding="utf-8")
    report["workload_sha256"]=file_hash(corpus)
    def checkpoint():
        (root/"comparison.json").write_text(json.dumps(report,indent=2)+"\n")
    def get_paths(files):
        result=[]
        for f in files:
            p=Path(hf_hub_download(packed_name,f.rfilename,revision=hub.sha,local_dir=cache,token=False))
            if p.stat().st_size!=f.size or file_hash(p)!=f.lfs.sha256:
                raise ValueError("downloaded model identity mismatch")
            result.append(p)
        return result
    high=files_for(hub.siblings,"bf16") or files_for(hub.siblings,"f16")
    q8=files_for(hub.siblings,"q8_0")
    for label,files in [("reference",high),("q8",q8)]:
        size=sum(f.size for f in files)
        available=psutil.virtual_memory().available
        disk=shutil.disk_usage(root).free
        profile={"state":"not_listed","available_ram_bytes":available,"available_disk_bytes":disk,
                 "planning_reserve_bytes":768<<20,"weights_bytes":size,
                 "source_files":{f.rfilename:f.lfs.sha256 for f in files}}
        report["profiles"][label]=profile
        if files:
            if size+(768<<20)>available or size+(512<<20)>disk:
                profile["state"]="outside_measured_host_budget"
            else:
                profile["state"]="running"
                checkpoint()
                paths=get_paths(files)
                profile.update(measure(paths,args.bin,root,label,corpus))
                profile["state"]="measured"
                # Only the compact recurrent lane keeps its reference for a mixed trial.
                if label!="reference" or args.candidate!="rwkv7":
                    for p in paths:p.unlink()
                gc.collect()
        checkpoint()
    if args.candidate=="rwkv7" and all(r["state"]=="measured" for r in report["profiles"].values()):
        high_paths=[cache/f.rfilename for f in high]
        retained=mixed_types(report["profiles"]["reference"]["tensors"])
        recipe=root/"retained-types.txt"
        recipe.write_text("\n".join(name+"=f16" for name in retained)+"\n")
        if not retained:raise ValueError("no high precision tensors selected")
        path=cache/"control-mixed.gguf"
        run_tool([args.bin/"llama-quantize","--tensor-type-file",recipe,high_paths[0],path,"Q8_0","4"],
                 root,"quantize")
        result=measure([path],args.bin,root,"mixed",corpus)
        result.update(state="measured",retained_f16=retained)
        report["profiles"]["mixed"]=result
        checkpoint()
    print({k:(v["state"],v.get("ppl"),v.get("measured_bits_per_weight")) for k,v in report["profiles"].items()})


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("candidate",choices=CANDIDATES)
    parser.add_argument("--base-revision",default="main")
    parser.add_argument("--gguf-revision",default="main")
    parser.add_argument("--bin",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    run(parser.parse_args())
