"""PC-to-Samsung Wi-Fi transfer through the paired Asterion native agent.

The file bytes travel directly between Windows and Android over the user's
private LAN/VPN. No GitHub, cloud, ADB, Desktop Commander or public URL carries
file content. Files are placed in Android Downloads/Asterion Control via
MediaStore only after a matching SHA-256 checksum is verified.
"""
from __future__ import annotations
import hashlib
import base64
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .phone_bridge import load as phone_pairing
from . import session_journal

TRANSFER_LIMIT = 2 * 1024 * 1024 * 1024
CHUNK = 512 * 1024
_workers = ThreadPoolExecutor(max_workers=2,thread_name_prefix="asterion-wifi-file")
_guard = threading.RLock()
_jobs: dict[str,dict] = {}
_cancels: dict[str,threading.Event] = {}
_active_sources: dict[str,tuple[str,str]] = {}

class TransferRequest(BaseModel):
    pc_path: str = Field(min_length=1,max_length=2048)
    name: str | None = Field(default=None,max_length=180)

def _name(value: str) -> str:
    if not value or len(value)>180 or value in (".","..") or value.startswith(".") or any(
        c in value for c in ("/","\\",":","\0")) or any(ord(c)<32 or ord(c)==127 for c in value):
        raise HTTPException(422,"Unsafe Android destination filename")
    return value

def _update(key: str, **values):
    with _guard:
        row=_jobs[key]
        candidate=dict(row,**values,updated_at=time.time())
        try:
            session_journal.save_transfer_receipt(candidate)
        except Exception:
            row.update(state="outcome_unknown",error="Transfer receipt persistence failed")
            raise RuntimeError("Transfer outcome uncertain: receipt persistence failed")
        row.update(candidate)

class _TransferTransport:
    """Use the existing paired LAN and authenticated native WSS, never GitHub bytes.

    Only read operations may switch paths automatically. After an ambiguous write
    the chunk state machine reads the committed offset before another write.
    """
    def __init__(self,client,base,token):
        self.client,self.base,self.token=client,base,token
        self.route="private-wifi"

    def _via(self,route,method,url,**kwargs):
        if route=="private-wifi":
            return getattr(self.client,method.lower())(url,**kwargs)
        path=url[len(self.base):]
        payload=kwargs.get("json")
        if method=="PUT":
            identity=path.rsplit("/",1)[-1]
            path="/transfer/chunk"
            payload={"transfer_id":identity,"offset":int(kwargs["headers"]["X-Transfer-Offset"]),
                "data":base64.b64encode(kwargs["content"]).decode("ascii")}
            method="POST"
        elif path.startswith("/transfer/") and path!="/transfer/start":
            path,identity=path.rsplit("/",1)
            payload={"transfer_id":identity}
            method="POST"
        rsp=self.client.post("http://127.0.0.1:8995/phone/rpc",
            json={"path":path,"method":method,"payload":payload,"timeout_seconds":22},
            headers={"Authorization":"Bearer "+self.token},timeout=25)
        if rsp.status_code>=400:return rsp
        body=rsp.json()
        if body.get("kind")!="json" or not isinstance(body.get("value"),dict):
            raise httpx.RemoteProtocolError("Invalid native transfer receipt")
        return httpx.Response(200,json=body["value"],request=rsp.request)

    def get(self,url,**kwargs):
        preferred=self.route
        alternate="native-wss" if preferred=="private-wifi" else "private-wifi"
        try:
            rsp=self._via(preferred,"GET",url,**kwargs)
            if rsp.status_code not in (502,503,504):return rsp
        except httpx.TransportError:
            pass
        # Safe read fallback; authorization and transfer identity are unchanged.
        rsp=self._via(alternate,"GET",url,**kwargs)
        if rsp.is_success:self.route=alternate
        return rsp

    def post(self,url,**kwargs):
        return self._via(self.route,"POST",url,**kwargs)

    def put(self,url,**kwargs):
        return self._via(self.route,"PUT",url,**kwargs)


