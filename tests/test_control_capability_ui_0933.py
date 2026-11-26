"""Control capability surface: status remains truthful and native navigation is unified."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote.control_ai_routes import router as intelligence

ROOT = Path(__file__).resolve().parents[1]
JAVA = (ROOT/"android/app/src/main/java/com/asterion/control/MainActivity.java")


class CapabilitySurfaceTests(unittest.TestCase):
    def test_unconfigured_local_inference_is_not_marked_running(self):
        with patch.dict(os.environ, {
            "ASTERION_LOCAL_MODEL_ENDPOINT": "",
            "ASTERION_LOCAL_MODEL_ID": "",
            "ASTERION_API_TOKEN": "B"*40,
        }):
            app=FastAPI()
            app.include_router(intelligence)
            with TestClient(app) as client:
                noauth=client.get("/api/v1/intelligence/capabilities")
                self.assertIn(noauth.status_code,(401,403))
                r=client.get("/api/v1/intelligence/capabilities",
                             headers={"Authorization": "Bearer " + "B"*40})
                self.assertEqual(r.status_code,200)
                data=r.json()
                self.assertTrue(data["ok"])
                self.assertFalse(data["local_model_configured"])
                self.assertFalse(data["local_model_reachable_verified"])
                self.assertFalse(data["work_executor_bound"])
                self.assertFalse(data["automatic_project_work_running"])
                self.assertFalse(data["paid_cloud_fallback"])
                self.assertNotIn("endpoint",str(data).lower())

    def test_invalid_local_endpoint_does_not_claim_ready(self):
        with patch.dict(os.environ, {
            "ASTERION_LOCAL_MODEL_ENDPOINT": "https://example.com/v1/chat/completions",
            "ASTERION_LOCAL_MODEL_ID": "local",
        }):
            from asterion_remote.control_ai_routes import capabilities
            result=capabilities()
            self.assertFalse(result["local_model_configured"])

    def test_all_previous_native_features_have_one_owner_screen(self):
        source=JAVA.read_text("utf8")
        self.assertIn('private final View[] pages=new View[5]',source)
        self.assertIn('pages[4]=scrollTools()',source)
        self.assertIn('String[] names={"Home","Screen","Health","Connect","Tools"}',source)
        self.assertIn('private View scrollTools()',source)
        tools=source.split('private View scrollTools()',1)[1].split(
            'private void showWindowsIntelligence()',1)[0]
        connect=source.split('private View scrollDevices()',1)[1].split(
            'private View scrollTools()',1)[0]
        for item in ("Asterion voice","Connected applications",
                     "Direct Wi-Fi file transfer","Asterion Control updates"):
            self.assertIn(item,tools)
            self.assertNotIn(item,connect)
        for item in ("Asterion intelligence","Incident investigation","Network & privacy"):
            self.assertIn(item,tools)
        self.assertIn('this::showPhoneAiChat',tools)
        self.assertIn('this::showPhoneAiStatus',tools)
        self.assertIn('private void showWindowsIntelligence()',source)
        self.assertIn('"/api/v1/intelligence/capabilities"',source)
        self.assertIn('new Intent(this,AssistantActivity.class)',source)
        workspace=(ROOT/"android/app/src/main/java/com/asterion/control/AssistantActivity.java").read_text("utf8")
        session=(ROOT/"android/app/src/main/java/com/asterion/control/AssistantSession.java").read_text("utf8")
        self.assertIn('session.send(this,prompt)',workspace)
        self.assertIn('OnDeviceLlm.generate(app,target.project,target.modelMessages()',session)

    def test_embedded_windows_navigation_not_duplicated(self):
        text=JAVA.read_text("utf8")
        self.assertIn(".authbar,.notice,.tabs{display:none!important}",text)
        for item in ('showRemoteSection("desktop")',
                     'showRemoteSection("android")',
                     'showRemoteSection("diagnostics")'):
            self.assertIn(item,text)
        self.assertIn("showPage(",text)
        self.assertIn("JSONObject.quote(pendingRemoteSection)",text)


if __name__ == "__main__":
    unittest.main()
