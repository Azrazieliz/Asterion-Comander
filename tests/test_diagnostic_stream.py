"""Durable SSE event continuity, wake-up latency, privacy and permissions."""
import asyncio
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote import diagnostic_core as core
from asterion_remote.diagnostic_routes import router, sse_message, live_events


class DiagnosticStreamTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{"ASTERION_DIAGNOSTIC_ROOT":self.tmp.name,
                                        "ASTERION_API_TOKEN":"S"*40})
        self.env.start()
        app=FastAPI()
        app.include_router(router)
        self.client=TestClient(app)
        self.headers={"Authorization":"Bearer "+"S"*40}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_sse_format_is_safe_and_single_event(self):
        line=sse_message("event",{"text":"hello\nsecret:\npassword"},17)
        self.assertIn("id: 17\n",line)
        self.assertIn("event: event\n",line)
        self.assertEqual(line.count("\ndata: "),1)
        self.assertIn("\\nsecret:\\npassword",line)

    def test_subscriber_wakes_after_committed_event(self):
        result=[]
        def wait():
            begun=time.perf_counter()
            result.append((core.wait_for_change(0,2.0),
                          (time.perf_counter()-begun)*1000))
        waiter=threading.Thread(target=wait,daemon=True)
        waiter.start()
        time.sleep(.10)
        core.record("ready",app="asterion.control",trace_id="sse-test")
        waiter.join(2)
        self.assertEqual(len(result),1)
        self.assertTrue(result[0][0])
        self.assertLess(result[0][1],2000)

    def test_cursors_are_durable_across_restart(self):
        first=core.record("first")
        second=core.record("second")
        self.assertGreater(second["sequence"],first["sequence"])
        self.assertEqual(core.bounds()["oldest_sequence"],first["sequence"])
        self.assertEqual(core.events(since=first["sequence"])["events"][0]["kind"],"second")
        self.assertTrue(core.wait_for_change(first["sequence"],.1))

    def test_stream_requires_authentication(self):
        response=self.client.get("/api/v1/diagnostics/stream?since=-1")
        self.assertEqual(response.status_code,401)

    def test_invalid_stream_resume_is_rejected(self):
        async def call(since,header=None):
            class Req:
                headers={"last-event-id":header} if header is not None else {}
                async def is_disconnected(self):return True
            return await live_events(Req(),since=since)
        async def invalid():
            return await call(None,"evil\nretry: 0")
        with self.assertRaises(Exception):
            asyncio.run(invalid())
        with self.assertRaises(Exception):
            asyncio.run(call(-1))

    def test_initial_sse_event_reports_real_cursor(self):
        core.record("first")
        async def run():
            class Req:
                headers={}
                async def is_disconnected(self):return True
            resp=await live_events(Req(),since=0)
            return await anext(resp.body_iterator)
        item=asyncio.run(run())
        self.assertIn("event: ready",item)
        self.assertIn('"latest_sequence":1',item)


if __name__=="__main__":
    unittest.main()
