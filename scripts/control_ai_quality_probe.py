"""Public original free-generation diagnostic using the existing Model Lab ledger.

Only public licensed GGUFs and authored synthetic evaluation fixtures are used.
The loopback runner is a CI test fixture, never a new production bridge.
"""
from __future__ import annotations
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

from asterion_remote import model_evaluation
from scripts.control_ai_gguf_comparison import CANDIDATES, PINNED_RUNTIME, files_for, tensor_info
from scripts.control_ai_adaptation import file_hash

# Identical cases across models, deliberately not used to fit adapters.
# The strict output contract is scored by the original evaluator.
def cases():
    rows = [
        ("dependencies", "planning", "Build graph: A takes 4 minutes; B takes 6; C takes 3 and needs A; D takes 5 and needs A and B; E takes 2 and needs C and D. Two workers, no overhead. Return JSON with keys minimum_minutes and critical_path (list of task letters).", {"minimum_minutes":13,"critical_path":["B","D","E"]}),
        ("release-gate", "verification", "A release needs signed-build, installed-version and functional-device-test. Build passed and was signed, transfer completed, installed version is unknown, and device test has no receipt. Return JSON with keys verdict (verified, failed or unknown) and missing (list in the original order, of unmet evidence requirements).", {"verdict":"unknown","missing":["installed-version","functional-device-test"]}),
        ("authority", "memory", "Record A: approved 8-bit trial. B: draft recommending 4-bit; C: approved correction superseding A, requiring mixed precision trial; D: later draft suggesting 2-bit. Only approved corrections supersede approved requirements. Return JSON with keys binding_record and remaining_drafts (list in chronological order).", {"binding_record":"C","remaining_drafts":["B","D"]}),
        ("data-model", "coding", "Python input rows=[('a',2),('b',3),('a',5),('c',1),('b',4)]. A dict accumulates sum by key. Then sort keys by descending total and alphabetically on ties. Return JSON with totals (object) and order (list).", {"totals":{"a":7,"b":7,"c":1},"order":["a","b","c"]}),
        ("french-math", "reasoning", "Un lot de 120 articles coûte 2,50 euros par article. Une remise de 15 % s'applique au total, puis 20 euros de livraison sont ajoutés. Le client verse 100 euros d'acompte. Donne un objet JSON avec montant_total et solde, en euros, comme nombres.", {"montant_total":275,"solde":175}),
        ("stat-analysis", "mathematics", "For measurements [12,16,16,18,23], give the median, mean and range (max minus min). Return JSON with numeric keys median, mean and range.", {"median":16,"mean":17,"range":11}),
        ("tool-routing", "cross-app", "A signed inventory advertises provider doc actions read and export; provider media advertises preview only. User asks to export a document, then make an image. No execution receipts exist. Return JSON with export_provider, image_action_available and completed (boolean).", {"export_provider":"doc","image_action_available":False,"completed":False}),
        ("source-reliability", "research", "A 2024 primary source reports 100 units. A 2025 official correction of that same measurement reports 96; a 2026 blog repeats 100 without new data. Return JSON with best_supported_value and authority_year.", {"best_supported_value":96,"authority_year":2025}),
        ("file-recovery", "diagnostics", "File length 1200 bytes. Destination receipt shows durable offset 800; a request for bytes 800..999 timed out and no new status check occurred. Return JSON with action ('recheck' or 'resend') and completion ('verified' or 'unknown').", {"action":"recheck","completion":"unknown"}),
        ("timezone", "scheduling", "A task repeats every 3 hours from 08:15 UTC. Current time is 14:17 UTC; missed executions must not be replayed. Return JSON with next_utc in HH:MM and replay_missed as a boolean.", {"next_utc":"17:15","replay_missed":False}),
        ("units-physics", "science", "A constant 24 W load runs for 45 minutes. Convert energy to watt-hours and joules. Return JSON with wh and joules as numbers.", {"wh":18,"joules":64800}),
        ("uncertainty", "verification", "Two independent tests are mandatory. One fails. The other has not run. Return JSON with verdict ('verified','failed','unknown') and ready (boolean).", {"verdict":"failed","ready":False}),
    ]
    sha = file_hash(Path(__file__))
    return [{"id":f"quality-{ident}", "split":"holdout","category":category,"mode":"json_subset",
             "prompt":prompt+" Return only the requested JSON object, without Markdown.",
             "expected":expected,"source":"original_public_diagnostic","source_sha256":sha}
            for ident,category,prompt,expected in rows]

def request(port,path,payload=None,timeout=300):
    conn=http.client.HTTPConnection("127.0.0.1",port,timeout=timeout)
    try:
        conn.request("GET" if payload is None else "POST",path,
                     None if payload is None else json.dumps(payload).encode(),
                     {"Content-Type":"application/json"})
        response=conn.getresponse()
        data=response.read(2_000_001)
        if response.status!=200 or len(data)>2_000_000:
            raise RuntimeError(f"runner_http_{response.status}")
        return json.loads(data)
    finally:
        conn.close()

