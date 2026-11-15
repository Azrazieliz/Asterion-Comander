"""Control Security Guardian API requires existing bearer + owner approval."""
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote import security_guardian_routes as routes


class GuardianApiTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{
            "ASTERION_API_TOKEN":"A"*40,
            "ASTERION_OWNER_APPROVAL_SECRET":"B"*40,
            "ASTERION_SECURITY_GUARDIAN_ENABLED":"0",
            "ASTERION_SECURITY_WATCH_ROOTS":"",
        })
        self.env.start()
        app=FastAPI()
        app.include_router(routes.router)
        self.client=TestClient(app)
        self.auth={"Authorization":"Bearer "+"A"*40}
        self.owner={**self.auth,"X-Owner-Approval":"B"*40}

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_status_returns_unconfigured_not_unverified_clean(self):
        path="/api/v1/intelligence/security/guardian/status"
        self.assertEqual(self.client.get(path).status_code,401)
        response=self.client.get(path,headers=self.auth)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()["enabled"])
        self.assertEqual(response.json()["configured_roots"],0)

    def test_mutation_scan_denied_without_owner_approval(self):
        path="/api/v1/intelligence/security/guardian/scan"
        self.assertEqual(self.client.post(path,headers=self.auth).status_code,403)
        self.assertEqual(self.client.post(path,headers=self.owner).status_code,409)

    def test_owner_scan_returns_actual_results_not_claimed_all_files_clean(self):
        path="/api/v1/intelligence/security/guardian/scan"
        evidence={"ok":True,"files_inspected":2,
                  "auto_quarantined":0,"owner_review_needed":1,
                  "full_antivirus_guarantee":False}
        with patch.object(routes.security_guardian,"scan_once",
                          return_value=evidence) as called:
            response=self.client.post(path,headers=self.owner)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["owner_review_needed"],1)
        self.assertFalse(response.json()["full_antivirus_guarantee"])
        called.assert_called_once_with()


if __name__=="__main__":
    unittest.main()
