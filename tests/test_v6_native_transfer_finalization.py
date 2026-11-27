"""Large signed APK publication receipts must never be confused with bytes sent.

Pure, read-only protocol tests: no Android install, no transfer, no APK build.
"""
from __future__ import annotations

import threading
import unittest
from unittest.mock import patch
import httpx
from asterion_remote.native_transfer import finalize_verified_android_transfer


EXPECTED = "a" * 64
SIZE = 505_163_972
URI = "content://downloads/857"
LEGACY = {
    "ok": True,
    "sha256": EXPECTED,
    "size": SIZE,
    "name": "Asterion-Control-v0.9.38-release.apk",
    "location": "Downloads/Asterion Control/Asterion-Control-v0.9.38-release.apk",
    "uri": URI,
}


def response(body, code=200, uri="http://127.0.0.1:8765/"):
    return httpx.Response(
        code,
        json=body,
        request=httpx.Request("GET", uri),
    )


class FakeClient:
    def __init__(self, finish, states=()):
        self.finish = finish
        self.states = list(states)
        self.posts = 0
        self.gets = 0

    def post(self, uri, **kwargs):
        self.posts += 1
        if isinstance(self.finish, Exception):
            raise self.finish
        return response(self.finish, uri=uri)

    def get(self, uri, **kwargs):
        self.gets += 1
        if not self.states:
            raise AssertionError("Polling beyond simulated transfer receipts")
        status = self.states.pop(0)
        if isinstance(status, Exception):
            raise status
        return response(status, uri=uri)


class PublicationAcceptance(unittest.TestCase):
    def run_case(self, client, size=SIZE, digest=EXPECTED):
        phases = []
        with patch("asterion_remote.native_transfer.time.sleep", return_value=None):
            result = finalize_verified_android_transfer(
                client=client, base="http://127.0.0.1:8765", token="unit-test-only",
                transfer_id="stable-id-123",checksum=digest,size=size,
                publish_state=phases.append,cancel=threading.Event(),
                max_wait_seconds=20)
        return result,phases

    def test_legacy_completed_receipt_still_works(self):
        client=FakeClient(LEGACY)
        reply, phases=self.run_case(client)
        self.assertEqual(reply,LEGACY)
        self.assertEqual(client.posts,1)
        self.assertEqual(client.gets,0)
        self.assertFalse(phases)

    def test_new_android_returns_verifying_then_commits_once(self):
        client=FakeClient(
            {"phase":"verifying","id":"stable-id-123"},
            [
                {"phase":"verifying","sha256":EXPECTED,"size":SIZE},
                {"phase":"publishing","sha256":EXPECTED,"size":SIZE},
                {"phase":"completed","sha256":EXPECTED,"size":SIZE,
                 "result":LEGACY},
            ])
        reply,phases=self.run_case(client)
        self.assertEqual(reply["uri"],URI)
        self.assertEqual(phases,["verifying","publishing"])
        self.assertEqual(client.posts,1)
        self.assertEqual(client.gets,3)

    def test_lost_finish_ack_uses_read_only_probe(self):
        client=FakeClient(httpx.ReadTimeout("simulated lost finish reply"),[
            {"phase":"publishing","sha256":EXPECTED,"size":SIZE},
            {"phase":"completed","sha256":EXPECTED,"size":SIZE,
             "result":LEGACY},
        ])
        result,phases=self.run_case(client)
        self.assertTrue(result["ok"])
        self.assertEqual(phases,["outcome_unknown","publishing"])
        self.assertEqual(client.posts,1)

    def test_failed_android_publication_is_not_replayed(self):
        client=FakeClient({"phase":"verifying"},[
            {"phase":"failed","sha256":EXPECTED,"size":SIZE,
             "error_code":"downloads_commit_denied"},
        ])
        with patch("asterion_remote.native_transfer.time.sleep",return_value=None):
            with self.assertRaisesRegex(RuntimeError,"downloads_commit_denied"):
                self.run_case(client)
        self.assertEqual(client.posts,1)

    def test_abnormal_checksum_blocks_completion(self):
        client=FakeClient({**LEGACY,"sha256":"b"*64})
        with self.assertRaisesRegex(RuntimeError,"receipt_mismatch"):
            self.run_case(client)
        self.assertEqual(client.posts,1)

    def test_mismatched_status_identity_refused(self):
        client=FakeClient({"phase":"verifying"},[
            {"phase":"completed","sha256":"b"*64,"size":SIZE,
             "result":LEGACY},
        ])
        with self.assertRaisesRegex(RuntimeError,"identity_changed"):
            self.run_case(client)
        self.assertEqual(client.posts,1)

    def test_invalid_media_store_uri_not_accepted(self):
        client=FakeClient({**LEGACY,"uri":"https://evil.example/file.apk"})
        with self.assertRaisesRegex(RuntimeError,"uri_not_verified"):
            self.run_case(client)

    def test_http_400_is_classified_without_sensitive_response(self):
        client=FakeClient({"error":"private error"},())
        # Wrap as a genuine HTTP 400 returned by the phone.
        client.finish={"error":"internal detail"}
        original=client.post
        def bad(uri,**kwargs):
            client.posts+=1
            return response({"error":"private"},400,uri)
        client.post=bad
        with self.assertRaisesRegex(RuntimeError,"android_finish_http_400"):
            self.run_case(client)
        self.assertEqual(client.posts,1)