def _post(client: httpx.Client,base: str,token: str,path: str,body: dict):
    response=client.post(base+path,json=body,headers={"Authorization":"Bearer "+token})
    response.raise_for_status()
    return response.json()

def finalize_verified_android_transfer(
    *, client: httpx.Client, base: str, token: str,
    transfer_id: str, checksum: str, size: int,
    publish_state, cancel: threading.Event,
    max_wait_seconds: float = 900.0, initial_phase: str = 'receiving',
) -> dict:
    """One finalization request, then read-only reconciliation until Android ACK.

    The old Android finished synchronously; new TransferStore ACKs "verifying"
    immediately while a background worker hashes and publishes into MediaStore.
    Never re-send a finalization after uncertain transport. A timeout is
    reconciled by GET status, not another POST.
    """
    headers={"Authorization":"Bearer "+token}
    issued=time.monotonic()
    envelope=None
    if initial_phase=="receiving":
        try:
            envelope=_post(client,base,token,"/transfer/finish/"+transfer_id,{})
        except (httpx.TimeoutException,httpx.TransportError):
            publish_state("outcome_unknown")
            # Android might have received the command; ONLY safe reads below.
        except httpx.HTTPStatusError as ex:
            code=ex.response.status_code
            if code not in (408,500,502,503,504):
                raise RuntimeError(f"android_finish_http_{code}") from ex
            publish_state("outcome_unknown")
    elif initial_phase=="outcome_unknown":
        raise RuntimeError("android_publication_outcome_unknown")
    elif initial_phase not in ("verifying","publishing","completed","failed"):
        raise RuntimeError("android_unknown_initial_transfer_phase")
    if envelope is not None and envelope.get("ok") is True:
        receipt=envelope
    else:
        receipt=None
        while time.monotonic()-issued<max_wait_seconds:
            if cancel.is_set():
                raise RuntimeError("android_publication_cancel_ambiguous")
            time.sleep(1)
            try:
                probe=client.get(base+"/transfer/status/"+transfer_id,
                                 headers=headers)
                probe.raise_for_status()
            except (httpx.TransportError,httpx.TimeoutException):
                publish_state("outcome_unknown")
                continue
            except httpx.HTTPStatusError as ex:
                code=ex.response.status_code
                if code in (408,429,500,502,503,504):
                    publish_state("outcome_unknown")
                    continue
                raise RuntimeError(f"android_transfer_receipt_http_{code}") from ex
            state=probe.json()
            if state.get("sha256")!=checksum or int(state.get("size",-1))!=size:
                raise RuntimeError("android_transfer_identity_changed")
            phase=state.get("phase")
            if phase=="completed":
                receipt=state.get("result")
                break
            if phase=="outcome_unknown":
                raise RuntimeError("android_publication_outcome_unknown")
            if phase=="failed":
                error=state.get("error_code","android_publication_failed")
                if not isinstance(error,str) or len(error)>100:
                    error="android_publication_failed"
                raise RuntimeError(error)
            if phase not in ("verifying","publishing","receiving"):
                raise RuntimeError("android_unknown_publication_phase")
            publish_state(phase)
        else:
            raise RuntimeError("android_publication_outcome_unknown")
    if not isinstance(receipt,dict) or receipt.get("sha256")!=checksum or \
       int(receipt.get("size",-1))!=size or receipt.get("ok") is not True:
        raise RuntimeError("android_verified_publication_receipt_mismatch")
    if not isinstance(receipt.get("location"),str) or not \
       receipt["location"].startswith("Downloads/Asterion Control/"):
        raise RuntimeError("android_unexpected_publication_location")
    if not isinstance(receipt.get("uri"),str) or not \
       receipt["uri"].startswith("content://"):
        raise RuntimeError("android_download_uri_not_verified")
    return receipt


