"""Public 7B adaptation diagnostic; no owner data, deployment or maturity claims."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from scripts.control_ai_adaptation import file_hash, validate
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
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def run(root,expanded=False):
    import psutil
    from huggingface_hub import HfApi,snapshot_download
    root=root.resolve();root.mkdir(parents=True,exist_ok=False)
    report={"state":"admission","model":MODEL,"base":BASE,"production_promoted":False,
            "device_verified":False,"owner_private_data":False,"maturity_certified":False}
    def save(): dump(root/"report.json",report);print(json.dumps(report),flush=True)
    save()
    try:
        api=HfApi(token=False)
        model=api.model_info(MODEL,files_metadata=True)
        base=api.model_info(BASE)
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
        if size+(3<<30)>budget*(1<<20) or size+(2<<30)>report["available_disk_bytes"]:
            report["state"]="outside_measured_host_budget";save();return
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
        report.update(state="training",curriculum="native_application_v1" if expanded else "diagnostic",suite_sha256=file_hash(suite),train_rows=len(train),holdout_rows=len(hold),step_budget=48 if expanded else 12,private_owner_data=False);save()
        args=[sys.executable,"-m","scripts.control_ai_adaptation","train","--base",str(snapshot),
              "--revision",model.sha,"--train",str(root/"train.jsonl"),"--holdout",str(root/"holdout.jsonl"),
              "--output",str(root/"candidate"),"--device","cpu","--precision","nf4",
              "--memory-budget-mib",str(budget),"--context","256","--rank","8","--accumulate","1",
              "--max-steps","48" if expanded else "12","--target-modules","q_proj,v_proj","--threads","4","--save-steps","4"]
        # SFT is the priority. Preference pairs are preserved for a subsequent
        # reviewed optimization pass rather than doubling this CPU run budget.
        subprocess.run(args,check=True)
        manifest=json.loads((root/"candidate/candidate.json").read_text())
        if not manifest["weights_changed"] or file_hash(suite)!=report["suite_sha256"]:
            raise RuntimeError("adaptation_or_evaluation_integrity_failure")
        report.update(state="trained",adapter_sha256=file_hash(root/"candidate/adapter/adapter_model.safetensors"));save()
        # Real free-generation comparison; never certify the model on these fixtures.
        os.environ["HF_HUB_OFFLINE"]="1";os.environ["TRANSFORMERS_OFFLINE"]="1"
        os.environ["ASTERION_MODEL_EVAL_ROOT"]=str(root)
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM,AutoTokenizer
        from asterion_remote import model_evaluation
        torch.set_num_threads(4)
        tok=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
        core=AutoModelForCausalLM.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,
             use_safetensors=True,torch_dtype=torch.float32,device_map={"":"cpu"})
        model=PeftModel.from_pretrained(core,str(root/"candidate/adapter"),is_trainable=False,local_files_only=True)
        model.eval()
        def provider(prompt,request_id):
            tokens=tok.apply_chat_template([{"role":"user","content":prompt}],tokenize=True,
                       add_generation_prompt=True,return_tensors="pt")
            if hasattr(tokens,"input_ids"):tokens=tokens.input_ids
            with torch.inference_mode():
                generated=model.generate(tokens,max_new_tokens=192,do_sample=False,
                    pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id)
            response=tok.decode(generated[0,tokens.shape[-1]:],skip_special_tokens=True)
            with (root/"generations.jsonl").open("a",encoding="utf-8") as f:
                f.write(json.dumps({"request_id":request_id,"response":response},ensure_ascii=False)+"\n")
            return {"content":response}
        import hashlib
        identity=hashlib.sha256(json.dumps(manifest["base_files_sha256"],sort_keys=True).encode()).hexdigest()
        with model.disable_adapter():
            report["base_score"]=model_evaluation.run_batch(suite,identity,provider)
        report["adapted_score"]=model_evaluation.run_batch(suite,report["adapter_sha256"],provider)
        report["state"]="evaluated" if all(report[x]["fully_evaluated"] and not report[x]["model_errors"] for x in ("base_score","adapted_score")) else "evaluation_errors"
        save()
        if report["state"]!="evaluated":raise RuntimeError("incomplete_evaluation")
    except Exception as e:
        report.update(state="blocked_or_failed",error=str(e)[:1000]);save();raise

if __name__=="__main__":
    run(Path(sys.argv[1]),expanded="--curriculum" in sys.argv[2:])
