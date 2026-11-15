"""No-mock device effects: deterministic mixed-session validation and package predicates."""
import unittest
import httpx
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

    def test_assert_package_uses_semantic_phone_state(self):
        calls=[]
        def respond(request):
            calls.append(request.url.path)
            return httpx.Response(200,json={"foreground_package":"com.asterion.control"})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            result=perform(Step(kind="assert_package",text="com.asterion.control"),
                           "phone",client,{"Authorization":"Bearer non-secret"},
                           "http://127.0.0.1:9999")
        self.assertTrue(result["verified"])
        self.assertEqual(calls,["/ui"])

    def test_wait_package_checks_actual_transition(self):
        count=[0]
        def respond(request):
            count[0]+=1
            return httpx.Response(200,json={"foreground_package":
                "com.asterion.control" if count[0]>=2 else "com.android.launcher"})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            result=perform(Step(kind="await_package",text="com.asterion.control",wait_ms=750),
                           "phone",client,{}, "http://127.0.0.1:9999")
        self.assertTrue(result["verified"])
        self.assertGreaterEqual(count[0],2)

    def test_mismatch_does_not_fake_success(self):
        with httpx.Client(transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json={"foreground_package":"com.other"}))) as client:
            with self.assertRaises(AssertionError):
                perform(Step(kind="assert_package",text="com.asterion.control"),
                        "phone",client,{}, "http://127.0.0.1:9999")


if __name__=="__main__":
    unittest.main()
