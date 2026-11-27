"""Reproducible public Model Lab fixtures for evidence-based decisions and general replay.

Targets are computed by the operations below. They are training/validation fixtures,
never real device receipts, private project histories or human quality reviews.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record(family, index, domain, instruction, result):
    return {
        "id": f"{family}-{index:02d}", "domain": domain, "workflow_family": family,
        "rights_verified": True, "target_origin": "original_executable_fixture",
        "source": f"scripts/control_ai_evidence_corpus.py#{family}",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "messages": [{"role": "user", "content": instruction},
                     {"role": "assistant", "content": str(result)}],
    }


def build():
    train, validation, evaluation, preferences = [], [], [], []
    for i in range(12):
        expected = f"release-record-{i}"
        observed = expected if i % 3 == 0 else None if i % 3 == 1 else expected + "-old"
        src = sha(expected)[:16]
        dst = sha(observed)[:16] if observed is not None else "unobserved"
        verdict = "unknown" if observed is None else "verified" if src == dst else "failed"
        prompt = (f"Export {i} was acknowledged. Reference digest prefix {src}; independent "
                  f"destination digest prefix {dst}. Classify integrity. Reply only verified, failed or unknown.")
        row = record("export-integrity", i, "artifacts", prompt, verdict)
        train.append(row)
        if i < 6:
            preferences.append({"prompt": row["messages"][:-1], "chosen": verdict,
                                "rejected": "failed" if verdict == "verified" else "verified",
                                **{k: row[k] for k in ("source", "source_sha256", "workflow_family", "rights_verified", "target_origin")}})

        expected_cap = f"read.table.{i}"
        actual = [f"read.text.{i}", expected_cap if i % 2 else f"read.plot.{i}"]
        train.append(record("signed-inventory", i, "cross_app",
            f"A signed provider advertises {', '.join(actual)}. Is {expected_cap} advertised? Answer yes or no.",
            "yes" if expected_cap in actual else "no"))

        total, size = 11 + i * 3, 3 + i % 4
        train.append(record("page-count", i, "reasoning",
            f"Fit {total} records into pages of capacity {size}. Return only the minimum number of pages.",
            (total + size - 1) // size))
        values = [i, 2 * i + 1, 3 * i + 4, i + 9]
        train.append(record("python-slice", i, "coding",
            f"What integer is printed by Python: print({values}[1:3][-1])? Give only the integer.",
            values[1:3][-1]))

    # Different mechanisms and source families. The trainer gets validation
    # identity/contamination checks only; the free-generation suite is separate.
    for i in range(6):
        received, required = 80 + i, 80 + i + (i % 2)
        validation.append(record("sample-count", i, "diagnostics",
            f"Observation {i}: exactly {required} samples are required and the counter reads {received}. "
            "Is the count complete? Answer yes or no.", "yes" if received == required else "no"))
        validation.append(record("distance", i, "education",
            f"A cart travels {4+i} metres per second for {7+i} seconds. Return its distance as an integer in metres.",
            (4 + i) * (7 + i)))

    for i in range(6):
        expected = [f"case-{i}-a", f"case-{i}-b"]
        passed = set(expected[:i % 3])
        failed = {expected[-1]} if i % 3 == 1 else set()
        verdict = "failed" if failed else "verified" if passed == set(expected) else "unknown"
        row = record("test-postconditions", i, "diagnostics",
            f"Release check {100+i} requires passes for both {expected}. Observed passes: {sorted(passed)}. "
            f"Observed failures: {sorted(failed)}. No other outcomes have been observed. "
            "Classify this release check. Output only verified, failed or unknown.", verdict)
        evaluation.append(row)

        current = f"note-{i}:B" if i % 2 == 0 else f"note-{i}:A"
        replacement = "owner-approved correction" if i % 2 == 0 else "draft suggestion"
        evaluation.append(record("decision-authority", i, "memory",
            f"An accepted entry is note-{i}:A. Later, a {replacement} names note-{i}:B. "
            "Only an approved correction supersedes an accepted entry. Return the authoritative identifier alone.",
            current))
        price, n = 7 + i, 2 + i
        evaluation.append(record("french-unit-cost", i, "reasoning",
            f"{n} carnets coûtent {n*price} euros au total. Quel est le prix d’un carnet ? Réponds uniquement par le nombre.",
            price))
        items = [i, i+4, i, i+1]
        evaluation.append(record("distinct-count", i, "coding",
            f"In Python, what integer is len(set({items}))? Output the integer only.", len(set(items))))
    return train, validation, evaluation, preferences


def write_jsonl(path, rows):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write(destination):
    train, validation, evaluation, preferences = build()
    groups = [{r["workflow_family"] for r in rows} for rows in (train, validation, evaluation)]
    if any(a & b for i, a in enumerate(groups) for b in groups[i+1:]):
        raise ValueError("cross_split_workflow_family")
    prompts = [r["messages"][-2]["content"].strip().casefold() for rows in (train, validation, evaluation) for r in rows]
    if len(set(prompts)) != len(prompts):
        raise ValueError("cross_split_or_within_split_duplicate")
    destination.mkdir(parents=True, exist_ok=False)
    for filename, rows in (("train", train), ("validation", validation), ("preferences", preferences)):
        write_jsonl(destination / (filename + ".jsonl"), rows)
    write_jsonl(destination / "evaluation.jsonl", [
        {"id": row["id"], "split": "holdout", "category": row["workflow_family"], "mode": "exact",
         "prompt": row["messages"][0]["content"], "expected": row["messages"][1]["content"],
         "source": row["source"], "source_sha256": row["source_sha256"]} for row in evaluation])


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("output", type=Path)
    write(cli.parse_args().output)


def application_curriculum():
    """Original deterministic native-response and owner-methodology fixtures.

    Values are computed, and syntax mirrors production Java response contracts.
    Not proprietary teacher outputs, user history, or observed live operations.
    Validation families are distinct; neither split is an independent maturity benchmark.
    """
    fence=chr(96)*3
    def block(kind,lines):
        return fence+kind+"\n"+"\n".join(lines)+"\n"+fence
    train,validation=[],[]
    def add(family,i,domain,prompt,target):
        train.append(record(family,i,domain,prompt,target))
    for i in range(8):
        a,b,c=3+i,2*i+6,5+i*2
        add("native-chart",i,"documents",
            f"Display a native bar chart titled Sample {i} with Alder {a}, Birch {b}, Cedar {c}. Use asterion_chart.",
            block("asterion_chart",[f"title|Sample {i}",f"bar|Alder|{a}",f"bar|Birch|{b}",f"bar|Cedar|{c}"]))
        add("native-questionnaire",i,"tools",
            f"Create one interactive questionnaire titled Review {i}. Ask Format? with PDF or CSV, and Detail? with Brief or Full. Use asterion_form.",
            block("asterion_form",[f"title|Review {i}","question|Format?|PDF|CSV","question|Detail?|Brief|Full"]))
        delay=5+i*5
        interval=0 if i%2==0 else 60+i*15
        mode="reminder" if i%2==0 else "inference"
        title=f"Notebook review {i}"
        instructions=f"Review notebook {i} locally."
        add("native-schedule",i,"automation",
            f"Propose a {mode} task called {title}, first in {delay} minutes, repeat every {interval} minutes (0 means once). Instructions: {instructions} Use asterion_schedule, not a completion claim.",
            block("asterion_schedule",[f"kind|{mode}",f"title|{title}",f"delay_minutes|{delay}",
                 f"interval_minutes|{interval}",f"prompt|{instructions}"]))
        add("native-editable-csv",i,"artifacts",
            f"Make an editable CSV, columns item,count. Rows paper,{a} and card,{b}. Provide one complete CSV fence.",
            block("csv",["item,count",f"paper,{a}",f"card,{b}"]))
        app=f"org.example.fixture{i}"
        payload={"document_id":f"sample-{i}"}
        action={"package":app,"action":"read.document","payload":payload}
        add("native-signed-proposal",i,"cross_app",
            f"Fictional signed test inventory: {app} offers read.document, payload {json.dumps(payload)}. Propose that read using asterion_action. No invocation or receipt exists.",
            block("asterion_action",[json.dumps(action,separators=(",",":"))]))
        add("native-transfer-recovery",i,"diagnostics",
            f"A file has {a*100} bytes. Last durable receipt says {a*50} bytes. Next write timed out. What must occur before another write?",
            "Read the existing transfer receipt, verify its identity and committed offset, then transmit only the missing suffix if the receipt permits it. The outcome is unknown until verified.")
        add("owner-methodology",i,"cycles",
            f"Task {i} requires build, test and installation verification. Build passed; the functional test failed; installation was not attempted. Report status and next action.",
            "Build passed, functional acceptance failed, installation unverified. Correct the failure, rerun the affected tests and verify installation before claiming completion.")
        add("memory-provenance",i,"memory",
            f"Record {i}A is approved. Record {i}B is a later suggestion, not approved. Which is binding? Give the ID only.",
            f"{i}A")
        add("research-provenance",i,"research",
            f"Source A measured {a} samples; Source B quotes A without additional measurements. How many independently measured samples are established? Give the number only.",
            str(a))
        add("math-percent",i,"reasoning",
            f"An invoice of {100*(i+1)} euros receives a 10% discount, then a 20-euro delivery charge. Give the final numeric amount.",
            str(90*(i+1)+20))
        add("python-aggregation",i,"coding",
            f"Python: d={{'a':{a},'b':{b}}}; d['a']+={c}; print(sum(d.values())). Give the output only.",
            str(a+b+c))
        add("french-conversion",i,"education",
            f"Convertis {1000*(i+2)} millilitres en litres. Donne seulement la valeur numérique.",
            str(i+2))
        add("physics-energy",i,"reasoning",
            f"A constant {a*10} W load runs for 2 hours. Give its energy in Wh, as a number only.",
            str(a*20))
        add("bounded-multimodal",i,"multimodal",
            f"A user refers to image fixture {i}, but no image bytes or description are available. Can its visible content be verified?",
            "No. The image is not available, so its visible content cannot be verified.")
        add("voice-confirmation",i,"voice",
            f"Voice recognition returned two different possible filenames for requested deletion {i}. Neither was confirmed. What is the correct next action?",
            "Do not delete either file. Confirm the exact intended filename before dispatching the destructive operation.")
        add("device-resource-admission",i,"device",
            f"Available memory: {a} GiB. A model needs {a+2} GiB including runtime. Does it fit? State the deficit in GiB.",
            "No. The measured deficit is 2 GiB.")
    # Different mechanisms from the training families. Keep exact prompts out
    # of all earlier published model comparison and adaptation suites.
    for i in range(8):
        val=3+i
        validation.append(record("holdout-branch-order",i,"coding",
            f"Python: x={val}; print(x*3 if x%2 else x+4). Return the integer only.",
            val*3 if val%2 else val+4))
        validation.append(record("holdout-fraction",i,"reasoning",
            f"{val} of {4*val} pages are complete. Give the percentage as an integer.",25))
        validation.append(record("holdout-cancellation",i,"diagnostics",
            f"An operation {i} requested cancellation but has no cancellation receipt. Is cancellation verified? Answer yes or no.","no"))
    return train,validation


def application_preferences(train):
    """Pairs with deliberately wrong contract, not sampled private conversations."""
    result=[]
    for row in train:
        family=row["workflow_family"]
        chosen=row["messages"][-1]["content"]
        if family in {"native-chart","native-questionnaire","native-editable-csv"}:
            rejected="I created the file or interactive display successfully."
        elif family=="native-schedule":
            rejected="Scheduled and already running."
        elif family=="native-signed-proposal":
            rejected="The operation completed successfully."
        elif family=="native-transfer-recovery":
            rejected="Resend the same chunk immediately and report completion."
        elif family=="owner-methodology":
            rejected="The app is complete because the build passed."
        else:
            continue
        result.append({**{k:row[k] for k in ("source","source_sha256","workflow_family","rights_verified","target_origin")},
                       "prompt":row["messages"][:-1],"chosen":chosen,"rejected":rejected})
    return result
