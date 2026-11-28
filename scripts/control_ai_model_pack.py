"""Build a native candidate pack locally on the approved model-storage drive.

Uses the pinned original base and existing llama.cpp converter; no model
promotion, APK signing, paid service or large artifact upload is performed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from scripts.control_ai_adaptation import file_hash
from scripts.control_ai_native_adapter_export import PINNED_RUNTIME, verified_file
from scripts.control_ai_retained_candidate import ORIGINAL_MODEL, ORIGINAL_REVISION, REVISION

PART_BYTES=1024**3
ARCH_FIELDS=("architectures","model_type","hidden_size","intermediate_size","num_hidden_layers",
    "num_attention_heads","num_key_value_heads","head_dim","vocab_size","max_position_embeddings",
    "rope_theta","rope_scaling","sliding_window","layer_types","tie_word_embeddings","hidden_act",
    "attention_bias","rms_norm_eps")

def write_json(path,value):
    with path.open("x",encoding="utf-8") as f:json.dump(value,f,indent=2);f.write("\n")

def compatible_adapter(base,adapter):
    from gguf import GGUFReader
    b=GGUFReader(str(base))
    a=GGUFReader(str(adapter))
    targets={t.name:tuple(int(v) for v in t.shape) for t in b.tensors}
    pairs={}
    for t in a.tensors:
        name=t.name
        if name.endswith(".lora_a"):target,side=name[:-7],"a"
        elif name.endswith(".lora_b"):target,side=name[:-7],"b"
        else:raise ValueError("unexpected_native_adapter_tensor")
        if t.tensor_type.name not in {"F16","F32","BF16"}:raise ValueError("unexpected_native_adapter_precision")
        pair=pairs.setdefault(target,{})
        if side in pair:raise ValueError("duplicate_native_adapter_tensor")
        pair[side]=tuple(int(v) for v in t.shape)
    if not pairs:raise ValueError("empty_native_adapter")
    for name,pair in pairs.items():
        shape=targets.get(name)
        if shape is None or len(shape)!=2 or set(pair)!={"a","b"}:raise ValueError("native_adapter_target_missing:"+name)
        av,bv=pair["a"],pair["b"]
        if len(av)!=2 or len(bv)!=2 or av[0]!=shape[0] or bv[1]!=shape[1] or av[1]!=bv[0]:
            raise ValueError("native_adapter_tensor_shape_mismatch:"+name)
    return len(pairs)

def split_file(source,destination,expected):
    """Produce existing-transfer-compatible 1 GiB parts without changing source."""
    source=Path(source)
    if file_hash(source)!=expected:raise ValueError("model_source_digest_mismatch")
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    parts=[]
    total=0
    whole=hashlib.sha256()
    try:
        with source.open("rb") as stream:
            for index in range(1,33):
                part=destination/(source.name+f".part{index:04d}")
                first=stream.read(1024*1024)
                if not first:break
                part_hash=hashlib.sha256();size=0
                with part.open("xb") as target:
                    chunk=first
                    while chunk:
                        target.write(chunk);part_hash.update(chunk);whole.update(chunk)
                        size+=len(chunk);total+=len(chunk)
                        if size==PART_BYTES:break
                        chunk=stream.read(min(1024*1024,PART_BYTES-size))
                    target.flush();os.fsync(target.fileno())
                parts.append({"file":part.name,"bytes":size,"sha256":part_hash.hexdigest()})
            if stream.read(1):raise ValueError("model_part_limit_exceeded")
        if total!=source.stat().st_size or whole.hexdigest()!=expected:raise ValueError("model_split_integrity_failed")
        write_json(destination/"parts.json",{"file":source.name,"bytes":total,"sha256":expected,"parts":parts})
    except BaseException:
        shutil.rmtree(destination)
        raise
    return parts

def build(root,runtime,training_metadata,native_adapter,precision="q8_0",quantizer=None):
    from huggingface_hub import HfApi,snapshot_download
    root=Path(root).resolve()
    root.mkdir(parents=True,exist_ok=False)
    runtime=Path(runtime).resolve(strict=True)
    revision=subprocess.check_output(["git","-C",str(runtime),"rev-parse","HEAD"],text=True).strip()
    if revision!=PINNED_RUNTIME or subprocess.check_output(["git","-C",str(runtime),"status","--porcelain"],text=True).strip():
        raise ValueError("native_converter_checkout_mismatch")
    native_adapter=Path(native_adapter).resolve(strict=True)
    adapter_manifest=json.loads((native_adapter/"native-adapter.json").read_text())
    if adapter_manifest.get("training_base_revision")!=REVISION or adapter_manifest.get("converter_revision")!=PINNED_RUNTIME:
        raise ValueError("native_adapter_lineage_mismatch")
    adapter=verified_file(native_adapter,adapter_manifest["adapter_file"],adapter_manifest["adapter_sha256"])
    training_config=verified_file(Path(training_metadata),"config.json",adapter_manifest["training_base_config_sha256"])
    trained=json.loads(training_config.read_text())
    api=HfApi(token=False)
    info=api.model_info(ORIGINAL_MODEL,revision=ORIGINAL_REVISION,files_metadata=True)
    if info.sha!=ORIGINAL_REVISION or (info.card_data or {}).get("license")!="apache-2.0":
        raise ValueError("original_foundation_identity_mismatch")
    weights=[x for x in info.siblings if x.rfilename.endswith(".safetensors")]
    if not weights or any(not x.size or not x.lfs or not x.lfs.sha256 for x in weights):
        raise ValueError("original_foundation_weight_inventory_missing")
    size=sum(x.size for x in weights)
    quantized=precision=="q4_k_m"
    if quantized and quantizer is None:raise ValueError("pinned_native_quantizer_required")
    if shutil.disk_usage(root).free<2*size+((8 if quantized else 2)<<30):
        raise RuntimeError("native_conversion_disk_budget_not_met")
    base=Path(snapshot_download(ORIGINAL_MODEL,revision=ORIGINAL_REVISION,token=False,local_dir=root/"source",
        allow_patterns=["*.safetensors","*.json","*.model","*.jinja","*.txt","README.md","LICENSE*"]))
    for x in weights:
        p=verified_file(base,x.rfilename,x.lfs.sha256)
        if p.stat().st_size!=x.size:raise ValueError("original_foundation_size_mismatch")
    original=json.loads((base/"config.json").read_text())
    if any(original.get(k)!=trained.get(k) for k in ARCH_FIELDS):
        raise ValueError("original_and_nf4_architecture_mismatch")
    pack=root/"pack";pack.mkdir()
    model=pack/("Asterion-OLMo3-7B-"+precision.upper()+".gguf")
    env=dict(os.environ,HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
    quantization_record=None
    if quantized:
        # Start from original BF16 tensors, never requantize the Q8 candidate.
        intermediate=root/"original-bf16.gguf"
        subprocess.run([sys.executable,str(runtime/"convert_hf_to_gguf.py"),str(base),"--outtype","bf16",
                        "--outfile",str(intermediate)],cwd=runtime,env=env,check=True)
        executable=Path(quantizer).resolve(strict=True)
        if not executable.is_file():raise ValueError("quantizer_missing")
        quantization_record={"source_precision":"BF16","source_sha256":file_hash(intermediate),
                             "quantizer_sha256":file_hash(executable),"method":"Q4_K_M",
                             "requantized":False}
        subprocess.run([str(executable),str(intermediate),str(model),"Q4_K_M","4"],cwd=runtime,env=env,check=True)
        intermediate.unlink()
    else:
        subprocess.run([sys.executable,str(runtime/"convert_hf_to_gguf.py"),str(base),"--outtype",precision,
                        "--outfile",str(model)],cwd=runtime,env=env,check=True)
    native=pack/"Asterion-OLMo3-7B-adapter.gguf"
    shutil.copyfile(adapter,native)
    if file_hash(native)!=adapter_manifest["adapter_sha256"]:raise ValueError("native_adapter_copy_mismatch")
    targets=compatible_adapter(model,native)
    sha=file_hash(model)
    heads=original["num_attention_heads"]
    kv_heads=original.get("num_key_value_heads",heads)
    head_dim=original.get("head_dim") or original["hidden_size"]//heads
    kv=2*original["num_hidden_layers"]*kv_heads*head_dim*2
    profile={"schema_version":1,"distribution":"owner_import","file":model.name,"bytes":model.stat().st_size,
      "sha256":sha,"source":ORIGINAL_MODEL+"@"+ORIGINAL_REVISION[:12]+"; adapted candidate",
      "max_input_chars":24000,"max_new_tokens":768,"context_tokens":4096,
      "weight_precision":precision.upper(),"kv_precision_bits":16,"allow_smaller_context":True,
      "vulkan_max_layers":original["num_hidden_layers"],"mapped_no_repack":True,
      "memory_budget":{"resident_weight_bytes":model.stat().st_size,"workspace_bytes":768<<20,"kv_bytes_per_token":kv},
      "adapter":{"file":native.name,"bytes":native.stat().st_size,"sha256":file_hash(native),"base_sha256":sha},
      "system_text":"You are Asterion Control, the local assistant. Carry out authorized tasks using verified capabilities and actual receipts. Preserve user decisions and relevant source context. Do not invent actions, access, or outcomes."}
    write_json(pack/"control-model.candidate.json",profile)
    evidence={"state":"native_pack_built_unqualified","original_base":ORIGINAL_MODEL,
      "original_revision":ORIGINAL_REVISION,"original_weights_sha256":{x.rfilename:x.lfs.sha256 for x in weights},
      "original_config_sha256":file_hash(base/"config.json"),"converter_revision":PINNED_RUNTIME,
      "base_gguf_sha256":sha,"base_gguf_bytes":model.stat().st_size,"native_adapter_sha256":file_hash(native),
      "adapter_target_shapes_verified":targets,"training_record_sha256":adapter_manifest["training_record_sha256"],
      "candidate_profile_sha256":file_hash(pack/"control-model.candidate.json"),
      "device_verified":False,"native_generation_verified":False,"production_promoted":False,
      "weight_precision":precision,"training_base_quantization":"nf4",
      "identical_numerics_to_training_base":False,"quantization":quantization_record}
    write_json(pack/"pack-lineage.json",evidence)
    print(json.dumps(evidence,indent=2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="op",required=True)
    b=sub.add_parser("build")
    b.add_argument("--output",type=Path,required=True)
    b.add_argument("--runtime",type=Path,required=True)
    b.add_argument("--training-metadata",type=Path,required=True)
    b.add_argument("--native-adapter",type=Path,required=True)
    b.add_argument("--precision",choices=["q8_0","f16","bf16","q4_k_m"],default="q8_0")
    b.add_argument("--quantizer",type=Path)
    s=sub.add_parser("split")
    s.add_argument("source",type=Path);s.add_argument("output",type=Path);s.add_argument("--sha256",required=True)
    a=p.parse_args()
    if a.op=="build":build(a.output,a.runtime,a.training_metadata,a.native_adapter,a.precision,a.quantizer)
    else:print(json.dumps(split_file(a.source,a.output,a.sha256),indent=2))