def run(candidate,precision,binary,out):
    import psutil
    from huggingface_hub import HfApi,hf_hub_download
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    os.environ["ASTERION_MODEL_EVAL_ROOT"]=str(out)
    suite=out/"evaluation.jsonl"
    suite.write_text("".join(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n" for row in cases()),encoding="utf-8")
    api=HfApi(token=False)
    base_name,pack_name=CANDIDATES[candidate]
    base=api.model_info(base_name)
    pack=api.model_info(pack_name,files_metadata=True)
    license_names=[(m.card_data or {}).get("license") for m in (base,pack)]
    if not any(license_names) or any(x not in ("mit","apache-2.0") for x in license_names if x):
        raise ValueError("model_license_not_admitted")
    files=files_for(pack.siblings,precision)
    report={"candidate":candidate,"precision":precision,"base_repo":base_name,"base_revision":base.sha,
            "gguf_repo":pack_name,"gguf_revision":pack.sha,"runtime_revision":PINNED_RUNTIME,
            "runner_sha256":file_hash(binary),"suite_sha256":file_hash(suite),
            "available_ram_bytes":psutil.virtual_memory().available,"available_disk_bytes":shutil.disk_usage(out).free,
            "weights_bytes":sum(f.size for f in files),"host_only":True,"device_verified":False,
            "production_promoted":False,"independent_maturity_cases":0,"human_reviews":0,
            "state":"not_listed"}
    def save():
        (out/"quality.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if k not in ("tensors",)}),flush=True)
    if not files:save();return
    if report["weights_bytes"]+(1536<<20)>report["available_ram_bytes"] or report["weights_bytes"]+(512<<20)>report["available_disk_bytes"]:
        report["state"]="outside_measured_host_budget";save();return
    paths=[]
    for f in files:
        p=Path(hf_hub_download(pack_name,f.rfilename,revision=pack.sha,local_dir=out.parent/"weights",token=False))
        if p.stat().st_size!=f.size or file_hash(p)!=f.lfs.sha256:raise ValueError("weights_digest_mismatch")
        paths.append(p)
    report.update(tensor_info(paths));report["weight_hashes"]={p.name:file_hash(p) for p in paths}
    model_revision=hashlib.sha256(json.dumps(report["weight_hashes"],sort_keys=True).encode()).hexdigest()
    report["model_identity"]=model_revision
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    report["state"]="running";save()
    with (out/"runner.log").open("w",encoding="utf-8") as log:
        proc=subprocess.Popen([str(binary.resolve()),"-m",str(paths[0]),"-ngl","0","-t","4","-c","2048",
                               "-b","256","-ub","128","-np","1","--host","127.0.0.1","--port",str(port),
                               "--no-webui","--jinja","--reasoning-format","deepseek"],stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+180
            while True:
                if proc.poll() is not None:raise RuntimeError("native_runner_exited")
                try:
                    if request(port,"/health",timeout=3).get("status")=="ok":break
                except (OSError,ValueError,RuntimeError):pass
                if time.monotonic()>deadline:raise TimeoutError("native_runner_not_ready")
                time.sleep(2)
            with (out/"generations.jsonl").open("x",encoding="utf-8") as captures:
                def provider(prompt,request_id):
                    if proc.poll() is not None:raise RuntimeError("native_runner_exited")
                    result=request(port,"/v1/chat/completions",{"messages":[{"role":"user","content":prompt}],
                         "temperature":0,"seed":42,"max_tokens":384,"stream":False})
                    choice=result["choices"][0]
                    text=choice["message"].get("content") or ""
                    captures.write(json.dumps({"request_id":request_id,"prompt":prompt,"content":text,
                        "finish_reason":choice.get("finish_reason"),"usage":result.get("usage")},ensure_ascii=False)+"\n")
                    captures.flush()
                    return {"content":text}
                report["score"]=model_evaluation.run_batch(suite,model_revision,provider)
            report["generations_sha256"]=file_hash(out/"generations.jsonl")
            report["state"]="evaluated" if report["score"]["fully_evaluated"] and not report["score"]["model_errors"] else "evaluation_errors"
        except Exception as error:
            report["state"]="evaluation_error";report["error"]=str(error)[:500];raise
        finally:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            save()
    if report["state"]!="evaluated":raise RuntimeError("incomplete_model_evaluation")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("candidate",choices=CANDIDATES);p.add_argument("--precision",default="q4_k_m")
    p.add_argument("--binary",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
    a=p.parse_args();run(a.candidate,a.precision,a.binary,a.output)
