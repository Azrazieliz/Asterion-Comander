"""Stage a pinned public mobile research foundation and measure free generation.

The fitting and scoring commands run in separate processes. The scorer calls the
same model with and without its adapter and records both responses in the original
evaluation ledger. No device actions or model promotion take place.
"""
from __future__ import annotations

import argparse
import json
import os
from contextlib import nullcontext
from pathlib import Path

from scripts.control_ai_adaptation import file_hash
from scripts.control_ai_evidence_corpus import write

REPO = "allenai/OLMo-2-0425-1B-Instruct"
REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
WEIGHT = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
BASE_ID = "olmo2-0425-1b-instruct-" + REVISION[:12]


def stage(root):
    from huggingface_hub import snapshot_download
    base = root / "base"
    snapshot_download(REPO, revision=REVISION, local_dir=base, token=False,
                      allow_patterns=["model.safetensors", "*.json", "merges.txt", "README.md"])
    if file_hash(base / "model.safetensors") != WEIGHT:
        raise ValueError("upstream foundation digest mismatch")
    card = (base / "README.md").read_text(encoding="utf-8")
    if "license: apache-2.0" not in card.split("---", 2)[1].splitlines():
        raise ValueError("upstream license declaration changed")
    write(root / "fixtures")
    # The trainer only receives training examples, split-validation and preference pairs.
    evidence = root / "evidence"
    evidence.mkdir()
    (root / "fixtures/evaluation.jsonl").rename(evidence / "evaluation.jsonl")
    (evidence / "foundation.json").write_text(json.dumps({
        "repo": REPO, "revision": REVISION, "weights_sha256": WEIGHT,
        "license": "Apache-2.0", "model_card_sha256": file_hash(base / "README.md"),
        "source_commit": os.getenv("GITHUB_SHA"),
        "weights_bytes": (base / "model.safetensors").stat().st_size,
        "suite_sha256_before_fit": file_hash(evidence / "evaluation.jsonl"),
    }, indent=2) + "\n", encoding="utf-8")


def evaluate(root):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from asterion_remote import model_evaluation, model_lab

    base, candidate, evidence = root / "base", root / "candidate", root / "evidence"
    os.environ["ASTERION_MODEL_EVAL_ROOT"] = str(evidence.resolve())
    os.environ["ASTERION_MODEL_LAB_ROOT"] = str(evidence.resolve())
    suite = evidence / "evaluation.jsonl"
    foundation = json.loads((evidence / "foundation.json").read_text(encoding="utf-8"))
    record = json.loads((candidate / "candidate.json").read_text(encoding="utf-8"))
    if (file_hash(suite) != foundation["suite_sha256_before_fit"] or
            file_hash(base / "model.safetensors") != WEIGHT or
            record["base_revision_declared"] != REVISION or record["base_files_sha256"]["model.safetensors"] != WEIGHT):
        raise ValueError("experiment lineage mismatch")
    torch.set_num_threads(4)
    torch.manual_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True, trust_remote_code=False)
    reference = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, trust_remote_code=False,
                                                     torch_dtype=torch.float32, use_safetensors=True)
    parameters = sum(p.numel() for p in reference.parameters())
    model_lab.register_candidate(BASE_ID, "control", REPO, REVISION, WEIGHT, "dense",
                                 parameters/1e9, parameters/1e9, foundation["weights_bytes"], "Apache-2.0")
    adapter_sha = file_hash(candidate / "adapter/adapter_model.safetensors")
    if record["artifact_sha256"]["adapter/adapter_model.safetensors"] != adapter_sha:
        raise ValueError("adapter digest mismatch")
    model = PeftModel.from_pretrained(reference, candidate / "adapter", local_files_only=True)
    model.eval()
    summaries = {}
    with (evidence / "generations.jsonl").open("x", encoding="utf-8") as captures:
        for variant, revision in (("base", REVISION), ("adapted", adapter_sha)):
            def generate(prompt, request_id):
                ids = tokenizer.apply_chat_template([{"role": "user", "content": prompt}],
                        tokenize=True, add_generation_prompt=True, return_tensors="pt")
                with torch.inference_mode():
                    out = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                                         max_new_tokens=18, do_sample=False, use_cache=True,
                                         pad_token_id=tokenizer.pad_token_id)
                new_tokens = out[0, ids.shape[-1]:]
                answer = tokenizer.decode(new_tokens, skip_special_tokens=True)
                captures.write(json.dumps({"variant": variant, "request_id": request_id, "prompt": prompt,
                                           "text": answer, "generated_ids": new_tokens.tolist()}) + "\n")
                return {"content": answer}
            with model.disable_adapter() if variant == "base" else nullcontext():
                result = model_evaluation.run_batch(suite, revision, generate)
            if result["model_errors"] or not result["fully_evaluated"]:
                raise RuntimeError(f"model execution incomplete: {result}")
            summaries[variant] = result
    report = evidence / "comparison.json"
    report.write_text(json.dumps({"variants": summaries, "suite": "public procedural diagnostic",
        "decoding": {"sample": False, "max_new_tokens": 18, "device": "cpu", "dtype": "float32"},
        "generations_sha256": file_hash(evidence / "generations.jsonl"),
        "independent_maturity_cases": 0, "human_reviews": 0, "device_verified": False}, indent=2) + "\n")
    model_lab.register_adaptation("evidence-" + adapter_sha[:16], BASE_ID,
        adapter_sha256=adapter_sha, training_record_sha256=file_hash(candidate / "candidate.json"),
        evaluation_record_sha256=file_hash(report), weights_changed=record["weights_changed"])
    (evidence / "model-laboratory.json").write_text(json.dumps(model_lab.candidate_matrix("control"), indent=2) + "\n")
    print(report.read_text(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("op", choices=["stage", "evaluate"])
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    (stage if args.op == "stage" else evaluate)(args.root)
