"""Real primary WSS adapter and deterministic mixed-session validation."""
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from asterion_remote.interaction_sessions import SessionRequest, Step, perform


class MixedSessionTests(unittest.TestCase):
    def test_mixed_requires_explicit_target_for_every_step(self):
        with self.assertRaises(ValidationError):
            SessionRequest(device="mixed",steps=[Step(kind="health")])
        with self.assertRaises(ValidationError):
            SessionRequest(device="phone",steps=[Step(kind="health",device="pc")])
        with self.assertRaises(ValidationError):
            SessionRequest(device="mixed",steps=[Step(kind="assert_package",
                device="pc",text="com.openai.chatgpt")])

    def test_verified_mixed_session_is_valid(self):
        request=SessionRequest(device="mixed",steps=[
            Step(kind="window",device="pc"),
            Step(kind="assert_package",device="phone",text="com.asterion.control"),
            Step(kind="health",device="pc")])
        self.assertEqual(len(request.steps),3)
        self.assertEqual(request.steps[1].device,"phone")

    def test_assert_package_uses_primary_phone_bridge_not_lan(self):
        calls=[]
        def wss(path,method="GET",payload=None,timeout=5.0):
            calls.append((path,method))
            return httpx.Response(200,json={"foreground_package":"com.asterion.control"})
        with patch("asterion_remote.interaction_sessions.phone_request",side_effect=wss):
            result=perform(Step(kind="assert_package",text="com.asterion.control"),"phone")
        self.assertTrue(result["verified"])
        self.assertEqual(calls,[("/ui","GET")])

    def test_wait_package_checks_actual_transition(self):
        count=[0]
        def wss(path,method="GET",payload=None,timeout=5.0):
            count[0]+=1
            return httpx.Response(200,json={"foreground_package":
                "com.asterion.control" if count[0]>=2 else "com.android.launcher"})
        with patch("asterion_remote.interaction_sessions.phone_request",side_effect=wss):
            result=perform(Step(kind="await_package",
                text="com.asterion.control",wait_ms=750),"phone")
        self.assertTrue(result["verified"])
        self.assertGreaterEqual(count[0],2)

    def test_mismatch_does_not_fake_success(self):
        with patch("asterion_remote.interaction_sessions.phone_request",
                   return_value=httpx.Response(200,json={"foreground_package":"com.other"})):
            with self.assertRaises(AssertionError):
                perform(Step(kind="assert_package",
                             text="com.asterion.control"),"phone")

    def test_phone_mutation_uses_primary_adapter_exactly_once(self):
        events=[]
        def wss(path,method="GET",payload=None,timeout=5.0):
            events.append((path,method,payload))
            return httpx.Response(200,json={"ok":True})
        with patch("asterion_remote.interaction_sessions.phone_request",side_effect=wss):
            r=perform(Step(kind="input",payload={"action":"back"}),"phone")
        self.assertEqual(r,{"ok":True,"action":"back"})
        self.assertEqual(events,[("/input","POST",{"action":"back"})])

    def test_unknown_wss_post_outcome_never_replayed(self):
        events=[]
        def uncertain(path,method="GET",payload=None,timeout=5.0):
            events.append((path,method))
            raise HTTPException(503,"native phone outcome unknown")
        with patch("asterion_remote.interaction_sessions.phone_request",side_effect=uncertain):
            with self.assertRaises(HTTPException):
                perform(Step(kind="input",payload={"action":"back"}),"phone")
        self.assertEqual(events,[("/input","POST")])

    def test_session_does_not_build_second_private_lan_client(self):
        source=(Path(__file__).resolve().parents[1]/
                "asterion_remote"/"interaction_sessions.py").read_text("utf8")
        self.assertIn("request as phone_request",source)
        self.assertNotIn("httpx.Client(",source)
        self.assertNotIn("pairing['base_url']+path",source)


if __name__=="__main__":
    unittest.main()
