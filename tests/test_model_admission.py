"""Quantized phone LLM admission uses real reported hardware budgets, no weights."""
from __future__ import annotations

import unittest

from asterion_remote.model_admission import Candidate,assess


def phone(**overrides):
    info={
        "device":"SM-S948B","android":"17",
        "memory_available":3_656_753_152,
        "memory_total":11_623_395_328,
        "storage_available":68_251_230_208,
        "battery":{"percent":48,"charging":True,"temperature_c":42.4},
        "thermals":{"status":2},
    }
    info.update(overrides)
    return {"paired":True,"reachable":True,"device":"SM-S948B","info":info}


def model(**overrides):
    fields=dict(repository="Qwen/Qwen3.5-2B",
                license_id="apache-2.0",
                weight_file_bytes=1_350_000_000,
                estimated_peak_ram_bytes=2_050_000_000,
                expected_context_tokens=4096,
                quantization="Q4_K_M",
                artifact_sha256="a"*64,
                original_author_verified=True)
    fields.update(overrides)
    return Candidate(**fields)


class ModelAdmissionTests(unittest.TestCase):
    def test_compact_model_could_enter_benchmark_but_is_not_loaded(self):
        state=assess(phone(),model())
        self.assertTrue(state["candidate_for_device_test"])
        self.assertEqual(state["status"],"READY_FOR_CONTROLLED_BENCHMARK")
        self.assertFalse(state["model_loaded"])
        self.assertFalse(state["model_trained"])
        self.assertFalse(state["inference_device_benchmarked"])
        self.assertIn("android_thermal_pressure_present",state["warnings"])

    def test_large_model_peak_does_not_fit_phone_current_free_ram(self):
        state=assess(phone(),model(
            weight_file_bytes=2_500_000_000,
            estimated_peak_ram_bytes=3_400_000_000))
        self.assertFalse(state["candidate_for_device_test"])
        self.assertIn("estimated_runtime_peak_exceeds_available_ram",
                      state["blockers"])

    def test_missing_runtime_peak_never_claims_load_ready(self):
        state=assess(phone(),model(estimated_peak_ram_bytes=None))
        self.assertFalse(state["candidate_for_device_test"])
        self.assertIn("quantized_runtime_peak_memory_not_measured",
                      state["warnings"])

    def test_missing_license_origin_or_hash_fails_closed(self):
        state=assess(phone(),model(
            license_id="unverified-custom",
            original_author_verified=False,artifact_sha256=""))
        self.assertFalse(state["candidate_for_device_test"])
        self.assertEqual(len([x for x in state["blockers"] if
            x in {"model_license_requires_owner_review",
                  "model_author_not_verified",
                  "model_artifact_hash_not_supplied"}]),3)

    def test_unreachable_device_cannot_fake_memory(self):
        state=assess({"paired":True,"reachable":False},model())
        self.assertFalse(state["candidate_for_device_test"])
        self.assertIn("paired_phone_unreachable",state["blockers"])
        self.assertIsNone(state["memory_available_bytes"])

    def test_low_battery_hot_phone_blocks_loading(self):
        p=phone(thermals={"status":5},
                battery={"percent":12,"charging":False})
        state=assess(p,model())
        self.assertIn("android_thermal_critical",state["blockers"])
        self.assertIn("battery_too_low_for_model_load",state["blockers"])

    def test_large_context_requires_measurement_and_caution(self):
        state=assess(phone(),model(expected_context_tokens=32768))
        self.assertIn("large_context_requires_real_kv_cache_measurement",
                      state["warnings"])

    def test_store_insufficient_blocks_staged_replacement(self):
        state=assess(phone(storage_available=1_000_000_000),model())
        self.assertIn("insufficient_storage_for_staged_model_and_rollback",
                      state["blockers"])


if __name__=="__main__":
    unittest.main()
