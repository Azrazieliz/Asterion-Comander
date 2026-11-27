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
import shutil
import tempfile
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

def canonical_paths(mapping):
    """Support prior Windows records without allowing ambiguous aliases."""
    if not isinstance(mapping,dict):raise ValueError("invalid_artifact_inventory")
    result={}
    for name,digest in mapping.items():
        name=name.replace("\\","/")
        parts=name.split("/")
        if any(part in ("",".","..") or ":" in part for part in parts) or name in result:
            raise ValueError("ambiguous_or_invalid_artifact_path")
        result[name]=digest
    return result

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
    artifacts=canonical_paths(manifest["artifact_sha256"])
    for required in ("adapter/adapter_model.safetensors","adapter/adapter_config.json"):
        if required not in artifacts:raise ValueError("missing_adapter_artifact")
    for name,digest in artifacts.items():
        if not name.startswith("adapter/"):raise ValueError("invalid_adapter_path")
        verified_file(candidate,name,digest)
    base_hashes=canonical_paths(manifest["base_files_sha256"])
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
    # PEFT A/B matrices are floating-point tensors even when the frozen
    # training foundation was NF4. The upstream adapter-only converter also
    # calls its full-model dequantizer when quantization_config is present.
    # Preserve the admitted source metadata and remove ONLY the verified NF4
    # storage descriptor from an isolated converter-only copy. No foundation
    # weights are converted, modified, or represented as a matched GGUF.
    with tempfile.TemporaryDirectory(prefix="control-lora-converter-") as directory:
        source=Path(base).resolve(strict=True)
        config=json.loads((source/"config.json").read_text(encoding="utf-8"))
        quant=config.get("quantization_config")
        converter_base=source
        if quant is not None:
            if (not isinstance(quant,dict) or quant.get("quant_method")!="bitsandbytes" or
                quant.get("bnb_4bit_quant_type")!="nf4" or
                not quant.get("load_in_4bit",quant.get("_load_in_4bit",False))):
                raise ValueError("unsupported_adapter_training_quantization")
            converter_base=Path(directory)
            manifest=json.loads((Path(candidate)/"candidate.json").read_text(encoding="utf-8"))
            for name,digest in canonical_paths(manifest["base_files_sha256"]).items():
                if name.endswith(".safetensors"):continue
                verified=verified_file(source,name,digest)
                target=converter_base/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(verified,target)
            config.pop("quantization_config")
            (converter_base/"config.json").write_text(json.dumps(config,sort_keys=True,indent=2)+"\n",encoding="utf-8")
            evidence.update(converter_metadata_sha256=file_hash(converter_base/"config.json"),
                converter_removed_storage_descriptor="bitsandbytes_nf4",source_config_preserved=True,
                foundation_weights_converted=False)
        subprocess.run([sys.executable,str(runtime/"convert_lora_to_gguf.py"),
            "--base",str(converter_base),"--outtype","f16","--outfile",str(artifact),
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