if __name__=="__main__":
    unittest.main()


class ChunkRecoveryAcceptance(unittest.TestCase):
    def send(self,handler):
        from asterion_remote.native_transfer import _send_verified_chunk
        with httpx.Client(transport=httpx.MockTransport(handler)) as client, \
             patch("asterion_remote.native_transfer.time.sleep",return_value=None):
            return _send_verified_chunk(client,"http://127.0.0.1:8765",{},
                "stable-id-123",EXPECTED,4,0,b"abcd",threading.Event())

    def test_lost_put_and_failed_status_never_replay_committed_bytes(self):
        calls=[]
        def handler(req):
            calls.append(req.method)
            if len(calls)<3:raise httpx.ReadTimeout("simulated loss")
            return httpx.Response(200,json={"id":"stable-id-123","received":4,
                "sha256":EXPECTED,"size":4,"phase":"receiving"})
        self.assertEqual(self.send(handler),4)
        self.assertEqual(calls,["PUT","GET","GET"])

    def test_retry_only_uncommitted_suffix(self):
        calls=[]
        def handler(req):
            calls.append((req.method,req.headers.get("X-Transfer-Offset"),req.content))
            if len(calls)==1:raise httpx.ReadTimeout("lost ACK")
            if req.method=="GET":return httpx.Response(200,json={"received":2,
                "sha256":EXPECTED,"size":4,"phase":"receiving"})
            return httpx.Response(200,json={"received":4})
        self.assertEqual(self.send(handler),4)
        self.assertEqual(calls[-1],("PUT","2",b"cd"))

    def test_status_unavailable_never_reissues_write(self):
        calls=[]
        def handler(req):
            calls.append(req.method)
            raise httpx.ReadTimeout("no response")
        with self.assertRaisesRegex(RuntimeError,"status unavailable"):
            self.send(handler)
        self.assertEqual(calls.count("PUT"),1)
        self.assertEqual(calls.count("GET"),6)

    def test_wrong_transfer_identity_never_reissues_write(self):
        calls=[]
        def handler(req):
            calls.append(req.method)
            if req.method=="PUT":raise httpx.ReadTimeout("lost ACK")
            return httpx.Response(200,json={"received":0,"sha256":"b"*64,"size":4})
        with self.assertRaisesRegex(RuntimeError,"identity changed"):
            self.send(handler)
        self.assertEqual(calls,["PUT","GET"])


def test_uncertain_worker_releases_queue_slot(tmp_path,monkeypatch):
    from asterion_remote import native_transfer as t
    monkeypatch.setattr(t,"_jobs",{"job":{"state":"outcome_unknown"}})
    monkeypatch.setattr(t,"_cancels",{"job":threading.Event()})
    monkeypatch.setattr(t,"_active_sources",{"job":("file","name")})
    monkeypatch.setattr(t,"_copy",lambda *a:None)
    t._run_copy("job",tmp_path/"file","name",{},threading.Event())
    assert t.transfer_status("job")["state"]=="outcome_unknown"
    assert not t.transfer_status("job")["worker_active"]
    assert t.cancel_transfer("job")=={"ok":False,"state":"outcome_unknown"}


