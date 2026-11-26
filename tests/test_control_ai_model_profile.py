"""Structural, non-device regressions for signed native inference profiles.

These checks do not claim inference, reasoning quality or an installed Android release.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "android/app/src/main/cpp/on_device_llm.cpp"
JAVA = ROOT / "android/app/src/main/java/com/asterion/control"
MANIFEST = ROOT / "android/app/src/main/assets/models/control-model.json"


def test_model_profile_has_signed_asset_hash_and_reasonable_budgets():
    profile = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert profile["file"].endswith(".gguf")
    assert profile["bytes"] > 1_000_000
    assert len(profile["sha256"]) == 64
    assert profile["max_input_chars"] > 1800
    assert profile["max_new_tokens"] > 192
    assert profile["context_tokens"] >= profile["max_new_tokens"] + 256
    assert all(profile["chat_format"][k] for k in
               ("system_prefix", "user_prefix", "assistant_prefix"))
    assert "/no_think" not in profile["system_text"]
    assert "cannot autonomously operate" not in profile["system_text"].lower()


def test_on_device_loader_uses_profile_not_named_vendor_constants():
    source = (JAVA / "OnDeviceLlm.java").read_text(encoding="utf-8")
    assert "OnDeviceModelProfile.read(context)" in source
    assert "profile.prompt(userPrompt)" in source
    assert "profile.outputTokens,profile.contextTokens" in source
    assert "profile.sha256.equals(hex(digest.digest()))" in source
    assert "on_device_inference_already_running" in source
    assert "/no_think" not in source
    assert "MODEL_FILE=" not in source
    assert "Qwen3-0.6B" not in source


def test_jni_preserves_cancellation_and_rejects_context_overflow():
    code = NATIVE.read_text(encoding="utf-8")
    assert "jint context_limit" in code
    assert "limit>2048" in code
    assert "prompt.size()>262144" in code
    assert "tokens.size()+static_cast<size_t>(limit)+32u" in code
    assert "cp.n_ctx=context_limit;" in code
    assert "cancel_generation.load" in code
    assert "n_gpu_layers=0" in code  # fallback remains CPU; GPU acceleration unverified


def test_jobs_keep_durable_receipt_before_work_and_use_profile_budget():
    source = (JAVA / "OnDeviceAiJobs.java").read_text(encoding="utf-8")
    assert "OnDeviceModelProfile.read(ctx).inputChars" in source
    assert "prompt.length()>maxInputChars" in source
    assert "persist(ctx,job);" in source
    assert "EXECUTOR.submit(()->execute(app,job,prompt));" in source
    assert "OnDeviceLlm.generate(ctx,prompt)" in source
    assert "previous_process_outcome_unavailable" in source
