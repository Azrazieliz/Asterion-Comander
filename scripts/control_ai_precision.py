"""Describe precision experiments against an actual Android memory receipt."""

import argparse
import json
from pathlib import Path


def assess(parameters, available_bytes, context, kv_per_token, workspace, reserve):
    if min(parameters, available_bytes, context) <= 0 or min(kv_per_token, workspace, reserve) < 0:
        raise ValueError("invalid_precision_admission_inputs")
    overhead = context * kv_per_token + workspace + reserve
    rows = []
    for label, numerator, denominator, backend_artifact in (
        ("bf16_reference", 2, 1, "BF16"),
        ("fp16_reference", 2, 1, "F16"),
        ("12_bit_theoretical", 3, 2, None),
        ("int8_ideal", 1, 1, "Q8_0_with_block_overhead"),
    ):
        weights = (parameters * numerator + denominator - 1) // denominator
        rows.append({
            "precision": label,
            "backend_artifact": backend_artifact,
            "weight_only_lower_bound_bytes": weights,
            "minimum_accounted_bytes": weights + overhead,
            "lower_bound_fits_sample": weights + overhead <= available_bytes,
            "android_measured": False,
        })
    return {"parameters": parameters, "available_bytes_sample": available_bytes,
            "context_tokens": context, "kv_bytes_per_token_assumed": kv_per_token,
            "workspace_bytes_assumed": workspace, "minimum_reserve_bytes_assumed": reserve,
            "experiments": rows, "phone_fit_certified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--parameters", required=True, type=int)
    parser.add_argument("--context", type=int, default=4096)
    parser.add_argument("--kv-bytes-per-token", required=True, type=int)
    parser.add_argument("--workspace-mib", type=int, default=512)
    parser.add_argument("--reserve-mib", type=int, default=384)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if receipt.get("status") != "complete" or receipt.get("ok") is not True:
        raise ValueError("completed_phone_receipt_required")
    phone = receipt["result"]
    if phone.get("device") != "SM-S948B":
        raise ValueError("expected_sm_s948b_receipt")
    outcome = assess(args.parameters, phone["memory_available"], args.context,
                     args.kv_bytes_per_token, args.workspace_mib << 20, args.reserve_mib << 20)
    outcome["receipt_id"] = receipt["id"]
    print(json.dumps(outcome, indent=2))


if __name__ == "__main__":
    main()
