"""Owner-scoped MCP stdio client for the native Asterion Intelligence tool plane.

A REAL MCP client, NOT the discontinued ChatGPT-to-Control HTTP MCP gateway.
This is intentionally additive and does NOT install/launch anything until
an authenticated owner explicitly configures a real local MCP binary, its
SHA-256 checksum and a per-tool allowlist. No shell=True, no random npx/uvx,
no automatic package downloads, no forwarded secret env, no unsolicited
tool execution, no paid service call. Process lifetime is bounded.

Supports MCP 2025 handshake over newline-delimited JSON stdio and the newer
2026-07-28 stateless protocol envelope. The server itself remains a third
party and must be audited/scoped before receiving tokens or local files.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

_SHA = re.compile(r"^[0-9a-f]{64}$")
_TOOL = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")
_MODERN = "2026-07-28"
_HANDSHAKE = {"2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"}
_PROTOCOLS = _HANDSHAKE | {_MODERN}
_LIMIT = 1_000_000
_MAX_ARGS = 32_000
_SENTINEL = object()


@dataclass(frozen=True)
class McpServerConfig:
    """The app UI must obtain these values through genuine owner approval."""
    executable: Path
    sha256: str
    arguments: tuple[str, ...] = ("stdio",)
    tools_allowed: frozenset[str] = frozenset()
    inherited_env: Mapping[str, str] = field(default_factory=dict, repr=False)
    protocol: str = "2025-11-25"
    timeout_s: float = 15.0

    def __post_init__(self) -> None:
        file = Path(self.executable)
        if not file.is_absolute() or not file.is_file():
            raise ValueError("mcp_server_binary_not_installed")
        if not isinstance(self.sha256, str) or not _SHA.fullmatch(self.sha256):
            raise ValueError("mcp_binary_sha256_required")
        actual = hashlib.file_digest(file.open("rb"), "sha256").hexdigest()
        if actual != self.sha256:
            raise ValueError("mcp_binary_fingerprint_mismatch")
        if self.protocol not in _PROTOCOLS:
            raise ValueError("unsupported_mcp_protocol")
        if not isinstance(self.arguments, tuple) or len(self.arguments) > 16 or any(
            not isinstance(arg, str) or not arg or len(arg) > 512 or
            "\0" in arg for arg in self.arguments
        ):
            raise ValueError("mcp_command_arguments_invalid")
        if not isinstance(self.tools_allowed, frozenset) or not self.tools_allowed or any(
            not isinstance(name, str) or not _TOOL.fullmatch(name)
            for name in self.tools_allowed
        ):
            raise ValueError("mcp_tool_approval_required")
        if not 1 <= self.timeout_s <= 120:
            raise ValueError("mcp_tool_timeout_invalid")
        if any(
            not isinstance(k,str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",k)
            or not isinstance(v,str) or "\0" in v or len(v)>4096
            for k,v in self.inherited_env.items()
        ):
            raise ValueError("invalid_mcp_environment")


class McpStdioClient:
    """One serialized, fail-closed stdio MCP subprocess connection."""

    def __init__(self, config: McpServerConfig):
        self.config=config
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._rx: queue.Queue = queue.Queue(maxsize=32)
        self._seq=0
        self._guard=threading.RLock()
        self._selected_version=config.protocol
        self._tool_names: set[str] = set()
        self._initialized=False
        self._error: str | None = None

    def __enter__(self) -> McpStdioClient:
        self.start()
        return self

    def __exit__(self, *_):
        self.close()

    def _make_env(self)->dict[str,str]:
        # Explicit list of process essentials, no inherited arbitrary tokens.
        names=("PATH","SYSTEMROOT","WINDIR","TEMP","TMP","HOME","USERPROFILE",
               "LOCALAPPDATA","APPDATA","LANG","LC_ALL","TZ")
        env={k:os.environ[k] for k in names if k in os.environ}
        # Secrets passed to MCP binary through env, not command or logs.
        env.update(self.config.inherited_env)
        return env

    def start(self)->None:
        with self._guard:
            if self._proc is not None:
                raise RuntimeError("mcp_connection_already_started")
            path=Path(self.config.executable)
            # Re-verify the hash at LAUNCH to reduce wrong binary execution.
            with path.open("rb") as stream:
                digest=hashlib.file_digest(stream,"sha256").hexdigest()
            if digest!=self.config.sha256:
                raise RuntimeError("mcp_binary_changed_before_start")
            self._proc=subprocess.Popen(
                [str(path),*self.config.arguments],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,shell=False,env=self._make_env(),
                bufsize=0,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            self._reader=threading.Thread(target=self._read_loop,daemon=True,
                                           name="asterion-mcp-stdio")
            self._reader.start()
            try:
                if self.config.protocol in _HANDSHAKE:
                    result=self._rpc("initialize",{
                        "protocolVersion":self.config.protocol,
                        "capabilities":{},
                        "clientInfo":{"name":"asterion-control","version":"0.9.31"}
                    })
                    chosen=result.get("protocolVersion")
                    if chosen not in _HANDSHAKE:
                        raise RuntimeError("mcp_protocol_negotiation_failed")
                    self._selected_version=chosen
                    self._send({"jsonrpc":"2.0",
                                "method":"notifications/initialized"})
                else:
                    # 2026 protocol eliminated the initialize exchange.
                    # Each request carries its identity/capabilities in _meta.
                    self._selected_version=_MODERN
                self._initialized=True
            except BaseException:
                self.close()
                raise

    def _read_loop(self)->None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            while True:
                frame=self._proc.stdout.readline(_LIMIT+1)
                if not frame:
                    break
                if len(frame)>_LIMIT or not frame.endswith(b"\n"):
                    self._error="mcp_frame_too_large_or_unframed"
                    break
                try:
                    obj=json.loads(frame)
                    if not isinstance(obj,dict) or obj.get("jsonrpc")!="2.0":
                        self._error="mcp_protocol_invalid_jsonrpc"
                        break
                except (ValueError,UnicodeDecodeError):
                    self._error="mcp_protocol_invalid_json"
                    break
                try:
                    self._rx.put_nowait(obj)
                except queue.Full:
                    self._error="mcp_reply_backpressure"
                    break
        except (OSError,ValueError):
            self._error="mcp_stream_terminated"
        finally:
            try:self._rx.put_nowait(_SENTINEL)
            except queue.Full:pass

    def _send(self,value:dict)->None:
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("mcp_transport_not_started")
        payload=(json.dumps(value,separators=(",",":"),ensure_ascii=False,
                            allow_nan=False)+"\n").encode("utf-8")
        if len(payload)>_LIMIT:
            raise ValueError("mcp_request_too_large")
        self._proc.stdin.write(payload)
        self._proc.stdin.flush()

    def _rpc(self,method:str,params:dict | None = None)->dict:
        if self._proc is None:
            raise RuntimeError("mcp_transport_not_started")
        self._seq+=1
        ident=self._seq
        args={} if params is None else dict(params)
        if self._selected_version==_MODERN:
            args.setdefault("_meta",{}).update({
                "io.modelcontextprotocol/protocolVersion":_MODERN,
                "io.modelcontextprotocol/clientInfo":{
                    "name":"asterion-control","version":"0.9.31"}})
        self._send({"jsonrpc":"2.0","id":ident,
                    "method":method,"params":args})
        # Deadline includes time spent answering server pings/notifications.
        import time
        until=time.monotonic()+self.config.timeout_s
        while True:
            left=until-time.monotonic()
            if left<=0:
                raise TimeoutError("mcp_response_timeout_outcome_unknown")
            try:entry=self._rx.get(timeout=left)
            except queue.Empty:
                raise TimeoutError("mcp_response_timeout_outcome_unknown")
            if entry is _SENTINEL:
                raise RuntimeError(self._error or "mcp_server_stopped")
            if "method" in entry and "id" in entry:
                # MCP servers can request ping. Never authorize sampling or
                # elicitation directly; they require separate owner approval.
                if entry["method"]=="ping":
                    self._send({"jsonrpc":"2.0","id":entry["id"],"result":{}})
                else:
                    self._send({"jsonrpc":"2.0","id":entry["id"],
                                "error":{"code":-32601,
                                         "message":"method_unavailable"}})
                continue
            if entry.get("id") != ident:
                if "method" in entry and "id" not in entry:
                    # Stateless server notifications, not tool results.
                    continue
                raise RuntimeError("mcp_unmatched_reply_id")
            if "error" in entry:
                # Avoid reflecting untrusted verbose server errors/secrets.
                raise RuntimeError("mcp_server_returned_error")
            result=entry.get("result")
            if not isinstance(result,dict):
                raise RuntimeError("mcp_result_not_object")
            return result

    def list_tools(self)->dict:
        with self._guard:
            if not self._initialized:
                raise RuntimeError("mcp_server_not_initialized")
            result=self._rpc("tools/list")
            listed=result.get("tools")
            if not isinstance(listed,list) or len(listed)>200:
                raise RuntimeError("mcp_invalid_tool_catalog")
            names=set()
            safe=[]
            for entry in listed:
                if not isinstance(entry,dict):
                    raise RuntimeError("mcp_invalid_tool_definition")
                name=entry.get("name")
                if not isinstance(name,str) or not _TOOL.fullmatch(name):
                    raise RuntimeError("mcp_invalid_tool_name")
                names.add(name)
                if name in self.config.tools_allowed:
                    safe.append({"name":name,"available":True,
                                 "owner_approved":True})
            self._tool_names=names
            return {"ok":True,"items":safe,"server_tools":len(listed),
                    "owner_authorized_tools":len(safe),
                    "secrets_exposed":False}

    def call_tool(self,name:str,arguments:dict)->dict:
        with self._guard:
            if not self._initialized:
                raise RuntimeError("mcp_server_not_initialized")
            if not isinstance(name,str) or name not in self.config.tools_allowed:
                raise PermissionError("mcp_tool_not_owner_approved")
            if name not in self._tool_names:
                raise RuntimeError("mcp_tool_not_discovered")
            if not isinstance(arguments,dict):
                raise ValueError("mcp_arguments_must_be_object")
            body=json.dumps(arguments,separators=(",",":"),
                            ensure_ascii=False,allow_nan=False)
            if len(body)>_MAX_ARGS:
                raise ValueError("mcp_tool_arguments_too_large")
            result=self._rpc("tools/call",{
                "name":name,"arguments":arguments})
            # Success is a PROTOCOL result, not verified project work.
            return {"ok":not bool(result.get("isError",False)),
                    "tool_name":name,"result":result,
                    "project_work_verified":False,
                    "mcp_server_attested":False}

    def close(self)->None:
        proc=self._proc
        self._proc=None
        self._initialized=False
        if proc is None:return
        try:
            if proc.stdin:proc.stdin.close()
            proc.wait(timeout=1.5)
        except (OSError,subprocess.TimeoutExpired):
            try:proc.terminate();proc.wait(timeout=1.5)
            except (OSError,subprocess.TimeoutExpired):
                try:proc.kill();proc.wait(timeout=1)
                except (OSError,subprocess.TimeoutExpired):pass
        finally:
            if proc.stdout:proc.stdout.close()
