"""Independent teacher-forced held-out comparison; never claims task completion.

Reads a frozen evaluation split without optimizer access. Reports actual per-
case likelihoods before/after the adapter and exact artifact hashes. These are
likelihood measurements, NOT human reviews or free-generation quality grades.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

if __package__ in {None,''}:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.control_ai_adaptation import read_examples,encode,file_hash,digest

def evaluate(base,adapter,holdout,output,context=512,threads=4):
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from peft import PeftModel
    torch.manual_seed(42);torch.set_num_threads(threads)
    rows=read_examples(holdout)
    tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(base,local_files_only=True,trust_remote_code=False,use_safetensors=True,torch_dtype=torch.float32)
    model.config.use_cache=False
    model=PeftModel.from_pretrained(model,str(Path(adapter)/'adapter'),local_files_only=True,is_trainable=False)
    model.eval();scores=[];started=time.time()
    for key,row in rows:
        encoded=encode(tokenizer,row['messages'],context)
        inputs={k:torch.tensor([v]) for k,v in encoded.items()}
        with torch.inference_mode():
            with model.disable_adapter():before=float(model(**inputs).loss)
            after=float(model(**inputs).loss)
        if not math.isfinite(before+after):raise RuntimeError('nonfinite_evaluation')
        scores.append({'prompt_sha256':key,'domain':row['domain'],'source':row['source'],
            'base_nll':before,'adapted_nll':after,'target_tokens':sum(x!=-100 for x in encoded['labels'])})
        print(json.dumps(scores[-1]),flush=True)
    mean=lambda name:sum(x[name] for x in scores)/len(scores)
    result={'evaluation_kind':'teacher_forced_reference_likelihood','case_count':len(scores),
        'holdout_sha256':digest([r for _,r in rows]),
        'adapter_manifest_sha256':file_hash(Path(adapter)/'candidate.json'),
        'adapter_file_sha256':file_hash(Path(adapter)/'adapter/adapter_model.safetensors'),
        'base_mean_nll':mean('base_nll'),'adapted_mean_nll':mean('adapted_nll'),
        'cases':scores,'elapsed_s':time.time()-started,'free_generation_evaluated':False,
        'human_reviewed_count':0,'independent_maturity_holdout_count':0,
        'owner_behavior_certified':False,'phone_accepted':False,'production_promoted':False}
    Path(output).write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--adapter',required=True)
    p.add_argument('--holdout',required=True);p.add_argument('--output',required=True)
    p.add_argument('--context',type=int,default=512);p.add_argument('--threads',type=int,default=4)
    a=p.parse_args();print(json.dumps(evaluate(a.base,a.adapter,a.holdout,a.output,a.context,a.threads),indent=2))