def _send_verified_chunk(client,base,headers,transfer_id,checksum,size,offset,payload,cancel):
    """Retry an ambiguous PUT only after a successful identity/offset read."""
    end=offset+len(payload)
    for attempt in range(6):
        if cancel.is_set():raise InterruptedError("Cancelled by user")
        try:
            response=client.put(base+"/transfer/chunk/"+transfer_id,
                content=payload,headers={**headers,"Content-Type":"application/octet-stream",
                "X-Transfer-Offset":str(offset)})
            response.raise_for_status()
            if int(response.json().get("received",-1))!=end:
                raise RuntimeError("Phone acknowledged unexpected chunk length")
            return end
        except (httpx.HTTPError,ValueError,TypeError,RuntimeError) as exc:
            last=exc
        # A failed status GET must never loop back into PUT. Resolve the
        # original write outcome using bounded READ-only retries first.
        for probe_attempt in range(6):
            if cancel.is_set():raise InterruptedError("Cancelled by user")
            time.sleep(min(2.0,0.2*(probe_attempt+1)))
            try:
                probe=client.get(base+"/transfer/status/"+transfer_id,headers=headers)
                probe.raise_for_status()
                state=probe.json()
            except (httpx.TransportError,ValueError) as exc:
                last=exc
                continue
            except httpx.HTTPStatusError as exc:
                last=exc
                if exc.response.status_code in (408,429,500,502,503,504):continue
                raise RuntimeError("Transfer offset outcome uncertain: status HTTP "+
                                   str(exc.response.status_code)) from exc
            if (state.get("sha256")!=checksum or int(state.get("size",-1))!=size or
                state.get("id",transfer_id)!=transfer_id):
                raise RuntimeError("Transfer identity changed during recovery")
            current=int(state.get("received",-1))
            if not offset<=current<=end:
                raise RuntimeError("Transfer advanced outside expected chunk")
            if current==end:return end
            if state.get("phase","receiving")!="receiving":
                raise RuntimeError("Transfer not accepting remaining bytes")
            payload=payload[current-offset:]
            offset=current
            break
        else:
            raise RuntimeError("Transfer offset outcome uncertain: status unavailable") from last
    raise RuntimeError("Transfer offset outcome uncertain: retry limit") from last


