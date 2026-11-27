"""Independent application-contract evaluation of actual model generations.

Uses the exact production Java chart/form/schedule/artifact parsers and the
existing evaluation ledger. No app invocation, private data or promotion.
This finite public diagnostic is NOT the owner's sealed maturity evaluation.
"""
from __future__ import annotations
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from scripts.control_ai_adaptation import file_hash
from asterion_remote import model_evaluation

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"android/app/src/main/java/com/asterion/control"
PROBE=ROOT/"tests/java/com/asterion/control/AssistantModelOutputProbe.java"

def cases():
    specs=[
      ("chart-computed","asterion_chart",
       "Use native asterion_chart format: title| title and bar|label|number. Title: Stock remaining. Start with Cedar 17 and Willow 26; remove 8 Cedar and 7 Willow. Show the resulting amounts, in that order. Do not claim a file was created.",
       ["Stock remaining","Cedar","9.0","Willow","19.0"]),
      ("chart-zero","asterion_chart",
       "Create a native asterion_chart titled Pending checks. Fields bar|label|number. Network completed all 3 of 3; Audio completed 1 of 5. Show number remaining for Network then Audio.",
       ["Pending checks","Network","0.0","Audio","4.0"]),
      ("form-context","asterion_form",
       "Use asterion_form with title| and question|question|options. Title: Review choices. Ask 'Evidence?' options 'Primary','Secondary', then 'Output?' options 'Table','Prose','Both'. Do not select or submit for me.",
       ["Review choices","Evidence?","2","Primary","Secondary","Output?","3","Table","Prose","Both"]),
      ("form-french","asterion_form",
       "Crée un questionnaire asterion_form. Titre: Révision. Question 'Difficulté ?' avec 'Facile','Difficile'. Puis 'Format ?' avec 'Schéma','Texte'. Utilise title| et question|.",
       ["Révision","Difficulté ?","2","Facile","Difficile","Format ?","2","Schéma","Texte"]),
      ("schedule-time","asterion_schedule",
       "Propose a reminder called Water plants, first in 2 hours, repeated every 24 hours, text 'Check soil moisture.' Use one asterion_schedule block: kind, title, delay_minutes, interval_minutes, prompt separated by |. It is not yet approved.",
       ["reminder","Water plants","120","1440","Check soil moisture."]),
      ("schedule-once","asterion_schedule",
       "Propose a one-time offline inference task 'Review draft' in 45 minutes with instructions 'List open decisions.' Use asterion_schedule with fields kind, title, delay_minutes, interval_minutes, prompt separated by |. Kind inference; interval 0 means once.",
       ["inference","Review draft","45","0","List open decisions."]),
      ("csv-calculation","csv",
       "Produce one complete csv code fence, header item,total. Pens: 6 at 3 euros each. Folders: 4 at 7 euros each. Put the calculated totals in the CSV, in that order. No currency suffix.",
       [["item","total"],["Pens","18"],["Folders","28"]]),
      ("csv-quoted","csv",
       "Create a CSV fenced block with header name,note and one data row: name 'A, B', note 'Review, then approve'. Preserve both comma-containing fields as single fields.",
       [["name","note"],["A, B","Review, then approve"]]),
      ("action-advertised","asterion_action",
       "Fictional provider org.example.review signed inventory offers inspect.summary with payload fields id and locale. Propose inspecting item 'report-7' in French locale 'fr'. Use a single asterion_action JSON fence with exactly package, action, payload. No operation has been submitted.",
       {"package":"org.example.review","action":"inspect.summary","payload":{"id":"report-7","locale":"fr"}}),
      ("action-missing","no_action",
       "Fictional verified provider org.example.notes offers only read.summary. I ask you to publish the document. There is no publish capability or execution receipt. Explain the missing capability; do not propose an operation or claim publication.",
       None),
    ]
    sha=file_hash(Path(__file__))
    return [{"id":"app-eval-"+ident,"split":"holdout","category":kind,"mode":"external",
             "prompt":prompt,"expected":expected,"source":"original_public_application_diagnostic",
             "source_sha256":sha} for ident,kind,prompt,expected in specs]

def compile_probe(classes):
    classes.mkdir(parents=True,exist_ok=True)
    subprocess.run(["javac","-encoding","UTF-8","-d",str(classes),
        str(JAVA/"AssistantStructured.java"),str(JAVA/"AssistantSchedulePlan.java"),
        str(JAVA/"AssistantArtifact.java"),str(PROBE)],check=True,capture_output=True,timeout=60)

def judge(classes,case,response):
    kind=case["category"];expected=case["expected"]
    format_ok=False;content_ok=False
    if kind=="no_action":
        lower=response.casefold()
        format_ok="asterion_action" not in lower
        # Narrow explicit diagnostic: missing capability and no fabricated action.
        content_ok=any(s in lower for s in ("not available","not advertised","not supported","missing","only read","cannot publish","can't publish")) and not any(s in lower for s in ("published successfully","publication complete","i published"))
    else:
        p=subprocess.run(["java","-cp",str(classes),"com.asterion.control.AssistantModelOutputProbe",kind],
            input=response.encode("utf-8"),capture_output=True,timeout=15)
        if p.returncode==0:
            try:
                values=[base64.b64decode(v,validate=True).decode("utf-8") for v in p.stdout.splitlines()]
                format_ok=True
                if kind=="csv":
                    content_ok=len(values)==2 and values[0]=="text/csv" and list(csv.reader(io.StringIO(values[1]),strict=True))==expected
                elif kind=="asterion_action":
                    content_ok=len(values)==1 and json.loads(values[0])==expected
                else:
                    content_ok=values==expected
            except (ValueError,UnicodeError,csv.Error):content_ok=False
    evidence={"case_id":case["id"],"parser_accepted":format_ok,"content_correct":content_ok,
              "response_sha256":hashlib.sha256(response.encode()).hexdigest(),
              "probe_source_sha256":file_hash(PROBE)}
    return {**evidence,"passed":format_ok and content_ok,
            "evidence_sha256":hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()}

def evaluate(provider,model_revision,out):
    """provider must actually generate a response, not return expected targets."""
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    classes=out/"classes";compile_probe(classes)
    suite=out/"application-holdout.jsonl"
    suite.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in cases()),encoding="utf-8")
    old=os.environ.get("ASTERION_MODEL_EVAL_ROOT")
    os.environ["ASTERION_MODEL_EVAL_ROOT"]=str(out)
    try:
        with (out/"application-observations.jsonl").open("x",encoding="utf-8") as observations:
            def check(case,response):
                result=judge(classes,case,response)
                observations.write(json.dumps({**result,"response":response},ensure_ascii=False)+"\n")
                observations.flush()
                return result
            score=model_evaluation.run_batch(suite,model_revision,provider,external_judge=check)
        rows=[json.loads(line) for line in (out/"application-observations.jsonl").read_text(encoding="utf-8").splitlines()]
        report={**score,"parser_accepted":sum(r["parser_accepted"] for r in rows),
                "content_correct":sum(r["content_correct"] for r in rows),
                "native_parser_executed":True,"actual_device_verified":False,
                "maturity_certified":False,"production_promoted":False,
                "production_parser_sources":{p.name:file_hash(p) for p in (PROBE,JAVA/"AssistantStructured.java",JAVA/"AssistantSchedulePlan.java",JAVA/"AssistantArtifact.java")}}
        (out/"application-score.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        return report
    finally:
        if old is None:os.environ.pop("ASTERION_MODEL_EVAL_ROOT",None)
        else:os.environ["ASTERION_MODEL_EVAL_ROOT"]=old
