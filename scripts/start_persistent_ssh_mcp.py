"""Persistent, owner-controlled, direct HTTPS ingress for Asterion Control MCP.

No GitHub command transport at runtime. One ssh key = one stable HTTPS URL
across SSH reconnects. Never expose native Android / Windows agent ports.
The published endpoint is exclusively the existing bearer-authenticated MCP
gateway bound to 127.0.0.1:8995.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

STATE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
ROOT = Path(__file__).resolve().parents[1]
SSH_KEY = STATE / "mcp-stable-ssh-ed25519"
SSH_URL = STATE / "mcp-stable-https-url.txt"
TOKEN = STATE / "mcp-gateway-token.txt"
FLAG = STATE / "mcp-stable-ssh-enabled.flag"
LOG = STATE / "mcp-stable-ssh.log"
LOCAL = "http://127.0.0.1:8995/mcp"
HOST = "proxy.tunnl.gg"
EXPECTED_HOST_SHA256 = "SHA256:5uQ6VobmUpY4wyMmm5jnAwFtt3aX06WYDDM4ER+2WUw"
MAX_BACKOFF = 45

def emit(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    try:
        if LOG.exists() and LOG.stat().st_size > 1024 * 1024:
            LOG.replace(LOG.with_suffix(".log.old"))
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

def prepare_key() -> None:
    sshgen = shutil.which("ssh-keygen")
    if not sshgen:
        raise RuntimeError("OpenSSH ssh-keygen unavailable")
    if SSH_KEY.exists() and not SSH_KEY.with_suffix(SSH_KEY.suffix + ".pub").exists():
        raise RuntimeError("Existing SSH identity is missing public key; refusing key rotation")
    if not SSH_KEY.exists():
        r = subprocess.run([sshgen, "-q", "-t", "ed25519", "-N", "",
                            "-f", str(SSH_KEY), "-C", "asterion-control-mcp"],
                           capture_output=True, text=True, timeout=25)
        if r.returncode != 0:
            raise RuntimeError("Could not generate private SSH tunnel identity")
        if os.name == "nt":
            owner = os.environ.get("USERNAME", "")
            if owner:
                subprocess.run(["icacls", str(SSH_KEY), "/inheritance:r",
                                "/grant:r", owner + ":(R)"],
                               capture_output=True, timeout=10)
    if not SSH_KEY.exists():
        raise RuntimeError("Persistent tunnel identity not available")

def gateway_up() -> subprocess.Popen | None:
    """Start existing local MCP gateway only if not already authenticated."""
    secret = TOKEN.read_text(encoding="utf8").strip()
    if len(secret) < 43:
        raise RuntimeError("Existing Control MCP credential invalid")
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                       "clientInfo": {"name": "asterion-stable-ingress", "version": "1"}}}
    headers = {"Authorization": "Bearer " + secret,
               "Accept": "application/json, text/event-stream"}
    def probe(url: str, timeout: float = 4) -> bool:
        try:
            with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
                r = client.post(url, json=body, headers=headers)
                return r.status_code == 200 and r.json().get("result", {}).get(
                    "serverInfo", {}).get("name") == "asterion-control"
        except (httpx.HTTPError, ValueError, KeyError):
            return False
    if probe(LOCAL):
        emit("CONTROL_LOCAL_MCP_AUTH_OK")
        return None
    if os.name == "nt":
        check = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            "(Get-NetTCPConnection -LocalPort 8995 -State Listen "
            "-ErrorAction SilentlyContinue | Measure-Object).Count"],
            capture_output=True, text=True, timeout=10)
        if check.stdout.strip() != "0":
            raise RuntimeError("Local port 8995 is occupied by an unknown or inaccessible service")
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)
    out = (STATE / "mcp-stable-gateway.stdout.log").open("a", encoding="utf-8")
    err = (STATE / "mcp-stable-gateway.stderr.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([str(py), "-m", "uvicorn", "asterion_remote.mcp_gateway:app",
                             "--host", "127.0.0.1", "--port", "8995"],
                            cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=out,
                            stderr=err, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(24):
        if proc.poll() is not None:
            raise RuntimeError("Control local MCP gateway exited on startup")
        if probe(LOCAL):
            emit("CONTROL_LOCAL_MCP_AUTH_OK")
            return proc
        time.sleep(0.5)
    raise RuntimeError("Control local MCP gateway authentication failed")

def host_key() -> None:
    """Verify the documented SSH server key before any private tunneling."""
    scan, keygen = shutil.which("ssh-keyscan"), shutil.which("ssh-keygen")
    if not scan or not keygen:
        raise RuntimeError("SSH key verification tools are unavailable")
    r = subprocess.run([scan, "-t", "ed25519", "-T", "8", HOST],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       text=True, timeout=12)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("SSH host key could not be retrieved")
    fingerprint = subprocess.run([keygen, "-lf", "-"],
                                 input=r.stdout, capture_output=True,
                                 text=True, timeout=8)
    if EXPECTED_HOST_SHA256 not in fingerprint.stdout:
        raise RuntimeError("Tunnel server host key fingerprint mismatch; connection refused")
    known = STATE / "mcp-stable-known-hosts"
    known.write_text(r.stdout, encoding="utf-8")
    emit("CONTROL_STABLE_SSH_HOST_KEY_VERIFIED")

def verify_public(url: str) -> bool:
    secret = TOKEN.read_text(encoding="utf8").strip()
    body = {"jsonrpc": "2.0", "id": 19, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                       "clientInfo": {"name": "asterion-public-check", "version": "1"}}}
    headers = {"Authorization": "Bearer " + secret,
               "Accept": "application/json, text/event-stream"}
    try:
        with httpx.Client(timeout=18, follow_redirects=False, trust_env=False) as client:
            r = client.post(url, json=body, headers=headers)
            if r.status_code != 200 or r.json().get("result", {}).get(
                    "serverInfo", {}).get("name") != "asterion-control":
                return False
            anonymous = client.post(url, json=body,
                                    headers={"Accept": "application/json, text/event-stream"})
            return anonymous.status_code == 401
    except (httpx.HTTPError, ValueError, KeyError):
        return False

def run() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    FLAG.touch(exist_ok=True)
    if os.name != "nt":
        raise RuntimeError("The current supervisor is intended for the authorized Control Windows worker")
    # Win32 advisory lock prevents duplicate tunnel supervisors.
    import msvcrt
    lockfile = (STATE / "mcp-stable-ssh-supervisor.lock").open("a+b")
    if lockfile.tell() == 0:
        lockfile.write(b"0")
        lockfile.flush()
    lockfile.seek(0)
    try:
        msvcrt.locking(lockfile.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        emit("CONTROL_STABLE_INGRESS_ALREADY_RUNNING")
        return
    prepare_key()
    host_key()
    gateway_up()
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("Windows OpenSSH client unavailable")
    backoff = 3
    known = STATE / "mcp-stable-known-hosts"
    while FLAG.exists():
        cmd = [ssh, "-v", "-n", "-T", "-i", str(SSH_KEY),
               "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
               "-o", "StrictHostKeyChecking=yes",
               "-o", "UserKnownHostsFile=" + str(known),
               "-o", "ServerAliveInterval=25", "-o", "ServerAliveCountMax=3",
               "-o", "ExitOnForwardFailure=yes",
               "-R", "80:127.0.0.1:8995", "stable@" + HOST, "output=json"]
        emit("CONTROL_STABLE_SSH_CONNECTING")
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", bufsize=1,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        url_ready = threading.Event()
        url_holder = {"url": None}
        def reader() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                if len(line) > 8192:
                    continue
                try:
                    evt = json.loads(line)
                except (ValueError, TypeError):
                    evt = {}
                    emit("CONTROL_STABLE_SSH_HANDSHAKE=" + line.strip()[:230])
                values = [str(evt.get(k, "")) for k in ("url", "public_url", "https_url", "message")]
                values.append(line)
                for candidate in values:
                    match = re.search(r"https://[a-z0-9-]+\.tunnl\.gg(?:/|\\b)", candidate, re.I)
                    if match:
                        url_holder["url"] = match.group(0).rstrip("/")
                        url_ready.set()
                if "error" in evt:
                    emit("CONTROL_STABLE_SSH_REMOTE_ERROR")
        t = threading.Thread(target=reader, daemon=True)
        t.start()
        url_ready.wait(timeout=30)
        url = url_holder["url"]
        if url is not None and proc.poll() is None:
            endpoint = url + "/mcp"
            if verify_public(endpoint):
                if SSH_URL.exists() and SSH_URL.read_text(encoding="utf8").strip() not in ("", endpoint):
                    emit("CONTROL_STABLE_SSH_HOSTNAME_CHANGED_UNEXPECTEDLY")
                    proc.terminate()
                    raise RuntimeError("Persistent URL identity changed unexpectedly")
                SSH_URL.write_text(endpoint, encoding="utf8")
                emit("CONTROL_STABLE_MCP_PUBLIC_AUTH_VERIFIED=" + endpoint)
                backoff = 3
            else:
                emit("CONTROL_STABLE_MCP_PUBLIC_NOT_VERIFIED")
        else:
            emit("CONTROL_STABLE_SSH_PUBLIC_URL_NOT_RETURNED")
            # Do not keep a stalled, unauthenticated SSH process forever.
            if proc.poll() is None:
                proc.terminate()
        while FLAG.exists() and proc.poll() is None:
            time.sleep(3)
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        emit("CONTROL_STABLE_SSH_RECONNECT")
        if FLAG.exists():
            time.sleep(backoff)
            backoff = min(MAX_BACKOFF, backoff * 2)

if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        emit("CONTROL_STABLE_SSH_FATAL=" + str(exc)[:240])
        sys.exit(1)