def _copy(key: str, path: Path, name: str, paired: dict, cancel: threading.Event):
    transfer_id=None
    headers={"Authorization":"Bearer "+paired["token"]}
    base=paired["base_url"]
    try:
        _update(key,state="hashing")
        expected=hashlib.sha256()
        size=0
        with path.open("rb") as file:
            while data:=file.read(1024*1024):
                if cancel.is_set():raise InterruptedError("Cancelled by user")
                expected.update(data);size+=len(data)
                if size>TRANSFER_LIMIT:raise ValueError("File exceeds Android transfer limit")
        checksum=expected.hexdigest()
        with httpx.Client(timeout=httpx.Timeout(30.0,connect=5.0),
                          trust_env=False,follow_redirects=False) as http:
            client=_TransferTransport(http,base,paired["token"])
            # Select a working authenticated route with a read before any write.
            client.get(base+"/health",headers=headers).raise_for_status()
            _update(key,state="starting",size=size,sha256=checksum)
            init=_post(client,base,paired["token"],"/transfer/start",
                {"name":name,"size":size,"sha256":checksum})
            transfer_id=init["id"]
            if not isinstance(transfer_id,str) or not transfer_id or len(transfer_id)>64 or not all(
                character.isalnum() or character in "_-" for character in transfer_id):
                raise RuntimeError("Phone returned invalid transfer identifier")
            chunk_size=min(CHUNK,int(init.get("chunk_max",CHUNK)))
            if not (4096 <= chunk_size <= CHUNK):
                raise RuntimeError("Phone refused safe transfer chunk size")
            if init.get("sha256") != checksum or int(init.get("size",-1))!=size:
                raise RuntimeError("Phone resumed a different file; refusing transmission")
            offset=int(init.get("received",0))
            if not 0<=offset<=size:
                raise RuntimeError("Phone returned invalid transfer offset")
            _update(key,state="transferring",size=size,bytes_sent=offset,
                    recovered_bytes=offset,transport=client.route,phone_transfer_id=transfer_id)
            if init.get("phase","receiving")!="receiving" and offset!=size:
                raise RuntimeError("Android transfer no longer accepts incomplete file")
            with path.open("rb") as file:
                while offset<size:
                    if cancel.is_set():raise InterruptedError("Cancelled by user")
                    file.seek(offset)
                    payload=file.read(min(chunk_size,size-offset))
                    if not payload:
                        raise RuntimeError("Source changed during transfer")
                    offset=_send_verified_chunk(client,base,headers,transfer_id,
                        checksum,size,offset,payload,cancel)
                    _update(key,bytes_sent=offset,transport=client.route)
            _update(key,state="verifying")
            done=finalize_verified_android_transfer(
                client=client,base=base,token=paired["token"],
                transfer_id=transfer_id,checksum=checksum,size=size,
                publish_state=lambda phase: _update(key,state=phase),
                cancel=cancel,initial_phase=init.get("phase","receiving"),
            )
            _update(key,state="completed",result={
                "name":done["name"],"size":done["size"],"sha256":done["sha256"],
                "location":done["location"],"android_uri":done["uri"],
                "transport":client.route,"verified":True})
    except Exception as e:
        aborted=isinstance(e,InterruptedError)
        # A disconnected sender cannot assume the phone did not accept data.
        # Keep partial bytes until explicit cancellation or Android TTL cleanup;
        # the same SHA/name can resume without a second media publication.
        unknown=isinstance(e,(httpx.TransportError,httpx.TimeoutException)) or \
            "outcome uncertain" in str(e).lower() or \
            "outcome_unknown" in str(e).lower() or \
            "cancel_ambiguous" in str(e).lower()
        label="cancelled" if aborted and transfer_id is None else ("outcome_unknown" if unknown or aborted else "failed")
        if transfer_id and aborted:
            try:
                with httpx.Client(timeout=4,trust_env=False,follow_redirects=False) as c:
                    route=_TransferTransport(c,base,paired["token"])
                    route.get(base+"/health",headers=headers).raise_for_status()
                    reply=route.post(base+"/transfer/cancel/"+transfer_id,json={},headers=headers)
                    reply.raise_for_status()
                    if reply.json().get("cancelled") is True:label="cancelled"
            except Exception:pass
        _update(key,state=label,error=type(e).__name__+": "+str(e)[:160])

def _run_copy(key,path,name,paired,cancel):
    try:
        _copy(key,path,name,paired,cancel)
    finally:
        # outcome_unknown is an honest retained result, not a live worker.
        # It must not permanently consume one of the three active slots.
        with _guard:
            _cancels.pop(key,None)
            _active_sources.pop(key,None)


def start_transfer(data: TransferRequest,safe_path):
    source=safe_path(data.pc_path)
    if not source.is_file() or source.is_symlink():
        raise HTTPException(404,"Source is not an authorized regular file")
    if source.stat().st_size>TRANSFER_LIMIT:
        raise HTTPException(422,"File exceeds 2 GiB transfer limit")
    paired=phone_pairing()
    if not paired:raise HTTPException(503,"Phone not paired")
    name=_name(data.name or source.name)
    with _guard:
        # Keep the active queue bounded; old results do not occupy worker slots.
        identity=(str(source.resolve()),name)
        for existing,active in _active_sources.items():
            if active==identity:
                return {"id":existing,"status":"queued","transport":"PC-to-Android paired LAN / native WSS"}
            if active[1]==name:
                raise HTTPException(409,"Destination filename already has an active transfer")
        if len(_cancels)>=3:
            raise HTTPException(429,"Asterion Control transfer queue full",headers={"Retry-After":"10"})
        key=uuid.uuid4().hex
        record={"id":key,"state":"queued","pc_name":source.name,"android_name":name,
                    "bytes_sent":0,"size":source.stat().st_size,
                    "created_at":time.time(),"updated_at":time.time(),"result":None,"error":None}
        try:
            session_journal.save_transfer_receipt(record)
        except Exception as exc:
            raise HTTPException(503,"Transfer receipt storage unavailable; nothing submitted") from exc
        _jobs[key]=record
        cancel=threading.Event();_cancels[key]=cancel
        _active_sources[key]=identity
    try:
        _workers.submit(_run_copy,key,source,name,paired,cancel)
    except Exception:
        with _guard:
            _cancels.pop(key,None);_active_sources.pop(key,None)
            _update(key,state='failed',error='Transfer worker unavailable')
        raise HTTPException(503,'Transfer worker unavailable')
    return {"id":key,"status":"queued","transport":"PC-to-Android paired LAN / native WSS"}

