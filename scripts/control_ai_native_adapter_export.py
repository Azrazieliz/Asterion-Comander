"""Convert a completed, hash-verified PEFT adapter for the existing native runtime.

Conversion is not model qualification. A native base GGUF must subsequently
be bound by exact digest and independently evaluated before signed release.
No downloads, secrets, remote code, or production profile updates.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from scripts.control_ai_adaptation import file_hash

PINNED_RUNTIME="4b77dee0524c64b8471869232e2958bd9589607d"
SHA=re.compile(r"[a-f0-9]{64}")

def verified_file(root,name,expected):
    if not isinstance(name,str) or not isinstance(expected,str) or not SHA.fullmatch(expected):
        raise ValueError("invalid_artifact_identity")
    root=root.resolve(strict=True)
    file=(root/name).resolve(strict=True)
    if not file.is_relative_to(root) or not file.is_file() or file_hash(file)!=expected:
        raise ValueError("artifact_digest_mismatch")
    return file

def admit(candidate,base):
    candidate=Path(candidate).resolve(strict=True)
    base=Path(base).resolve(strict=True)
    manifest_path=candidate/"candidate.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("weights_changed") is not True or manifest.get("adapter_only") is not True:
        raise ValueError("completed_changed_adapter_required")
    before=manifest.get("trainable_sha256_before","")
    after=manifest.get("trainable_sha256_after","")
    if not SHA.fullmatch(before) or not SHA.fullmatch(after) or before==after:
        raise ValueError("invalid_training_weight_lineage")
    revision=manifest.get("base_revision_declared","")
    if not re.fullmatch(r"[a-f0-9]{40,64}",revision):
        raise ValueError("immutable_base_revision_required")
    artifacts=manifest["artifact_sha256"]
    for required in ("adapter/adapter_model.safetensors","adapter/adapter_config.json"):
        if required not in artifacts:raise ValueError("missing_adapter_artifact")
    for name,digest in artifacts.items():
        if not name.startswith("adapter/"):raise ValueError("invalid_adapter_path")
        verified_file(candidate,name,digest)
    base_hashes=manifest["base_files_sha256"]
    verified_file(base,"config.json",base_hashes["config.json"])
    # The converter needs the exact training architecture metadata, not
    # another release of a similarly named foundation.
    for name,digest in base_hashes.items():
        if not name.endswith(".safetensors"):
            verified_file(base,name,digest)
    config=json.loads((candidate/"adapter/adapter_config.json").read_text(encoding="utf-8"))
    if config.get("peft_type")!="LORA" or config.get("bias","none")!="none":
        raise ValueError("unsupported_adapter_type")
    return {"training_record_sha256":file_hash(manifest_path),
            "training_base_revision":revision,
            "training_base_config_sha256":base_hashes["config.json"],
            "peft_adapter_sha256":artifacts["adapter/adapter_model.safetensors"],
            "peft_config_sha256":artifacts["adapter/adapter_config.json"]}

def export(candidate,base,runtime,out):
    evidence=admit(candidate,base)
    runtime=Path(runtime).resolve(strict=True)
    revision=subprocess.check_output(["git","-C",str(runtime),"rev-parse","HEAD"],text=True).strip()
    if revision!=PINNED_RUNTIME:raise ValueError("converter_runtime_revision_mismatch")
    if subprocess.check_output(["git","-C",str(runtime),"status","--porcelain","--untracked-files=all"],text=True).strip():
        raise ValueError("converter_checkout_not_clean")
    out=Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    artifact=out/"control-adapter-f16.gguf"
    env=dict(os.environ,HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
    subprocess.run([sys.executable,str(runtime/"convert_lora_to_gguf.py"),
        "--base",str(Path(base).resolve()),"--outtype","f16","--outfile",str(artifact),
        str(Path(candidate).resolve()/"adapter")],cwd=runtime,env=env,check=True)
    with artifact.open("rb") as stream:
        if stream.read(4)!=b"GGUF":raise ValueError("invalid_native_adapter_header")
    if artifact.stat().st_size<=32:raise ValueError("empty_native_adapter")
    evidence.update({"state":"converted_unqualified","converter_revision":revision,
        "adapter_file":artifact.name,"adapter_bytes":artifact.stat().st_size,
        "adapter_sha256":file_hash(artifact),"precision":"F16",
        "compatible_base_gguf_sha256":None,"native_inference_verified":False,
        "device_verified":False,"production_promoted":False})
    (out/"native-adapter.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(evidence,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True,type=Path)
    p.add_argument("--base",required=True,type=Path)
    p.add_argument("--runtime",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    export(a.candidate,a.base,a.runtime,a.output)
