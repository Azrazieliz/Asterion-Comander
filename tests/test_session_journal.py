"""Crash-safe native Control session receipts: no input/payload leakage or replay."""
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from asterion_remote import session_journal


class SessionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{"ASTERION_DIAGNOSTIC_ROOT":self.temp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_persists_terminal_receipt_without_user_data(self):
        job,reuse=session_journal.reserve("session-0001","mixed",4,"owner-request-0001")
        self.assertFalse(reuse)
        session_journal.progress(job["id"],state="running",current_step=2,completed_steps=2)
        final=session_journal.progress(job["id"],state="completed",
            current_step=4,completed_steps=4,elapsed_ms=97.4)
        self.assertEqual(final["state"],"completed")
        self.assertEqual(session_journal.get(job["id"])["completed_steps"],4)
        rows=session_journal.recent()
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]["inputs_persisted"])
        self.assertFalse(rows[0]["replay_allowed"])

    def test_same_user_request_never_runs_twice(self):
        original,_=session_journal.reserve("session-0002","phone",2,"owner-request-0002")
        replay,reused=session_journal.reserve("session-9999","phone",2,"owner-request-0002")
        self.assertTrue(reused)
        self.assertEqual(replay["id"],original["id"])
        self.assertEqual(len(session_journal.recent()),1)

    def test_after_restart_running_job_becomes_outcome_unknown(self):
        original,_=session_journal.reserve("session-0003","pc",1,"owner-request-0003")
        session_journal.progress(original["id"],state="running")
        with patch.object(session_journal,"_EPOCH","new-worker-epoch"):
            previous=session_journal.get(original["id"])
            self.assertEqual(previous["state"],"outcome_unknown")
            self.assertFalse(previous["replay_allowed"])
            other,reused=session_journal.reserve("session-9998","pc",1,"owner-request-0003")
            self.assertTrue(reused)
            self.assertEqual(other["state"],"outcome_unknown")

    def test_concurrent_reservations_are_atomic(self):
        out=[]
        def task(i):
            out.append(session_journal.reserve("session-%04d"%(i+100),"pc",1,
                                                "owner-request-concurrent")[0]["id"])
        threads=[threading.Thread(target=task,args=(i,)) for i in range(8)]
        for t in threads:t.start()
        for t in threads:t.join(timeout=8)
        self.assertEqual(len(set(out)),1)
        self.assertEqual(len(session_journal.recent()),1)

    def test_invalid_request_id_denied(self):
        with self.assertRaises(ValueError):
            session_journal.reserve("session-0004","pc",1,"../forbidden")

    def test_receipt_filtering_by_id(self):
        session_journal.reserve("session-0005","mixed",1)
        self.assertIsNone(session_journal.get("invalid/id"))
        self.assertEqual(session_journal.get("session-0005")["device"],"mixed")


if __name__=="__main__":
    unittest.main()
