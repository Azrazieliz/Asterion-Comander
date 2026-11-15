"""Phone-first continuation and observation contracts on the retained native route.

The retired public MCP discovery/tool interface is intentionally NOT imported.
These are routing/security tests; real Samsung acceptance is a separate gate.
"""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from asterion_remote.app import app
from asterion_remote import native_routes, github_bridge, phone_bridge


PAYLOAD = {
    "project": "Asterion-Game",
    "checkpoint_id": "phase7-checkpoint001",
    "priority_tier": "7*",
    "spec_reference": "7STAR_FROZEN_MASTER.md",
    "message": "Continue from the saved progress ledger without changing scope.",
}


class Reply:
    def __init__(self, value):
        self.value=value

    def json(self):
        return self.value


class NativeContinuationTests(unittest.TestCase):
    def test_continuation_observer_and_voice_require_authentication(self):
        with TestClient(app) as client:
            for path in (
                "/api/v1/phone/continuation/status",
                "/api/v1/phone/observation/status",
                "/api/v1/phone/observation/events",
                "/api/v1/phone/observation/frame",
                "/api/v1/phone/voice/status",
                "/api/v1/phone/bridge/status",
                "/api/v1/phone/apps",
            ):
                self.assertEqual(client.get(path).status_code, 401)
            for path,body in (
                ("/api/v1/phone/continuation/queue",PAYLOAD),
                ("/api/v1/phone/continuation/dispatch",{}),
                ("/api/v1/phone/voice/question",{"text":"Question"}),
                ("/api/v1/phone/apps/launch",{"package":"com.gamepilot"}),
                ("/api/v1/phone/continuation/ack",
                 {"checkpoint_id":"abc","response_receipt":"observed-next-chat-turn"}),
            ):
                self.assertEqual(client.post(path,json=body).status_code,401)

    def test_checkpoint_schema_and_rank_validation(self):
        self.assertEqual(native_routes.ContinuationRequest(**PAYLOAD).priority_tier,"7*")
        for mutation in ({"priority_tier":"critical"},{"message":""},
                         {"message":"x"*4000}):
            with self.subTest(mutation=list(mutation)):
                with self.assertRaises(ValidationError):
                    native_routes.ContinuationRequest(**{**PAYLOAD, **mutation})

    def test_private_bridge_contains_continuation_and_observer_operations(self):
        operations=set(github_bridge.ALLOWED)|set(github_bridge.PHONE_NATIVE)
        expected={
            "phone_continuation_status", "phone_continuation_queue",
            "phone_continuation_dispatch", "phone_observation_status",
            "phone_observation_events", "phone_observation_frame",
            "phone_voice_status", "phone_voice_question",
            "phone_bridge_status", "phone_apps", "phone_app_launch",
            "phone_continuation_ack", "phone_continuation_cancel",
        }
        self.assertTrue(expected.issubset(operations))

    def test_authorized_native_dispatch_uses_bounded_existing_phone_paths(self):
        calls=[]
        def fake(path,method="GET",payload=None,timeout=5):
            calls.append((path,method,payload))
            return Reply({"ok":True,"state":"queued"})
        with patch.object(native_routes,"request",side_effect=fake):
            result=native_routes.phone_continuation_queue(
                native_routes.ContinuationRequest(**PAYLOAD))
            self.assertEqual(result["state"],"queued")
            native_routes.phone_observation_status()
            native_routes.phone_voice_question(
                native_routes.VoiceQuestion(text="What happened?"))
            native_routes.phone_continuation_dispatch()
        self.assertEqual([call[0] for call in calls],
                         ["/continuation/queue","/observation/status",
                          "/voice/question","/continuation/dispatch"])
        self.assertEqual(calls[0][1],"POST")
        self.assertEqual(calls[0][2]["checkpoint_id"],PAYLOAD["checkpoint_id"])

    def test_new_chat_ack_and_app_launch_are_not_claimed_verified(self):
        with self.assertRaises(ValidationError):
            native_routes.AppLaunch(package="bad package")
        with self.assertRaises(ValidationError):
            native_routes.CheckpointAcknowledgment(
                checkpoint_id="abc",response_receipt="short")
        observations=[]
        with patch.object(native_routes,"request",side_effect=lambda path,
                          method="GET",payload=None,timeout=5: (
                            observations.append((path,method,payload)) or
                            Reply({"requested":True,"verified_new_chat":False}))):
            result=native_routes.phone_chat_new()
            native_routes.phone_app_launch(native_routes.AppLaunch(
                package="com.onemt.and.shoujokaisen"))
        self.assertTrue(result["requested"])
        self.assertFalse(result["verified_new_chat"])
        self.assertEqual(observations[0][0],"/chat/new")
        self.assertEqual(observations[1][0],"/apps/launch")

    def test_observation_frame_path_is_scoped_to_receipt_images(self):
        with patch.object(phone_bridge,"load",return_value=None):
            with self.assertRaises(HTTPException) as invalid:
                phone_bridge.request("/observation/frame/../private")
            self.assertEqual(invalid.exception.status_code,400)
            with self.assertRaises(HTTPException) as unavailable:
                phone_bridge.request("/observation/frame/frame-1793804400000.jpg")
            self.assertEqual(unavailable.exception.status_code,503)

    def test_voice_and_bridge_receipt_do_not_disclose_credentials(self):
        with self.assertRaises(ValidationError):
            native_routes.VoiceQuestion(text="")
        with self.assertRaises(ValidationError):
            native_routes.VoiceQuestion(text="x"*701)
        with patch.object(native_routes,"request",
                          return_value=Reply({"enabled":True,"completed":3})):
            state=native_routes.phone_bridge_status()
        self.assertEqual(state["completed"],3)
        self.assertNotIn("token",state)


if __name__ == "__main__":
    unittest.main()
