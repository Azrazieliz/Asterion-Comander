"""Retain the completed public 7B adapter without trusting optimizer pickle or an unpinned base."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import zipfile

from scripts.control_ai_adaptation import file_hash
from scripts.control_ai_native_adapter_export import admit, canonical_paths, verified_file

ARTIFACT_ID=15230982528
ARCHIVE_SHA="964e0da062daf5b74458b4366732d9ee233a25973920d34634d5f17756e91b42"
ADAPTER_SHA="14aec16fcadb689224e25895347466453133e08aeea0926d68e183f1de3f3351"
MODEL="unsloth/Olmo-3-7B-Instruct-unsloth-bnb-4bit"
REVISION="5d19c438a3f72bd74a2b1e1f7aa90e24d359c690"
ORIGINAL_MODEL="allenai/Olmo-3-7B-Instruct"
ORIGINAL_REVISION="6e5971d9eba42665f5bd5a0fcf047f299ce1dccc"


def restore(archive,root):
    archive,root=Path(archive),Path(root)
    if file_hash(archive)!=ARCHIVE_SHA:
        raise ValueError("retained_archive_digest_mismatch")
    root.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as source:
        if len(set(source.namelist()))!=len(source.namelist()):
            raise ValueError("duplicate_archive_member")
        manifest=json.loads(source.read("candidate/candidate.json"))
        if manifest.get("base_revision_declared")!=REVISION or manifest.get("weights_changed") is not True:
            raise ValueError("retained_candidate_identity_mismatch")
        files=canonical_paths(manifest["artifact_sha256"])
        if files.get("adapter/adapter_model.safetensors")!=ADAPTER_SHA:
            raise ValueError("retained_adapter_digest_mismatch")
        for name,digest in files.items():
            if not name.startswith("adapter/"):
                raise ValueError("unexpected_candidate_member")
            member=source.getinfo("candidate/"+name)
            if member.file_size>64*1024*1024:
                raise ValueError("candidate_member_too_large")
            target=root/"candidate"/name
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("xb") as output,source.open(member) as input_:
                import shutil
                shutil.copyfileobj(input_,output)
            verified_file(root/"candidate",name,digest)
        (root/"candidate/candidate.json").write_bytes(source.read("candidate/candidate.json"))
        for name in ("report.json","train.jsonl","holdout.jsonl","generation-evaluation.jsonl"):
            (root/name).write_bytes(source.read(name))
    return root/"candidate"


def stage(root,weights=False):
    from huggingface_hub import HfApi,hf_hub_download
    root=Path(root)
    candidate=root/"candidate"
    manifest=json.loads((candidate/"candidate.json").read_text())
    inventory=canonical_paths(manifest["base_files_sha256"])
    api=HfApi(token=False)
    for name,revision in ((MODEL,REVISION),(ORIGINAL_MODEL,ORIGINAL_REVISION)):
        info=api.model_info(name,revision=revision)
        if info.sha!=revision or (info.card_data or {}).get("license")!="apache-2.0":
            raise ValueError("foundation_identity_or_license_changed")
    base=root/"base"
    base.mkdir(exist_ok=False)
    for name,digest in inventory.items():
        if not weights and name.endswith(".safetensors"):
            continue
        path=Path(hf_hub_download(MODEL,name,revision=REVISION,local_dir=base,token=False))
        if path.resolve()!=verified_file(base,name,digest):
            raise ValueError("staged_base_path_mismatch")
    evidence=admit(candidate,base)
    if weights:
        for name,digest in inventory.items():
            verified_file(base,name,digest)
    evidence.update(archive_sha256=ARCHIVE_SHA,artifact_id=ARTIFACT_ID,base_weights_staged=weights,
                    original_base_revision=ORIGINAL_REVISION,training_model=MODEL,production_promoted=False)
    (root/"retained-lineage.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps(evidence),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("root",type=Path)
    p.add_argument("--weights",action="store_true")
    a=p.parse_args()
    restore(a.archive,a.root)
    stage(a.root,a.weights)
