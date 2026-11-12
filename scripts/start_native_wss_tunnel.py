"""Restartable owner-authenticated native WSS SSH forwarding.

This is NOT a ChatGPT plugin or an MCP gateway. It forwards the existing
public phone WSS hostname to the native phone-only relay on localhost:8995.
Reuses the ORIGINAL SSH identity and pinned host key without rotation.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import httpx

STATE=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
FLAG=STATE/"native-wss-enabled.flag"
# Historical *filenames* must be reused to preserve the original SSH identity.
KEY=STATE/"mcp-stable-ssh-ed25519"
KNOWN=STATE/"mcp-stable-known-hosts"
LOCK=STATE/"native-wss-ssh-supervisor.lock"
LOG=STATE/"native-wss-ssh.log"
HOST="proxy.tunnl.gg"
PUBLIC="https://wise-eagle-c8b55706.tunnl.gg"
LOCAL="http://127.0.0.1:8995/healthz"
EXPECTED_FINGERPRINT="SHA256:5uQ6VobmUpY4wyMmm5jnAwFtt3aX06WYDDM4ER+2WUw"

def emit(message):
    LOG.parent.mkdir(parents=True,exist_ok=True)
    if LOG.exists() and LOG.stat().st_size>1024*1024:
        LOG.replace(LOG.with_suffix(".log.old"))
    with LOG.open("a",encoding="utf-8") as output:
        output.write(time.strftime("%Y-%m-%d %H:%M:%S ")+message+"\n")

def local_ready():
    try:
        with httpx.Client(timeout=3,trust_env=False) as client:
            r=client.get(LOCAL)
        return r.status_code==200 and r.json().get("service")=="asterion-native-phone-wss"
    except (httpx.HTTPError,ValueError,KeyError):
        return False

def public_ready():
    try:
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
            r=client.get(PUBLIC+"/healthz")
        return r.status_code==200 and r.json().get("service")=="asterion-native-phone-wss"
    except (httpx.HTTPError,ValueError,KeyError):
        return False

def main():
    if os.name!="nt":raise RuntimeError("Windows owner worker only")
    if not KEY.is_file() or not KNOWN.is_file():
        raise RuntimeError("Existing trusted SSH identity or known-host file missing; will not rotate")
    ssh=shutil.which("ssh")
    keygen=shutil.which("ssh-keygen")
    if not ssh or not keygen:
        raise RuntimeError("Existing Windows OpenSSH installation not available")
    check=subprocess.run([keygen,"-lf",str(KNOWN)],capture_output=True,text=True,timeout=8,
                         creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if EXPECTED_FINGERPRINT not in check.stdout:
        raise RuntimeError("Pinned SSH host key unexpectedly changed")
    import msvcrt
    with LOCK.open("a+b") as lock:
        # Windows denies reading another process's byte-range lock before
        # msvcrt.locking can detect the owner. Check size without reading.
        if os.fstat(lock.fileno()).st_size == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            emit("NATIVE_WSS_SSH_ALREADY_SUPERVISED")
            return
        backoff=3
        while FLAG.is_file():
            if not local_ready():
                emit("NATIVE_WSS_LOCAL_RELAY_NOT_READY")
                time.sleep(3)
                continue
            cmd=[ssh,"-n","-tt","-i",str(KEY),
                 "-o","IdentitiesOnly=yes","-o","BatchMode=yes",
                 "-o","StrictHostKeyChecking=yes",
                 "-o","UserKnownHostsFile="+str(KNOWN),
                 "-o","ServerAliveInterval=25","-o","ServerAliveCountMax=3",
                 "-o","ExitOnForwardFailure=yes",
                 "-R","80:127.0.0.1:8995","stable@"+HOST]
            emit("NATIVE_WSS_STABLE_SSH_CONNECTING")
            proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
               stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",
               creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            urls=[]
            def capture():
                if proc.stdout is None:return
                for line in proc.stdout:
                    match=re.search(r"https://[a-z0-9-]+\.tunnl\.gg",line,re.I)
                    if match and len(urls)<5:urls.append(match.group(0))
            threading.Thread(target=capture,daemon=True).start()
            for _ in range(8):
                if proc.poll() is not None or not FLAG.exists():break
                time.sleep(2)
                if public_ready():break
            if proc.poll() is None and public_ready() and (not urls or PUBLIC in urls):
                emit("NATIVE_WSS_PUBLIC_ENDPOINT_VERIFIED")
                backoff=3
            elif urls and any(u!=PUBLIC for u in urls):
                emit("NATIVE_WSS_HOSTNAME_MISMATCH_REFUSING_ROUTE")
                proc.terminate()
                raise RuntimeError("Public stable WSS hostname changed")
            else:
                emit("NATIVE_WSS_PUBLIC_ENDPOINT_UNVERIFIED")
            while FLAG.exists() and proc.poll() is None:time.sleep(3)
            if proc.poll() is None:proc.terminate()
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:proc.kill()
            if FLAG.exists():
                emit("NATIVE_WSS_SSH_RECONNECTING")
                time.sleep(backoff)
                backoff=min(45,backoff*2)
        emit("NATIVE_WSS_SSH_SUPERVISOR_STOPPED")

if __name__=="__main__":
    try:main()
    except Exception as exc:
        emit("NATIVE_WSS_SSH_FATAL="+type(exc).__name__)
        raise