def test_transfer_falls_back_to_original_wss_on_read_only_probe():
    from asterion_remote.native_transfer import _TransferTransport
    import base64
    seen=[]
    def handler(req):
        if req.url.host=='192.168.8.8':
            seen.append(('LAN',req.method))
            raise httpx.ConnectError('LAN unavailable')
        body=__import__('json').loads(req.content)
        seen.append(('WSS',body['path']))
        if body['path']=='/transfer/chunk':
            assert base64.b64decode(body['payload']['data'])==b'abcd'
            assert body['payload']['offset']==0
            return httpx.Response(200,json={'kind':'json','value':{'received':4}})
        return httpx.Response(200,json={'kind':'json','value':{'ok':True}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        route=_TransferTransport(client,'http://192.168.8.8:8973','token')
        route.get('http://192.168.8.8:8973/health').raise_for_status()
        assert route.route=='native-wss'
        reply=route.put('http://192.168.8.8:8973/transfer/chunk/valid-id-123',
                       content=b'abcd',headers={'X-Transfer-Offset':'0'})
        assert reply.json()['received']==4
    assert seen==[('LAN','GET'),('WSS','/health'),('WSS','/transfer/chunk')]


def test_transport_does_not_switch_after_ambiguous_write():
    from asterion_remote.native_transfer import _TransferTransport
    calls=[]
    def handler(req):
        calls.append((req.url.host,req.method))
        raise httpx.ReadTimeout('lost reply')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        route=_TransferTransport(client,'http://192.168.8.8:8973','token')
        import pytest
        with pytest.raises(httpx.ReadTimeout):
            route.post('http://192.168.8.8:8973/transfer/finish/valid-id-123',json={})
    assert calls==[('192.168.8.8','POST')]


def test_resumed_completed_transfer_reads_receipt_without_finish_replay():
    client=FakeClient(AssertionError('Must not finish again'),[
        {'phase':'completed','sha256':EXPECTED,'size':SIZE,'result':LEGACY}])
    with patch('asterion_remote.native_transfer.time.sleep',return_value=None):
        reply=finalize_verified_android_transfer(client=client,base='http://127.0.0.1:8765',
            token='redacted',transfer_id='valid-id-123',checksum=EXPECTED,size=SIZE,
            publish_state=lambda phase:None,cancel=threading.Event(),initial_phase='completed')
    assert reply==LEGACY and client.posts==0 and client.gets==1


def test_interrupted_android_publication_is_not_replayed():
    import pytest
    client=FakeClient(AssertionError("Must not reinsert or finish"))
    with pytest.raises(RuntimeError,match="publication_outcome_unknown"):
        finalize_verified_android_transfer(client=client,base="http://127.0.0.1:8765",
            token="redacted",transfer_id="valid-id-123",checksum=EXPECTED,size=SIZE,
            publish_state=lambda phase:None,cancel=threading.Event(),initial_phase="outcome_unknown")
    assert client.posts==client.gets==0


def test_recovery_poll_stops_on_durable_unknown_publication():
    import pytest
    client=FakeClient({"phase":"verifying"},[{"phase":"outcome_unknown","size":SIZE,"sha256":EXPECTED}])
    with patch("asterion_remote.native_transfer.time.sleep",return_value=None):
        with pytest.raises(RuntimeError,match="publication_outcome_unknown"):
            finalize_verified_android_transfer(client=client,base="http://127.0.0.1:8765",
                token="redacted",transfer_id="valid-id-123",checksum=EXPECTED,size=SIZE,
                publish_state=lambda phase:None,cancel=threading.Event())
    assert client.posts==1 and client.gets==1

def test_worker_restart_retains_receipt_without_replay(tmp_path,monkeypatch):
    from asterion_remote import native_transfer as t, session_journal as j
    monkeypatch.setenv("ASTERION_DIAGNOSTIC_ROOT",str(tmp_path))
    monkeypatch.setattr(t,"_jobs",{})
    monkeypatch.setattr(t,"_cancels",{})
    monkeypatch.setattr(t,"phone_pairing",lambda:None)
    ident="a"*32
    j.save_transfer_receipt({"id":ident,"state":"transferring","size":4,
        "bytes_sent":2,"android_name":"test.txt","pc_name":"test.txt",
        "sha256":EXPECTED,"phone_transfer_id":"phone-identifier","source_path":"private",
        "token":"private","error":None})
    monkeypatch.setattr(j,"_EPOCH","new-worker")
    result=t.transfer_status(ident)
    assert result["state"]=="outcome_unknown"
    assert result["bytes_sent"]==2
    assert result["worker_active"] is False
    assert "token" not in result and "source_path" not in result
    assert t.cancel_transfer(ident)=={"ok":False,"state":"outcome_unknown"}

def test_restarted_transfer_can_read_verified_android_completion(tmp_path,monkeypatch):
    from asterion_remote import native_transfer as t, session_journal as j
    monkeypatch.setenv("ASTERION_DIAGNOSTIC_ROOT",str(tmp_path))
    monkeypatch.setattr(t,"_jobs",{})
    monkeypatch.setattr(t,"_cancels",{})
    monkeypatch.setattr(t,"phone_pairing",lambda:{"base_url":"http://127.0.0.1:8973","token":"test"})
    ident="b"*32
    j.save_transfer_receipt({"id":ident,"state":"verifying","size":SIZE,
        "bytes_sent":SIZE,"android_name":LEGACY["name"],"sha256":EXPECTED,
        "phone_transfer_id":"phone-identifier","error":None})
    calls=[]
    def handler(req):
        calls.append(req.method)
        return httpx.Response(200,json={"id":"phone-identifier","sha256":EXPECTED,
            "size":SIZE,"name":LEGACY["name"],"received":SIZE,"phase":"completed","result":LEGACY})
    factory=httpx.Client
    monkeypatch.setattr(t.httpx,"Client",lambda **kw:factory(transport=httpx.MockTransport(handler),**kw))
    assert t.transfer_status(ident)["result"]["verified"] is True
    assert t.transfer_status(ident)["state"]=="completed"
    assert calls==["GET"]

def test_receipt_failure_refuses_submission(tmp_path,monkeypatch):
    from asterion_remote import native_transfer as t, session_journal as j
    from fastapi import HTTPException
    import pytest
    src=tmp_path/"test.txt";src.write_text("test")
    monkeypatch.setattr(t,"_jobs",{})
    monkeypatch.setattr(t,"_cancels",{})
    monkeypatch.setattr(t,"_active_sources",{})
    monkeypatch.setattr(t,"phone_pairing",lambda:{"base_url":"http://127.0.0.1:8973","token":"test"})
    def fail(_):raise OSError("disk full")
    monkeypatch.setattr(j,"save_transfer_receipt",fail)
    with pytest.raises(HTTPException) as e:
        t.start_transfer(t.TransferRequest(pc_path=str(src)),lambda _:src)
    assert e.value.status_code==503 and not t._jobs and not t._cancels

def test_stale_reconciliation_cannot_replace_verified_receipt(tmp_path,monkeypatch):
    from asterion_remote import session_journal as j
    monkeypatch.setenv("ASTERION_DIAGNOSTIC_ROOT",str(tmp_path))
    row={"id":"c"*32,"state":"outcome_unknown","size":SIZE,"bytes_sent":SIZE}
    j.save_transfer_receipt(row)
    j.save_transfer_receipt(dict(row,state="completed",result={"verified":True}))
    result=j.save_transfer_receipt(row)
    assert result["state"]=="completed"
    assert j.get_transfer_receipt(row["id"])["result"]["verified"] is True

def test_stale_offset_cannot_regress_receipt(tmp_path,monkeypatch):
    from asterion_remote import session_journal as j
    monkeypatch.setenv("ASTERION_DIAGNOSTIC_ROOT",str(tmp_path))
    row={"id":"d"*32,"state":"outcome_unknown","size":4,"bytes_sent":4}
    j.save_transfer_receipt(row)
    assert j.save_transfer_receipt(dict(row,bytes_sent=2))["bytes_sent"]==4
