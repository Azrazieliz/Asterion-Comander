"""Control V2: scanning coverage, quarantine integrity, model evidence and skills."""
import hashlib
import io
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote import security_scanner,model_lab,skill_studio
from asterion_remote.control_v2_routes import router


class ControlV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{
            "ASTERION_API_TOKEN":"T"*40,
            "ASTERION_OWNER_APPROVAL_SECRET":"O"*40,
            "ASTERION_MODEL_LAB_ROOT":str(self.root/"model"),
            "ASTERION_SKILL_STUDIO_ROOT":str(self.root/"skills"),
            "ASTERION_QUARANTINE_ROOT":str(self.root/"quarantine"),
            "ASTERION_DIAGNOSTIC_ROOT":str(self.root/"diagnostic"),
        })
        self.env.start()
        self.auth={"Authorization":"Bearer "+"T"*40}
        self.owner={**self.auth,"X-Owner-Approval":"O"*40}
        self.patcher=patch("asterion_remote.app.ROOT",self.root)
        self.patcher.start()
        app=FastAPI()
        app.include_router(router)
        self.client=TestClient(app)

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_no_antivirus_does_not_claim_clean(self):
        f=self.root/"sample.txt"
        f.write_text("hello harmless example")
        output=security_scanner.scan(f,level="standard",antivirus="")
        self.assertTrue(output["ok"])
        self.assertEqual(output["verdict"],"incomplete")
        self.assertEqual(output["antivirus"],"not_available")
        self.assertFalse(output["safe_guarantee"])
        quick=security_scanner.scan(f,level="quick",antivirus="")
        self.assertEqual(quick["verdict"],"no_known_threat_detected")

    def test_auto_deep_risky_and_detects_zip_traversal(self):
        f=self.root/"test.apk"
        with zipfile.ZipFile(f,"w") as out:
            out.writestr("../outside.exe","test")
        result=security_scanner.scan(f,level="auto",antivirus="")
        self.assertEqual(result["profile"],"deep")
        self.assertEqual(result["verdict"],"suspicious")
        self.assertIn("archive_path_traversal",result["findings"])

    def test_quarantine_hash_bound_and_reversible(self):
        f=self.root/"sample.exe"
        f.write_bytes(b"MZ"+b"X"*1024)
        expected=hashlib.sha256(f.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            security_scanner.quarantine(f,self.root/"quarantine","0"*64)
        result=security_scanner.quarantine(f,self.root/"quarantine",expected)
        self.assertFalse(f.exists())
        self.assertEqual(len(security_scanner.inventory(self.root/"quarantine")["items"]),1)
        restored=security_scanner.restore(result["id"],self.root/"quarantine")
        self.assertEqual(restored["sha256"],expected)
        self.assertEqual(f.read_bytes(),b"MZ"+b"X"*1024)

    def test_auth_required_and_separate_owner_approval(self):
        f=self.root/"data.bin"
        f.write_bytes(b"hello")
        data={"path":"data.bin","file_sha256":hashlib.sha256(f.read_bytes()).hexdigest()}
        self.assertEqual(self.client.post("/api/v1/v2/security/scan",
            json={"path":"data.bin"}).status_code,401)
        scan=self.client.post("/api/v1/v2/security/scan",
            headers=self.auth,json={"path":"data.bin"})
        self.assertEqual(scan.status_code,200)
        self.assertEqual(scan.json()["verdict"],"incomplete")
        self.assertEqual(self.client.post("/api/v1/v2/security/quarantine",
            headers=self.auth,json=data).status_code,403)
        moved=self.client.post("/api/v1/v2/security/quarantine",
            headers=self.owner,json=data)
        self.assertEqual(moved.status_code,200)
        self.assertFalse(f.exists())
        restore=self.client.post("/api/v1/v2/security/quarantine/restore",
            headers=self.owner,json={"quarantine_id":moved.json()["id"]})
        self.assertEqual(restore.status_code,200)
        self.assertTrue(f.exists())

    def test_model_watch_and_evidence_only_recommendation(self):
        app,repo="asterion-art","example-org/Model-7B"
        old="a"*40;new="b"*40
        model_lab.watch(app,repo,old)
        class Response:
            content=b"{}"
            def raise_for_status(self):return None
            def json(self):return {"id":repo,"sha":new,
                "lastModified":"2026-11-15T15:00:00Z",
                "cardData":{"license":"apache-2.0"},
                "gated":False,"safetensors":{"total":2048}}
        class Client:
            def get(self,url):
                assert url=="https://huggingface.co/api/models/"+repo
                return Response()
        result=model_lab.refresh(app,repo,client=Client())
        self.assertTrue(result["update_candidate"])
        self.assertEqual(model_lab.recommendations(app)["items"][0]["verdict"],
                         "benchmark_required")
        ev="c"*64
        model_lab.benchmark(app,repo,old,.75,300,1100,True,True,ev)
        model_lab.benchmark(app,repo,new,.81,260,1120,True,True,ev)
        advice=model_lab.recommendations(app)["items"][0]
        self.assertEqual(advice["verdict"],"owner_review_recommended")
        self.assertFalse(advice["automatic_update"])

    def test_skill_approval_hash_and_replay(self):
        doc=skill_studio.create("test_health","Get existing Windows health",
            "pc",[{"kind":"health"}])
        self.assertEqual(doc["state"],"draft")
        with self.assertRaises(PermissionError):
            skill_studio.execute("test_health",doc["sha256"],"request-12345")
        self.assertEqual(self.client.post("/api/v1/v2/skills/test_health/approve",
            headers=self.auth,json={"sha256":doc["sha256"]}).status_code,403)
        yes=self.client.post("/api/v1/v2/skills/test_health/approve",
            headers=self.owner,json={"sha256":doc["sha256"]})
        self.assertEqual(yes.status_code,200)
        first=skill_studio.execute("test_health",doc["sha256"],"request-12345")
        repeat=skill_studio.execute("test_health",doc["sha256"],"request-12345")
        self.assertEqual(first["session"]["id"],repeat["session"]["id"])
        self.assertTrue(repeat["session"]["reused"])
        self.assertEqual(skill_studio.details("test_health")["executions"],1)
        # start() schedules the native session executor asynchronously. It may
        # still hold the per-test SQLite database when TemporaryDirectory exits
        # on Windows. Consume its terminal receipt before destroying the DB.
        from asterion_remote import interaction_sessions
        terminal={"completed","failed","cancelled","timed_out","outcome_unknown"}
        settled=None
        for _ in range(120):
            settled=interaction_sessions.status(first["session"]["id"])
            if settled["state"] in terminal:break
            time.sleep(0.05)
        self.assertIn(settled["state"],terminal)
        skill_studio.revoke("test_health")
        with self.assertRaises(PermissionError):
            skill_studio.execute("test_health",doc["sha256"],"request-67890")


if __name__=="__main__":
    unittest.main()
