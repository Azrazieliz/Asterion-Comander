"""Real-output evaluation accounting; no training, download or cloud provider."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion_remote import model_evaluation as ev


class ModelEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{"ASTERION_MODEL_EVAL_ROOT":self.tmp.name})
        self.env.start()
        self.root=Path(self.tmp.name)
        self.data=self.root/"holdout.jsonl"

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self,rows):
        self.data.write_text("".join(json.dumps(x)+"\n" for x in rows),
                             encoding="utf-8")
        return self.data

    def case(self,ident,expected,mode="exact",category="reasoning",**kw):
        return {"id":ident,"split":"holdout","category":category,
                "mode":mode,"prompt":"Solve this known-source evaluation problem",
                "expected":expected,**kw}

    def provider(self,prompt,request_id):
        self.assertTrue(request_id.startswith("eval-"))
        return {"message_id":"genuine-local-req-001",
                "content":"Actual local response"}

    def test_empty_invalid_and_duplicate_are_not_passed(self):
        self.data.write_text("")
        with self.assertRaises(ValueError):
            ev.inspect(self.data)
        a=self.case("case-00001","Actual local response")
        self.write([a,a])
        with self.assertRaises(ValueError):
            ev.inspect(self.data)
        self.write([{**a,"split":"train"}])
        with self.assertRaises(ValueError):
            ev.inspect(self.data)

    def test_batch_executes_provider_and_persists_real_scores(self):
        self.write([self.case("case-00001","Actual local response"),
                    self.case("case-00002","incorrect expected")])
        first=ev.run_batch(self.data,"model-a",self.provider,batch_limit=1)
        self.assertEqual(first["assessed"],1)
        self.assertEqual(first["passed"],1)
        self.assertEqual(first["remaining"],1)
        second=ev.run_batch(self.data,"model-a",self.provider,batch_limit=1)
        self.assertEqual(second["passed"],1)
        self.assertEqual(second["failed"],1)
        self.assertEqual(second["verified_accuracy"],.5)
        self.assertTrue(second["fully_evaluated"])
        self.assertFalse(second["model_weights_trained"])
        again=ev.run_batch(self.data,"model-a",self.provider,batch_limit=1)
        self.assertEqual(again["assessed"],2)

    def test_json_subset_and_numeric_tolerance(self):
        rows=[self.case("case-00003",{"ok":True},"json_subset",
                        prompt="Return a JSON result"),
              self.case("case-00004","1.25","numeric",tolerance="0.02")]
        self.write(rows)
        def provider(prompt,ident):
            return {"content":
                    '{"ok":true,"extra":"unused"}'
                    if "JSON" in prompt else "1.26"}
        outcome=ev.run_batch(self.data,"model-b",provider)
        self.assertEqual(outcome["passed"],2)

    def test_external_tests_require_a_real_judge_evidence(self):
        self.write([self.case("case-00005",{"compile":"passed"},
                              "external",category="coding")])
        no=ev.run_batch(self.data,"model-c",self.provider)
        self.assertEqual(no["assessed"],0)
        self.assertEqual(no["remaining"],1)
        def judge(case,reply):
            self.assertEqual(case["category"],"coding")
            return {"passed":True,"evidence_sha256":"a"*64}
        yes=ev.run_batch(self.data,"model-c",self.provider,
                         external_judge=judge)
        self.assertEqual(yes["passed"],1)
        self.assertTrue(yes["fully_evaluated"])

    def test_no_fake_success_when_model_is_unavailable(self):
        self.write([self.case("case-00006","Actual local response")])
        def broken(prompt,ident):
            raise ConnectionError("local model not installed")
        out=ev.run_batch(self.data,"model-d",broken)
        self.assertEqual(out["passed"],0)
        self.assertEqual(out["model_errors"],1)
        self.assertIsNone(out["verified_accuracy"])

    def test_dataset_must_be_owner_approved_local_path(self):
        with tempfile.TemporaryDirectory() as outside:
            foreign=Path(outside)/"other.jsonl"
            foreign.write_text('{"id":"case-other"}\n')
            with self.assertRaises(ValueError):
                ev.inspect(foreign)

    def test_evaluations_are_revision_isolated(self):
        self.write([self.case("case-00007","Actual local response")])
        first=ev.run_batch(self.data,"revision-a",self.provider)
        second=ev.run_batch(self.data,"revision-b",lambda p,i:
                {"content":"bad answer"})
        self.assertEqual(first["passed"],1)
        self.assertEqual(second["failed"],1)
        self.assertEqual(ev.summary(self.data,"revision-a")["passed"],1)

    def test_large_streamed_evaluation_runs_in_bounded_batches(self):
        self.write([self.case("case-%05d"%i,"Actual local response")
                    for i in range(500)])
        self.assertEqual(ev.inspect(self.data)["total_cases"],500)
        out=ev.run_batch(self.data,"revision-c",self.provider,batch_limit=100)
        self.assertEqual(out["assessed"],100)
        for _ in range(4):
            out=ev.run_batch(self.data,"revision-c",self.provider,batch_limit=100)
        self.assertEqual(out["passed"],500)
        self.assertTrue(out["fully_evaluated"])


if __name__=="__main__":
    unittest.main()
