"""Local preference optimization anchored to the completed SFT adapter."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path


def read_preferences(path, train, holdout):
    """Keep whole workflow families out of both SFT and preference training."""
    from scripts.control_ai_adaptation import digest

    reserved = {key for key, _ in holdout}
    held_families = {row.get("workflow_family") for _, row in holdout}
    if None in held_families or any(not isinstance(family, str) or not family.strip() for family in held_families):
        raise ValueError("preference_training_requires_holdout_workflow_families")
    training_families = {row.get("workflow_family") for _, row in train}
    if None in training_families or training_families & held_families:
        raise ValueError("train_and_holdout_workflow_families_must_be_disjoint")

    rows, seen = [], set()
    with Path(path).open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            messages = row.get("prompt")
            if row.get("rights_verified") is not True or not str(row.get("source", "")).strip():
                raise ValueError("preference_requires_rights_and_provenance")
            family = row.get("workflow_family")
            if not isinstance(family, str) or not family.strip() or family in held_families:
                raise ValueError("preference_workflow_contaminates_holdout")
            if not isinstance(messages, list) or not messages:
                raise ValueError("preference_prompt_missing")
            for message in messages:
                if not isinstance(message, dict) or set(message) != {"role", "content"} or not isinstance(message["content"], str) or not message["content"].strip():
                    raise ValueError("invalid_preference_message")
            roles = [message["role"] for message in messages]
            if roles[0] == "system":
                roles = roles[1:]
            if roles != ["user", "assistant"] * (len(roles) // 2) + ["user"]:
                raise ValueError("invalid_preference_roles")
            key = digest(" ".join(messages[-1]["content"].casefold().split()))
            if key in reserved or key in seen:
                raise ValueError("preference_prompt_contamination")
            chosen, rejected = row.get("chosen"), row.get("rejected")
            if not all(isinstance(value, str) and value.strip() for value in (chosen, rejected)) or chosen.strip() == rejected.strip():
                raise ValueError("preference_pair_requires_distinct_outputs")
            seen.add(key)
            rows.append(row)
    if not rows:
        raise ValueError("empty_preference_corpus")
    return rows


def optimize(model, tokenizer, rows, *, context, steps, learning_rate, beta):
    from scripts.control_ai_adaptation import encode
    import torch
    import torch.nn.functional as functional

    device = model.get_input_embeddings().weight.device

    def answer_log_probability(sample):
        ids = torch.tensor([sample["input_ids"]], device=device)
        logits = model(input_ids=ids, use_cache=False).logits[0, :-1]
        labels = torch.tensor(sample["labels"][1:], device=logits.device)
        selected = labels != -100
        return -functional.cross_entropy(logits[selected].float(), labels[selected], reduction="sum")

    # Only the deterministic optimizer schedule needs reference scores.
    # Cache these from the immutable SFT state BEFORE any optimizer update.
    # In a short CPU run, computing unused pairs previously consumed most
    # of the wall-clock budget without contributing a gradient.
    if steps<1 or not rows:
        raise ValueError("empty_preference_schedule")
    rng = random.Random(42)
    order = list(range(len(rows)))
    scheduled = []
    for step in range(steps):
        if step % len(order) == 0:
            rng.shuffle(order)
        scheduled.append(order[step % len(order)])
    pairs = {}
    model.eval()
    with torch.no_grad():
        for index in dict.fromkeys(scheduled):
            row=rows[index]
            chosen = encode(tokenizer, row["prompt"] + [{"role": "assistant", "content": row["chosen"]}], context)
            rejected = encode(tokenizer, row["prompt"] + [{"role": "assistant", "content": row["rejected"]}], context)
            reference = float(answer_log_probability(chosen) - answer_log_probability(rejected))
            if not math.isfinite(reference):
                raise RuntimeError("nonfinite_reference_log_ratio")
            pairs[index]=(chosen, rejected, reference)
            print(json.dumps({"phase":"preference_reference","pair_index":index,
                "cached_pairs":len(pairs),"scheduled_pairs":len(set(scheduled))}),flush=True)

    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=learning_rate,
    )
    # Eval mode disables dropout and leaves Autograd enabled. With sequential
    # backwards only one response graph is resident at a time.
    total_loss = 0.0
    for step,index in enumerate(scheduled):
        chosen, rejected, reference = pairs[index]
        with torch.no_grad():
            # Step zero uses the exact frozen reference weights. No repeat
            # forward pass is needed to know the preference logit is zero.
            logit = torch.tensor(0.0,device=device) if step==0 else beta * (
                answer_log_probability(chosen) - answer_log_probability(rejected) - reference)
            loss = -functional.logsigmoid(logit)
            slope = -beta * torch.sigmoid(-logit)
        if not torch.isfinite(loss):
            raise RuntimeError("nonfinite_preference_loss")
        optimizer.zero_grad(set_to_none=True)
        (slope * answer_log_probability(chosen)).backward()
        (-slope * answer_log_probability(rejected)).backward()
        torch.nn.utils.clip_grad_norm_(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            1.0,
            error_if_nonfinite=True,
        )
        optimizer.step()
        total_loss += float(loss)
        print(json.dumps({"phase":"preference_optimizer_step","step":step+1,"total_steps":steps,
            "pair_index":index,"loss":float(loss)}),flush=True)
    return {"method": "dpo", "reference": "completed_sft_adapter", "steps": steps,
            "beta": beta, "pair_count": len(rows), "reference_pairs":len(pairs),
            "scheduled_pair_indices":scheduled,"mean_loss": total_loss / steps}
