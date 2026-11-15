"""Model Laboratory reusable free-release watcher with real database events."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from asterion_remote import model_lab, model_watch_service as watch


def fake_api(new_sha:str,status=200):
    def handle(request):
        assert request.url.host=="huggingface.co"
        assert request.url.path.startswith("/api/models/")
        body={"id":"Qwen/Qwen3.5-2B",
              "sha":new_sha,"cardData":{"license":"apache-2.0"},
              "gated":False,"lastModified":"2026-11-15T18:00:00Z"}
        return httpx.Response(status,json=body)
    return httpx.Client(transport=httpx.MockTransport(handle))


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            "ASTERION_MODEL_LAB_ROOT":self.tmp.name+"/lab",
            "ASTERION_MODEL_WATCH_ROOT":self.tmp.name+"/watch",
            "ASTERION_MODEL_WATCH_ENABLED":"0",
        })
        self.env.start()
        self.app="asterion-art"
        self.repo="Qwen/Qwen3.5-2B"
        self.base="a"*40
        self.new="b"*40
        model_lab.watch(self.app,self.repo,self.base)

    def tearDown(self):
        watch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_disabled_watcher_never_runs_network_at_startup(self):
        status=watch.start()
        self.assertFalse(status["enabled"])
        self.assertFalse(status["worker_running"])
        self.assertFalse(watch.status()["automatic_model_replacement"])

    def test_release_change_creates_single_actionable_evaluation_request(self):
        with fake_api(self.new) as client:
            result=watch.scan_once(client=client)
            self.assertEqual(result["scanned"],1)
            self.assertEqual(result["new_review_events"],1)
            self.assertEqual(result["models_replaced"],0)
            again=watch.scan_once(client=client)
            self.assertEqual(again["new_review_events"],0)
        state=watch.events()
        self.assertEqual(len(state["items"]),1)
        self.assertEqual(state["items"][0]["verdict"],"benchmark_required")
        self.assertTrue(state["needs_owner_intervention"])
        self.assertEqual(model_lab.list_models(self.app)["items"][0]
                         ["installed_sha"],self.base)

    def test_measured_improvement_requests_owner_review_not_auto_switch(self):
        proof=hashlib.sha256(b"real-benchmark-test-fixture").hexdigest()
        model_lab.benchmark(self.app,self.repo,self.base,
                task_score=.55,latency_ms=3000,ram_mb=1100,
                thermal_ok=True,verified=True,evidence_sha256=proof)
        model_lab.benchmark(self.app,self.repo,self.new,
                task_score=.72,latency_ms=3100,ram_mb=1130,
                thermal_ok=True,verified=True,evidence_sha256=proof)
        with fake_api(self.new) as client:
            result=watch.scan_once(client=client)
        self.assertEqual(result["new_review_events"],1)
        event=watch.events()["items"][0]
        self.assertEqual(event["verdict"],"owner_review_recommended")
        self.assertEqual(model_lab.list_models(self.app)["items"][0]
                         ["installed_sha"],self.base)
        ack=watch.acknowledge(event["id"])
        self.assertTrue(ack["acknowledged"])
        self.assertFalse(ack["model_replaced"])
        self.assertFalse(watch.events()["needs_owner_intervention"])

    def test_resource_regression_no_upgrade_or_owner_spam(self):
        proof="b"*64
        model_lab.benchmark(self.app,self.repo,self.base,
                task_score=.6,latency_ms=2000,ram_mb=1200,
                thermal_ok=True,verified=True,evidence_sha256=proof)
        model_lab.benchmark(self.app,self.repo,self.new,
                task_score=.8,latency_ms=2500,ram_mb=2200,
                thermal_ok=False,verified=True,evidence_sha256=proof)
        with fake_api(self.new) as client:
            result=watch.scan_once(client=client)
        self.assertEqual(result["new_review_events"],0)
        self.assertEqual(len(watch.events()["items"]),0)
        self.assertEqual(model_lab.list_models(self.app)["items"][0]
                         ["installed_sha"],self.base)

    def test_uninstalled_model_never_falsely_marks_upgrade_candidate(self):
        model_lab.watch(self.app,self.repo,installed_sha="")
        with fake_api(self.new) as client:
            result=watch.scan_once(client=client)
        self.assertFalse(result["results"][0]["update_candidate"])
        self.assertEqual(result["new_review_events"],0)

    def test_remote_api_failure_not_conflated_with_update(self):
        with fake_api(self.new,status=503) as client:
            result=watch.scan_once(client=client)
        self.assertFalse(result["results"][0]["ok"])
        self.assertEqual(result["new_review_events"],0)

    def test_acknowledge_invalid_event_does_not_fake_action(self):
        with self.assertRaises((KeyError,ValueError)):
            watch.acknowledge("invalid")

    def test_small_bounded_check_budget(self):
        with fake_api(self.new) as client:
            with self.assertRaises(ValueError):
                watch.scan_once(client=client,limit=1000)
            result=watch.scan_once(client=client,limit=1)
        self.assertEqual(result["scanned"],1)


if __name__=="__main__":
    unittest.main()
