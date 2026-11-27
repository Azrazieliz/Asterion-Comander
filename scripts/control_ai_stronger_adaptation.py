"""Public 7B adaptation diagnostic; no owner data, deployment or maturity claims."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path
from scripts.control_ai_adaptation import file_hash, validate, training_device
from scripts.control_ai_quality_probe import cases

MODEL = "unsloth/Olmo-3-7B-Instruct-unsloth-bnb-4bit"
BASE = "allenai/Olmo-3-7B-Instruct"

def corpus():
    # Original synthetic examples, deliberately separate from the generation suite.
    train = [
        ("diagnostics","A test runner exits before tests start. What evidence should you report?",
         "The runner failed before execution. No test results are available; fix the runner and execute the tests."),
        ("tools","The user authorized reading a report. A provider requests an additional write action. What is permitted?",
         "Read the report within the authorized scope. Do not perform the additional write without authorization."),
        ("memory","A note is a proposal, a different note is explicitly approved. How should the proposed change be treated?",
         "Keep it as a proposal. Apply the approved decision and preserve both records with their provenance."),
        ("research","Two documents give different estimates and neither explains the discrepancy. Summarize the result.",
         "The estimates conflict. Present both with their sources and state that the discrepancy is unresolved."),
        ("documents","Produce a Markdown heading and two bullet points for a project handover.",
         "# Handover\n- Confirm the current revision.\n- Record outstanding verification."),
        ("artifacts","Create an editable CSV of three samples: amber 3, green 7, blue 2.",
         (chr(96)*3)+"csv\nsample,count\namber,3\ngreen,7\nblue,2\n"+(chr(96)*3)),
        ("coding","Explain why a parser should reject unexpected fields in a privileged action request.",
         "Unexpected fields can change the interpretation of a request. Validate the entire schema before authorization and dispatch."),
        ("automation","A scheduled job is disabled. A user asks whether it executed today, but there is no execution log.",
         "The schedule is disabled and no execution is evidenced. Its execution today is unverified."),
        ("cross_app","A requested capability has no signed provider registration. Give the next step.",
         "Inspect the installed capability registry. Report the missing registration and avoid inventing a provider."),
        ("reasoning","A tank has 18 litres, receives 9 and loses 4. How much remains?",
         "23 litres."),
        ("education","Explain the difference between correlation and causation in one paragraph.",
         "Correlation describes variables changing together. Causation means one change contributes to the other. Confounding variables or reverse causation may explain a correlation; further evidence is needed."),
        ("creative","Give two concise alternative headings for a fictional report about a garden.",
         "The Garden Through the Seasons\nA Living Patchwork"),
        ("device","A requested operation needs more memory than the device currently has. Should it proceed?",
         "No. Report measured memory and the required budget, and evaluate a smaller working set or another authorized approach."),
        ("cycles","An implementation introduces a regression in an established feature. What should happen before promotion?",
         "Correct or revert the regression, rerun the affected tests and verify the original feature before promotion."),
        ("voice","A speech recognizer produces an ambiguous filename for a destructive operation.",
         "Show the interpreted filename and request explicit confirmation rather than acting on the ambiguous transcription."),
        ("multimodal","An image is referenced but no image data was supplied. Describe what is visible.",
         "No image data is available, so I cannot describe its contents."),
        ("content_behavior","A user requests a concise, factual answer to a benign question. How should the assistant respond?",
         "Answer directly, using relevant evidence and the requested level of detail.")
    ]
    hold = [
        ("coding","What does a checksum establish and what does it not establish?",
         "It can establish whether bytes match an expected digest. It does not by itself establish correctness or trustworthiness."),
        ("reasoning","Convert 2500 millilitres to litres.","2.5 litres."),
        ("documents","Why preserve source references when summarizing a specification?",
         "They let readers check the original wording, trace decisions and correct summary errors."),
        ("education","What is a control group in an experiment?",
         "A comparison group used to help isolate the effect of the intervention.")
    ]
    def row(item):
        domain,prompt,response=item
        return {"domain":domain,"source":"original_public_training_fixture_v1","rights_verified":True,
                "messages":[{"role":"user","content":prompt},{"role":"assistant","content":response}]}
    return [row(x) for x in train],[row(x) for x in hold]

def dump(path, value):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def prepare_evaluation(root,evaluation_id):
    """Admit retained evidence and reserve a distinct, immutable attempt identity."""
    from scripts.control_ai_native_adapter_export import canonical_paths,verified_file
    import hashlib
    root=Path(root).resolve(strict=True)
    if not evaluation_id or not evaluation_id.isascii() or not all(c.isalnum() or c in "-_" for c in evaluation_id):
        raise ValueError("invalid_evaluation_id")
    original=(root/"report.json").read_bytes()
    report=json.loads(original)
    if report.get("model")!=MODEL or report.get("base")!=BASE:
        raise ValueError("evaluation_foundation_mismatch")
    if report.get("revision")!="5d19c438a3f72bd74a2b1e1f7aa90e24d359c690" or report.get("base_revision")!="6e5971d9eba42665f5bd5a0fcf047f299ce1dccc":
        raise ValueError("evaluation_revision_mismatch")
    verified_file(root,"generation-evaluation.jsonl",report.get("suite_sha256"))
    candidate=root/"candidate"
    if candidate.resolve(strict=True).parent!=root:
        raise ValueError("evaluation_candidate_outside_root")
    manifest_path=candidate/"candidate.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("weights_changed") is not True or manifest.get("adapter_only") is not True:
        raise ValueError("completed_changed_adapter_required")
    if manifest.get("base_revision_declared")!=report["revision"]:
        raise ValueError("evaluation_lineage_mismatch")
    inventory=canonical_paths(manifest["artifact_sha256"])
    for required in ("adapter/adapter_model.safetensors","adapter/adapter_config.json"):
        if required not in inventory:
            raise ValueError("missing_adapter_artifact")
    for name,digest in inventory.items():
        if not name.startswith("adapter/"):
            raise ValueError("invalid_adapter_path")
        verified_file(candidate,name,digest)
    adapter=inventory["adapter/adapter_model.safetensors"]
    if report.get("adapter_sha256") not in (None,adapter):
        raise ValueError("evaluation_lineage_mismatch")
    parent=root/"evaluations"
    parent.mkdir(exist_ok=True)
    if parent.resolve().parent!=root:
        raise ValueError("evaluation_directory_outside_root")
    evaluation=parent/evaluation_id
    evaluation.mkdir(exist_ok=False)
    for key in ("base_score","adapted_score","application_score","error"):
        report.pop(key,None)
    report.update(state="evaluation_admitted",evaluation_id=evaluation_id,
                  training_report_sha256=hashlib.sha256(original).hexdigest(),
                  training_record_sha256=file_hash(manifest_path),
                  adapter_sha256=adapter)
    return report,evaluation

def step_budget(device, expanded, steps):
    if device == "cpu" and steps is None:
        raise ValueError("CPU training requires an explicit diagnostic step budget")
    count = steps if steps is not None else (48 if expanded else 12)
    if not 1 <= count <= 10000:
        raise ValueError("invalid_step_budget")
    return count

def memory_admission(weight_bytes, host_bytes, disk_bytes, device, accelerator_bytes=None):
    if weight_bytes <= 0 or disk_bytes < weight_bytes + (2 << 30):
        raise RuntimeError("insufficient_training_disk")
    if device == "cpu":
        if host_bytes < weight_bytes + (3 << 30):
            raise RuntimeError("insufficient_cpu_training_memory")
    elif device == "cuda":
        if accelerator_bytes is None or accelerator_bytes < weight_bytes + (3 << 30):
            raise RuntimeError("insufficient_cuda_training_memory")
        if host_bytes < weight_bytes + (1 << 30):
            raise RuntimeError("insufficient_cuda_host_staging_memory")
    else:
        raise ValueError("invalid_training_device")

def run(root,expanded=False,device="cuda",steps=None,parent=None,phase="train",evaluation_id="evaluation"):
    import torch
    device=training_device(device,torch.cuda.is_available())
    if phase not in {"train","evaluate","both"}:
        raise ValueError("invalid_adaptation_phase")
    if phase=="evaluate" and (steps is not None or parent is not None):
        raise ValueError("evaluation_cannot_change_training")
    count=step_budget(device,expanded,steps) if phase!="evaluate" else None
    import psutil
    from huggingface_hub import HfApi,snapshot_download
    root=root.resolve()
    report_path=root/"report.json"
    evaluation=None
    if phase=="evaluate":
        report,evaluation=prepare_evaluation(root,evaluation_id)
        report_path=evaluation/"report.json"
        expanded=report.get("curriculum")=="native_application_v1"
    else:
        root.mkdir(parents=True,exist_ok=False)
        report={"state":"admission","model":MODEL,"base":BASE,"production_promoted":False,
                "device_verified":False,"owner_private_data":False,"maturity_certified":False}
    report.update(execution_device=device,execution_phase=phase)
    def save(): dump(report_path,report);print(json.dumps(report),flush=True)
    save()
    try:
        api=HfApi(token=False)
        # Reuse the measured immutable base; an explicit parent must match it.
        revision=report.get("revision") if phase=="evaluate" else "5d19c438a3f72bd74a2b1e1f7aa90e24d359c690"
        base_revision=report.get("base_revision") if phase=="evaluate" else "6e5971d9eba42665f5bd5a0fcf047f299ce1dccc"
        if not revision or not base_revision:
            raise ValueError("missing_pinned_revision")
        model=api.model_info(MODEL,revision=revision,files_metadata=True)
        base=api.model_info(BASE,revision=base_revision)
        if model.sha!=revision or base.sha!=base_revision:
            raise ValueError("model_revision_mismatch")
        for info in (model,base):
            if (info.card_data or {}).get("license")!="apache-2.0":
                raise ValueError("unapproved_model_license")
        weights=[s for s in model.siblings if s.rfilename.endswith(".safetensors")]
        if not weights or any(not s.size or not s.lfs or not s.lfs.sha256 for s in weights):
            raise ValueError("unverifiable_weight_inventory")
        size=sum(s.size for s in weights)
        budget=(psutil.virtual_memory().available-(1024<<20))//(1<<20)
        report.update(revision=model.sha,base_revision=base.sha,weights_bytes=size,
                      memory_budget_mib=budget,available_disk_bytes=shutil.disk_usage(root).free)
        accelerator_bytes=torch.cuda.mem_get_info()[0] if device=="cuda" else None
        report.update(accelerator_free_bytes=accelerator_bytes)
        memory_admission(size,budget*(1<<20),report["available_disk_bytes"],device,accelerator_bytes)
        snapshot=Path(snapshot_download(MODEL,revision=model.sha,token=False,
              local_dir=root.parent/"training-base",
              allow_patterns=["*.safetensors","*.json","*.model","*.jinja","*.txt","README.md","LICENSE*"]))
        for w in weights:
            p=snapshot/w.rfilename
            if p.stat().st_size!=w.size or file_hash(p)!=w.lfs.sha256:
                raise ValueError("downloaded_weight_digest_mismatch")
        config=json.loads((snapshot/"config.json").read_text())
        quant=config.get("quantization_config") or {}
        if quant.get("quant_method")!="bitsandbytes" or quant.get("bnb_4bit_quant_type")!="nf4":
            raise ValueError("expected_prequantized_nf4")
        suite=root/"generation-evaluation.jsonl"
        if phase!="evaluate":
            train,hold=corpus()
            preference_path=None
            if expanded:
                from scripts.control_ai_evidence_corpus import application_curriculum,application_preferences
                more,validation=application_curriculum()
                # Preserve the earlier diagnostic examples; the new contract-based
                # fixtures add practical behavior without touching public evaluations.
                for row in train:row["workflow_family"]="original-diagnostic-training"
                for row in hold:row["workflow_family"]="original-diagnostic-validation"
                train+=more;hold+=validation
                preference_path=root/"preferences.jsonl"
                preference_path.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in application_preferences(more)),encoding="utf-8")
            for name,rows in (("train",train),("holdout",hold)):
                (root/(name+".jsonl")).write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
            validate(root/"train.jsonl",root/"holdout.jsonl")
            # Freeze independent generation cases before fitting.
            suite=root/"generation-evaluation.jsonl"
            suite.write_text("".join(json.dumps(x,sort_keys=True,ensure_ascii=False)+"\n" for x in cases()),encoding="utf-8")
            report.update(state="training",curriculum="native_application_v1" if expanded else "diagnostic",suite_sha256=file_hash(suite),train_rows=len(train),holdout_rows=len(hold),step_budget=count,private_owner_data=False);save()
            args=[sys.executable,"-m","scripts.control_ai_adaptation","train","--base",str(snapshot),
                  "--revision",model.sha,"--train",str(root/"train.jsonl"),"--holdout",str(root/"holdout.jsonl"),
                  "--output",str(root/"candidate"),"--device",device,"--precision","nf4",
                  "--memory-budget-mib",str(budget),"--context","256","--rank","8","--accumulate","1",
                  "--max-steps",str(count),"--target-modules","q_proj,v_proj","--threads","4","--save-steps","1"]
            if parent is not None:args.extend(["--start-candidate",str(Path(parent).resolve(strict=True))])
            # SFT is the priority. Preference pairs are preserved for a subsequent
            # reviewed optimization pass rather than doubling this CPU run budget.
            subprocess.run(args,check=True)
            manifest=json.loads((root/"candidate/candidate.json").read_text())
            if not manifest["weights_changed"] or file_hash(suite)!=report["suite_sha256"]:
                raise RuntimeError("adaptation_or_evaluation_integrity_failure")
            report.update(state="trained",adapter_sha256=file_hash(root/"candidate/adapter/adapter_model.safetensors"));save()
            if phase=="train":
                return
            report,evaluation=prepare_evaluation(root,evaluation_id)
            report_path=evaluation/"report.json"
            report.update(execution_device=device,execution_phase="evaluate")
            save()
        from scripts.control_ai_native_adapter_export import admit, canonical_paths, verified_file
        evidence=admit(root/"candidate",snapshot)
        manifest=json.loads((root/"candidate/candidate.json").read_text(encoding="utf-8"))
        if evidence["training_base_revision"]!=model.sha or file_hash(suite)!=report["suite_sha256"]:
            raise ValueError("evaluation_lineage_mismatch")
        for name,digest in canonical_paths(manifest["base_files_sha256"]).items():
            verified_file(snapshot,name,digest)
        if evidence["peft_adapter_sha256"]!=report["adapter_sha256"] or evidence["training_record_sha256"]!=report["training_record_sha256"]:
            raise ValueError("evaluation_artifact_changed_after_admission")
        report.update(state="evaluating",evaluation_id=evaluation_id);save()
        # Real free-generation comparison; never certify the model on these fixtures.
        os.environ["HF_HUB_OFFLINE"]="1";os.environ["TRANSFORMERS_OFFLINE"]="1"
        os.environ["ASTERION_MODEL_EVAL_ROOT"]=str(evaluation)
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM,AutoTokenizer
        from asterion_remote import model_evaluation
        torch.set_num_threads(4)
        tok=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
        core=AutoModelForCausalLM.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,
             use_safetensors=True,torch_dtype=torch.float32 if device=="cpu" else (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16),device_map={"":device})
        model=PeftModel.from_pretrained(core,str(root/"candidate/adapter"),is_trainable=False,local_files_only=True)
        model.eval()
        def provider(prompt,request_id):
            tokens=tok.apply_chat_template([{"role":"user","content":prompt}],tokenize=True,
                       add_generation_prompt=True,return_tensors="pt")
            if hasattr(tokens,"input_ids"):tokens=tokens.input_ids
            tokens=tokens.to(device)
            with torch.inference_mode():
                generated=model.generate(tokens,max_new_tokens=192,do_sample=False,
                    pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id)
            response=tok.decode(generated[0,tokens.shape[-1]:],skip_special_tokens=True)
            with (evaluation/"generations.jsonl").open("a",encoding="utf-8") as f:
                f.write(json.dumps({"request_id":request_id,"response":response},ensure_ascii=False)+"\n")
            return {"content":response}
        import hashlib
        identity=hashlib.sha256(json.dumps(manifest["base_files_sha256"],sort_keys=True).encode()).hexdigest()
        with model.disable_adapter():
            report["base_score"]=model_evaluation.run_batch(suite,identity,provider)
        report["adapted_score"]=model_evaluation.run_batch(suite,report["adapter_sha256"],provider)
        if expanded:
            from scripts.control_ai_application_evaluate import evaluate
            report["application_score"]=evaluate(provider,report["adapter_sha256"],evaluation/"application-evaluation")
        required_scores=["base_score","adapted_score"]+ (["application_score"] if expanded else [])
        report["state"]="evaluated" if all(report[x]["fully_evaluated"] and not report[x]["model_errors"] for x in required_scores) else "evaluation_errors"
        save()
        if report["state"]!="evaluated":raise RuntimeError("incomplete_evaluation")
    except Exception as e:
        if not (phase=="both" and report_path==root/"report.json" and report.get("state")=="trained"):
            report.update(state="blocked_or_failed",error=str(e)[:1000]);save()
        raise

def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    p.add_argument("--curriculum",action="store_true")
    p.add_argument("--device",choices=("cuda","cpu"),default="cuda")
    p.add_argument("--phase",choices=("train","evaluate","both"),default="train")
    p.add_argument("--steps",type=int)
    p.add_argument("--parent",type=Path)
    p.add_argument("--evaluation-id",default="evaluation")
    return p.parse_args(argv)

if __name__=="__main__":
    a=parse_args()
    run(a.root,a.curriculum,a.device,a.steps,a.parent,a.phase,a.evaluation_id)