def _reconcile_receipt(job: dict) -> dict:
    """Read only: an interrupted transfer must never dispatch a new start/finish."""
    identity=job.get("phone_transfer_id")
    checksum=job.get("sha256")
    if job.get("state")!="outcome_unknown" or not identity or not checksum:
        return job
    paired=phone_pairing()
    if not paired:return job
    try:
        base=paired["base_url"]
        headers={"Authorization":"Bearer "+paired["token"]}
        with httpx.Client(timeout=httpx.Timeout(5.0,connect=2.0),trust_env=False,follow_redirects=False) as http:
            route=_TransferTransport(http,base,paired["token"])
            probe=route.get(base+"/transfer/status/"+identity,headers=headers)
            probe.raise_for_status()
            state=probe.json()
        if (state.get("id")!=identity or state.get("sha256")!=checksum or
                int(state.get("size",-1))!=job["size"] or state.get("name")!=job["android_name"]):
            return job
        offset=int(state.get("received",-1))
        if not 0<=offset<=job["size"]:return job
        observed=dict(job,bytes_sent=offset,updated_at=time.time())
        phase=state.get("phase")
        if phase=="completed":
            done=state.get("result")
            if (not isinstance(done,dict) or done.get("ok") is not True or
                done.get("sha256")!=checksum or int(done.get("size",-1))!=job["size"] or
                offset!=job["size"] or not isinstance(done.get("name"),str) or
                done.get("location")!="Downloads/Asterion Control/"+done["name"] or
                not isinstance(done.get("uri"),str) or not done["uri"].startswith("content://")):
                return job
            _name(done["name"])
            observed.update(state="completed",error=None,result={
                "name":done["name"],"size":done["size"],"sha256":checksum,
                "location":done["location"],"android_uri":done["uri"],
                "transport":route.route,"verified":True})
        elif phase=="failed":
            observed.update(state="failed",error="Android reported publication failure")
        else:
            observed["error"]="Android phase: "+phase if phase in ("receiving","verifying","publishing","outcome_unknown") else "Android outcome unverified"
        durable=session_journal.save_transfer_receipt(observed)
        return dict(durable,worker_active=False,source='durable_transfer_receipt')
    except Exception:
        return job

def transfer_status(key: str):
    with _guard:
        job=_jobs.get(key)
        if job is not None:
            snapshot=dict(job,worker_active=key in _cancels)
        else:
            snapshot=session_journal.get_transfer_receipt(key)
    if snapshot is None:raise HTTPException(404,"Unknown transfer")
    if snapshot["worker_active"]:return snapshot
    # Never hold the worker lock during network reads.
    observed=_reconcile_receipt(snapshot)
    with _guard:
        if key in _jobs and key not in _cancels:
            if _jobs[key]["state"] not in ("completed","failed","cancelled"):
                _jobs[key].update(observed)
            else:
                return dict(_jobs[key],worker_active=False)
    return observed

def cancel_transfer(key: str):
    with _guard:
        job=_jobs.get(key)
        if job is None:
            job=session_journal.get_transfer_receipt(key)
            if job is None:raise HTTPException(404,"Unknown transfer")
        if key not in _cancels or job["state"] in ("completed","failed","cancelled"):
            return {"ok":False,"state":job["state"]}
        _cancels[key].set()
    return {"ok":True,"state":"cancelling"}
