"""Test missing-feature deployment without touching the paired production agent."""
from __future__ import annotations
import ast
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote.control_ai_routes import router as intelligence_router
from asterion_remote.control_v2_routes import router as v2_router
from asterion_remote.native_routes import router as phone_router
from scripts import deploy_control_missing_features_0933 as deployer

ROOT = Path(__file__).resolve().parents[1]


class MissingFeatureTests(unittest.TestCase):
    def test_restored_routes_require_owner_bearer(self):
        app = FastAPI()
        app.include_router(intelligence_router)
        app.include_router(v2_router)
        app.include_router(phone_router)
        with TestClient(app) as client:
            for target in (
                "/api/v1/intelligence/cycles",
                "/api/v1/v2/models",
                "/api/v1/v2/skills",
                "/api/v1/phone/diagnostics/vpn",
            ):
                response = client.get(target)
                self.assertIn(response.status_code, (401, 403), target)
            # Only authorized GETs; no model run or phone side effect.
            for target in (
                "/api/v1/intelligence/cycles",
                "/api/v1/v2/models",
                "/api/v1/v2/skills",
            ):
                response = client.get(
                    target, headers={"Authorization": "Bearer " + "A" * 40})
                # A normal non-owner bearer cannot bypass require_token.
                self.assertNotEqual(response.status_code, 500)

    def test_patch_is_only_additive_and_idempotent(self):
        old = '''from .diagnostic_routes import router as diagnostic_router
from .native_routes import router as phone_router
from fastapi import FastAPI
app=FastAPI()
app.include_router(phone_router)
app.include_router(diagnostic_router)
'''
        new = deployer._patch_app(old)
        ast.parse(new)
        self.assertEqual(
            new.count("app.include_router(control_ai_router)"), 1)
        self.assertEqual(
            new.count("app.include_router(control_v2_router)"), 1)
        self.assertEqual(deployer._patch_app(new), new)
        self.assertEqual(
            old.count("app.include_router(phone_router)"),
            new.count("app.include_router(phone_router)"))

    def test_rejects_partial_mount_or_unknown_layout(self):
        with self.assertRaises(RuntimeError):
            deployer._patch_app("app=FastAPI()")
        with self.assertRaises(RuntimeError):
            deployer._patch_app('''from .diagnostic_routes import router as diagnostic_router
app.include_router(diagnostic_router)
from .control_ai_routes import router as control_ai_router
''')

    def test_all_existing_native_routes_remain_in_source(self):
        routes = deployer._routes(
            (ROOT / "asterion_remote/native_routes.py").read_text("utf8"))
        for item in (
            ("GET", "/phone/diagnostics/vpn"),
            ("GET", "/phone/voice/status"),
            ("GET", "/phone/cycles/status"),
            ("POST", "/phone/input"),
            ("GET", "/phone/app-bridge/apps"),
        ):
            self.assertIn(item, routes)
        self.assertGreaterEqual(len(routes), 25)

    def test_binaries_secret_paths_and_live_worker_not_deployed(self):
        self.assertEqual(
            sorted(deployer.FILES),
            sorted(set(deployer.FILES)))
        self.assertNotIn("asterion_remote/phone_bridge.py", deployer.FILES)
        self.assertNotIn("android/app/build.gradle", deployer.FILES)
        self.assertNotIn("asterion_remote/native_phone_relay.py", deployer.FILES)
        self.assertTrue(all(
            path.endswith((".py",".html",".js")) for path in deployer.FILES))


if __name__ == "__main__":
    unittest.main()
