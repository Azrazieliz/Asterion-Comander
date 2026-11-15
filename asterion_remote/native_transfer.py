"""PC-to-Samsung Wi-Fi transfer through the paired Asterion native agent.

The file bytes travel directly between Windows and Android over the user's
private LAN/VPN. No GitHub, cloud, ADB, Desktop Commander or public URL carries
file content. Files are placed in Android Downloads/Asterion Control via
MediaStore only after a matching SHA-256 checksum is verified.
"""
from __future__ import annotations
import hashlib
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

TRANSFER_LIMIT = 2 * 1024 * 1024 * 1024
CHUNK = 512 * 1024
_workers = ThreadPoolExecutor(max_workers=2,thread_name_prefix="asterion-wifi-file")
_guard = threading.RLock()
_jobs: dict[str,dict] = {}
_cancels: dict[str,threading.Event] = {}

class TransferRequest(BaseModel):
    pc_path: str = Field(min_length=1,max_length=2048)
    name: str | None = Field(default=None,max_length=180)

def _name(value: str) -> str:
    if not value or len(value)>180 or value in (".","..") or value.startswith(".") or any(
        c in value for c in ("/","\\",":","\0")) or any(ord(c)<32 for c in value):
        raise HTTPException(422,"Unsafe Android destination filename")
    return value

def _update(key: str, **values):
    with _guard:
        row=_jobs[key]
        row.update(values)
        row["updated_at"]=time.time()

def _post(client: httpx.Client,base: str,token: str,path: str,body: dict):
    response=client.post(base+path,json=body,headers={"Authorization":"Bearer "+token})
    response.raise_for_status()
    return response.json()

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
                          trust_env=False,follow_redirects=False) as client:
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
                    recovered_bytes=offset)
            with path.open("rb") as file:
                while offset<size:
                    if cancel.is_set():raise InterruptedError("Cancelled by user")
                    file.seek(offset)
                    payload=file.read(min(chunk_size,size-offset))
                    if not payload:
                        raise RuntimeError("Source changed during transfer")
                    attempts=0
                    while True:
                        if cancel.is_set():raise InterruptedError("Cancelled by user")
                        try:
                            response=client.put(base+"/transfer/chunk/"+transfer_id,
                              content=payload,headers={**headers,
                                "Content-Type":"application/octet-stream",
                                "X-Transfer-Offset":str(offset)})
                            response.raise_for_status()
                            next_pos=int(response.json().get("received",-1))
                            if next_pos!=offset+len(payload):
                                raise RuntimeError("Phone acknowledged unexpected chunk length")
                            offset=next_pos
                            break
                        except (httpx.HTTPError,ValueError,RuntimeError) as exc:
                            # A network interruption can occur AFTER Android
                            # appended bytes. Never replay that same offset
                            # without asking the phone what was committed.
                            attempts+=1
                            if attempts>5:
                                raise RuntimeError("Transfer offset outcome uncertain") from exc
                            time.sleep(min(1.5,0.15*attempts))
                            try:
                                probe=client.get(base+"/transfer/status/"+transfer_id,
                                                 headers=headers)
                                probe.raise_for_status()
                                state=probe.json()
                                current=int(state["received"])
                                if state.get("sha256")!=checksum or int(state.get("size",-1))!=size:
                                    raise RuntimeError("Transfer identity changed during recovery")
                                if not offset<=current<=offset+len(payload):
                                    raise RuntimeError("Transfer advanced outside expected chunk")
                                if current>offset:
                                    offset=current
                                    # Retry only the uncommitted suffix.
                                    file.seek(offset)
                                    payload=file.read(min(chunk_size,size-offset))
                                    if not payload:
                                        break
                            except httpx.TransportError:
                                # Retry the READ probe, never blind-write old bytes.
                                continue
                    _update(key,bytes_sent=offset)
            _update(key,state="verifying")
            done=_post(client,base,paired["token"],"/transfer/finish/"+transfer_id,{})
            if done.get("sha256")!=checksum or done.get("size")!=size or not done.get("ok"):
                raise RuntimeError("Android checksum/size receipt mismatch")
            _update(key,state="completed",result={
                "name":done["name"],"size":done["size"],"sha256":done["sha256"],
                "location":done["location"],"android_uri":done["uri"],
                "transport":"private-wifi","verified":True})
    except Exception as e:
        aborted=isinstance(e,InterruptedError)
        # A disconnected sender cannot assume the phone did not accept data.
        # Keep partial bytes until explicit cancellation or Android TTL cleanup;
        # the same SHA/name can resume without a second media publication.
        unknown=isinstance(e,(httpx.TransportError,httpx.TimeoutException)) or \
            "outcome uncertain" in str(e).lower()
        label="cancelled" if aborted else ("outcome_unknown" if unknown else "failed")
        _update(key,state=label,error=type(e).__name__+": "+str(e)[:160])
        if transfer_id and aborted:
            try:
                with httpx.Client(timeout=4,trust_env=False,follow_redirects=False) as c:
                    c.post(base+"/transfer/cancel/"+transfer_id,json={},headers=headers)
            except Exception:pass

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
        if sum(r["state"] not in ("completed","failed","cancelled") for r in _jobs.values())>=3:
            raise HTTPException(429,"Asterion Control transfer queue full")
        key=uuid.uuid4().hex
        _jobs[key]={"id":key,"state":"queued","pc_name":source.name,"android_name":name,
                    "bytes_sent":0,"size":source.stat().st_size,
                    "created_at":time.time(),"updated_at":time.time(),"result":None,"error":None}
        cancel=threading.Event();_cancels[key]=cancel
    _workers.submit(_copy,key,source,name,paired,cancel)
    return {"id":key,"status":"queued","transport":"PC-to-Android private Wi-Fi"}

def transfer_status(key: str):
    with _guard:
        job=_jobs.get(key)
        if job is None:raise HTTPException(404,"Unknown transfer")
        return job.copy()

def cancel_transfer(key: str):
    with _guard:
        job=_jobs.get(key)
        if job is None:raise HTTPException(404,"Unknown transfer")
        if job["state"] in ("completed","failed","cancelled"):
            return {"ok":False,"state":job["state"]}
        _cancels[key].set()
    return {"ok":True,"state":"cancelling"}
