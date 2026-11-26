"""Control Model Lab: local, evidence-gated assistant adaptation.

No downloading, credential access, remote model code, or automatic deployment.
Run validate/selftest without ML dependencies. Train only from a reviewed local
base snapshot on a suitable accelerator. Output is a candidate, not a release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
import platform
import importlib.metadata
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.control_ai_preferences import optimize, read_preferences

DOMAINS = frozenset(("reasoning","coding","tools","research","documents","device",
                     "cross_app","voice","diagnostics","cycles","creative","memory",
                     "multimodal","automation","content_behavior","artifacts","education"))
ROLES = {"system","user","assistant"}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                         separators=(",",":")).encode("utf-8")).hexdigest()

def read_examples(path):
    rows = []
    seen = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row,dict) or row.get("domain") not in DOMAINS:
            raise ValueError(f"{path}:{number}: invalid domain")
        if not isinstance(row.get("source"),str) or not row["source"].strip():
            raise ValueError(f"{path}:{number}: provenance required")
        if row.get("rights_verified") is not True:
            raise ValueError(f"{path}:{number}: dataset rights not verified")
        messages = row.get("messages")
        if not isinstance(messages,list) or len(messages)<2:
            raise ValueError(f"{path}:{number}: messages required")
        roles=[]
        for msg in messages:
            if (not isinstance(msg,dict) or set(msg)!={"role","content"}
                or msg["role"] not in ROLES or not isinstance(msg["content"],str)
                or not msg["content"].strip()):
                raise ValueError(f"{path}:{number}: invalid message")
            roles.append(msg["role"])
        if roles[0]=="system":
            roles=roles[1:]
        if roles != ["user","assistant"]*(len(roles)//2) or not roles:
            raise ValueError(f"{path}:{number}: invalid dialogue ordering")
        # Compare final user prompt independently of system or earlier context.
        # Exact normalized matches are rejected; semantic near-duplicates still
        # require a separate contamination audit before maturity certification.
        prompt=" ".join(messages[-2]["content"].casefold().split())
        key=digest(prompt)
        if key in seen:
            raise ValueError(f"{path}:{number}: duplicate final user prompt")
        seen.add(key)
        rows.append((key,row))
    if not rows:
        raise ValueError(f"{path}: empty corpus")
    return rows

def validate(train_path,holdout_path):
    train,holdout=read_examples(train_path),read_examples(holdout_path)
    if {k for k,_ in train}&{k for k,_ in holdout}:
        raise ValueError("training/holdout prompt contamination")
    def summarize(rows):
        counts={}
        for _,r in rows:
            counts[r["domain"]]=counts.get(r["domain"],0)+1
        return {"count":len(rows),"by_domain":counts,
                "sha256":digest([r for _,r in rows])}
    return train,holdout,{"training":summarize(train),"holdout":summarize(holdout),
                         "holdout_minimum_met":len(holdout)>=50000,
                         "semantic_contamination_audited":False,
                         "maturity_certified":False}

def encode(tokenizer,messages,max_tokens):
    # Model's own chat template: no Qwen-specific tokens.
    prefix=tokenizer.apply_chat_template(messages[:-1],tokenize=True,
                                          add_generation_prompt=True)
    full=tokenizer.apply_chat_template(messages,tokenize=True,
                                        add_generation_prompt=False)
    if not isinstance(prefix,list) or not isinstance(full,list):
        raise ValueError("chat template did not return token IDs")
    if full[:len(prefix)]!=prefix or len(full)<=len(prefix):
        raise ValueError("incompatible template: assistant-only masking not proven")
    if len(full)>max_tokens:
        raise ValueError("sample exceeds context budget; curate, do not silently truncate")
    return {"input_ids":full,"attention_mask":[1]*len(full),
            "labels":[-100]*len(prefix)+full[len(prefix):]}

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def trainable_hash(model):
    import torch
    h=hashlib.sha256()
    for name,tensor in sorted(model.named_parameters()):
        if tensor.requires_grad:
            value=tensor.detach().cpu().contiguous()
            h.update(name.encode());h.update(str(value.dtype).encode())
            h.update(str(tuple(value.shape)).encode());h.update(value.view(-1).view(torch.uint8).numpy().tobytes())
    return h.hexdigest()

def training_device(requested,cuda_available):
    if requested=="cpu":return "cpu"
    if requested not in {"auto","cuda"}:raise ValueError("invalid_training_device")
    if not cuda_available:
        raise RuntimeError("CUDA accelerator unavailable; CPU training requires explicit --device cpu and a memory budget")
    return "cuda"

def train_adapter(args):
    train,holdout,manifest=validate(args.train,args.holdout)
    preferences=read_preferences(args.preferences,train,holdout) if getattr(args,"preferences",None) else []
    # No training on holdout, no implicit downloads and no remote model code.
    os.environ["HF_HUB_OFFLINE"]="1"
    os.environ["TRANSFORMERS_OFFLINE"]="1"
    import torch
    from transformers import AutoConfig,AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig,Trainer,TrainingArguments
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    device=training_device(getattr(args,"device","auto"),torch.cuda.is_available())
    torch.manual_seed(42)
    torch.set_num_threads(getattr(args,"threads",4))
    started=time.time()
    base=Path(args.base).resolve()
    if not (base/"config.json").is_file():
        raise ValueError("reviewed local base snapshot required")
    if not re.fullmatch(r"[0-9a-f]{40,64}",args.revision):
        raise ValueError("immutable base revision required")
    files=sorted(p for p in base.rglob("*") if p.is_file() and
                 (p.suffix in {".json",".safetensors",".model",".txt",".jinja"}))
    if not any(p.suffix==".safetensors" for p in files):
        raise ValueError("local safetensors weights required")
    hashes={}
    for p in files:
        h=hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):
                h.update(chunk)
        hashes[str(p.relative_to(base))]=h.hexdigest()
    out=Path(args.output)
    if out.exists():
        raise ValueError("candidate output must not already exist")
    tokenizer=AutoTokenizer.from_pretrained(str(base),local_files_only=True,
                                             trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        if tokenizer.eos_token_id is None:
            raise ValueError("tokenizer lacks padding and EOS")
        tokenizer.pad_token=tokenizer.eos_token
    encoded=[encode(tokenizer,r["messages"],args.context) for _,r in train]
    bf16=device=="cuda" and torch.cuda.is_bf16_supported()
    dtype=torch.float32 if device=="cpu" else torch.bfloat16 if bf16 else torch.float16
    precision=getattr(args,"precision","native")
    config=AutoConfig.from_pretrained(str(base),local_files_only=True,trust_remote_code=False)
    existing_quant=getattr(config,"quantization_config",None)
    quantized=precision=="nf4"
    if existing_quant and (not quantized or not isinstance(existing_quant,dict) or
            existing_quant.get("quant_method")!="bitsandbytes" or
            existing_quant.get("bnb_4bit_quant_type")!="nf4" or
            not existing_quant.get("load_in_4bit",existing_quant.get("_load_in_4bit",False))):
        raise ValueError("unsupported_prequantized_training_base")
    load_options={}
    if quantized:
        load_options["device_map"]={"":device}
        if not existing_quant:
            load_options["quantization_config"]=BitsAndBytesConfig(
                load_in_4bit=True,bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype)
    if device=="cpu":
        import psutil
        budget=getattr(args,"memory_budget_mib",0)*1024**2
        base_bytes=sum(p.stat().st_size for p in files if p.suffix==".safetensors")
        # Admission estimate only. On-the-fly quantization still requires
        # transient RAM for source tensors and dequantization workspaces.
        estimate=base_bytes*(1 if existing_quant else 2)+2*1024**3
        if budget<=0 or estimate>budget or budget>psutil.virtual_memory().available:
            raise RuntimeError("cpu_training_memory_admission_failed")
        if not 1<=getattr(args,"max_steps",0):
            raise ValueError("cpu_training_requires_explicit_step_budget")
    model=AutoModelForCausalLM.from_pretrained(str(base),local_files_only=True,
        trust_remote_code=False,use_safetensors=True,torch_dtype=dtype,**load_options)
    model.config.use_cache=False
    if quantized:
        if not getattr(model,"is_loaded_in_4bit",False):
            raise RuntimeError("requested_nf4_base_not_loaded")
        model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    requested=getattr(args,"target_modules","all-linear")
    targets=requested if requested=="all-linear" else requested.split(",")
    model=get_peft_model(model,LoraConfig(r=getattr(args,"rank",16),lora_alpha=2*getattr(args,"rank",16),lora_dropout=0.05,
        target_modules=targets,bias="none",task_type="CAUSAL_LM"))
    model.enable_input_require_grads()
    before=trainable_hash(model)
    def collate(rows):
        width=max(len(r["input_ids"]) for r in rows)
        def padded(key,pad):
            return torch.tensor([r[key]+[pad]*(width-len(r[key])) for r in rows])
        return {"input_ids":padded("input_ids",tokenizer.pad_token_id),
                "attention_mask":padded("attention_mask",0),"labels":padded("labels",-100)}
    out.mkdir(parents=True,exist_ok=False)
    trainer=Trainer(model=model,train_dataset=encoded,data_collator=collate,
        args=TrainingArguments(output_dir=str(out/"checkpoints"),
            per_device_train_batch_size=1,gradient_accumulation_steps=getattr(args,"accumulate",8),
            gradient_checkpointing=True,num_train_epochs=args.epochs,
            max_steps=getattr(args,"max_steps",-1),use_cpu=device=="cpu",
            learning_rate=getattr(args,"learning_rate",1e-4),bf16=bf16,fp16=device=="cuda" and not bf16,logging_steps=1,
            save_strategy="epoch",save_total_limit=2,report_to=[],
            remove_unused_columns=False,seed=42))
    metrics=trainer.train().metrics
    del trainer
    after_sft=trainable_hash(model)
    if before==after_sft:
        raise RuntimeError("sft_did_not_change_adapter_weights")
    preference_record=None
    if preferences:
        model.zero_grad(set_to_none=True)
        model.save_pretrained(str(out/"sft-adapter"),safe_serialization=True)
        preference_record=optimize(model,tokenizer,preferences,context=args.context,
            steps=args.preference_steps,learning_rate=args.preference_learning_rate,beta=args.preference_beta)
        preference_record["dataset_sha256"]=digest(preferences)
        preference_record["sft_weights_sha256"]=after_sft
    after=trainable_hash(model)
    if preferences and after==after_sft:
        raise RuntimeError("preference_training_did_not_change_adapter_weights")
    if before==after:raise RuntimeError("training_did_not_change_adapter_weights")
    model.save_pretrained(str(out/"adapter"),safe_serialization=True)
    tokenizer.save_pretrained(str(out/"adapter"))
    manifest.update({"base_revision_declared":args.revision,"base_files_sha256":hashes,
        "training_metrics":metrics,"training_precision":precision,"preference_training":preference_record,"adapter_only":True,"evaluated":False,
        "device_verified":False,"production_replaced":False,"weights_changed":before!=after,
        "trainable_sha256_before":before,"trainable_sha256_after":after,
        "artifact_sha256":{str(p.relative_to(out)):file_hash(p) for p in sorted((out/"adapter").rglob("*")) if p.is_file()},
        "training_device":device,"elapsed_s":time.time()-started,
        "parameters_trainable":sum(p.numel() for p in model.parameters() if p.requires_grad),
        "seed":42,"training_arguments":vars(args),
        "runtime_versions":{p:importlib.metadata.version(p) for p in ("torch","transformers","peft","accelerate")},
        "platform":platform.platform()})
    (out/"candidate.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))

def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as root:
        a,b=Path(root)/"train.jsonl",Path(root)/"holdout.jsonl"
        def example(p):
            return {"domain":"reasoning","source":"original synthetic test",
                "rights_verified":True,"messages":[{"role":"user","content":p},
                                      {"role":"assistant","content":"42"}]}
        a.write_text(json.dumps(example("question one")),encoding="utf-8")
        b.write_text(json.dumps(example("question two")),encoding="utf-8")
        _,_,m=validate(a,b)
        assert m["training"]["count"]==1 and not m["holdout_minimum_met"]
        b.write_text(json.dumps(example(" QUESTION   ONE ")),encoding="utf-8")
        try: validate(a,b)
        except ValueError: pass
        else: raise AssertionError("contaminated split accepted")
        class Tokenizer:
            def apply_chat_template(self,messages,tokenize,add_generation_prompt):
                return [1,2] if add_generation_prompt else [1,2,3,4]
        x=encode(Tokenizer(),example("x")["messages"],8)
        assert x["labels"]==[-100,-100,3,4]
        try: encode(Tokenizer(),example("x")["messages"],3)
        except ValueError: pass
        else: raise AssertionError("oversize accepted")
        r=example("x");r["rights_verified"]=False
        a.write_text(json.dumps(r),encoding="utf-8")
        try: read_examples(a)
        except ValueError: pass
        else: raise AssertionError("unverified rights accepted")
    print("5 local validation assertions passed; no model training or inference performed")

def main():
    p=argparse.ArgumentParser()
    s=p.add_subparsers(dest="op",required=True)
    s.add_parser("selftest")
    for name in ("validate","train"):
        q=s.add_parser(name);q.add_argument("--train",required=True)
        q.add_argument("--holdout",required=True)
        if name=="train":
            q.add_argument("--base",required=True);q.add_argument("--revision",required=True)
            q.add_argument("--output",required=True);q.add_argument("--context",type=int,default=2048)
            q.add_argument("--epochs",type=float,default=1)
            q.add_argument("--device",choices=("auto","cuda","cpu"),default="auto")
            q.add_argument("--threads",type=int,default=4)
            q.add_argument("--memory-budget-mib",type=int,default=0)
            q.add_argument("--max-steps",type=int,default=-1)
            q.add_argument("--rank",type=int,default=16)
            q.add_argument("--accumulate",type=int,default=8)
            q.add_argument("--learning-rate",type=float,default=1e-4)
            q.add_argument("--precision",choices=("native","nf4"),default="native")
            q.add_argument("--target-modules",default="all-linear")
            q.add_argument("--preferences")
            q.add_argument("--preference-steps",type=int,default=0)
            q.add_argument("--preference-learning-rate",type=float,default=5e-6)
            q.add_argument("--preference-beta",type=float,default=0.1)
    a=p.parse_args()
    if a.op=="selftest":selftest()
    elif a.op=="validate":print(json.dumps(validate(a.train,a.holdout)[2],indent=2))
    else:
        if not 128<=a.context<=8192 or not 0<a.epochs<=10:
            raise ValueError("invalid training budget")
        if not 1<=a.threads<=8 or not 1<=a.rank<=128 or not 1<=a.accumulate<=32 or not 0<a.learning_rate<=0.01:
            raise ValueError("invalid_training_resource_budget")
        if not re.fullmatch(r"(?:all-linear|[A-Za-z_][A-Za-z0-9_]*(?:,[A-Za-z_][A-Za-z0-9_]*)*)",a.target_modules):
            raise ValueError("invalid_adapter_modules")
        if bool(a.preferences)!=bool(a.preference_steps) or not 0<=a.preference_steps<=100000:
            raise ValueError("invalid_preference_training_steps")
        if not 0<a.preference_learning_rate<=0.01 or not 0<a.preference_beta<=10:
            raise ValueError("invalid_preference_training_budget")
        train_adapter(a)
if __name__=="__main__":
    main()
