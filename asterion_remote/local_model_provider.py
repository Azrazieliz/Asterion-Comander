"""No-subscription local LLM adapter for the independent Control cycle engine.

Uses ONLY an explicitly configured loopback OpenAI-compatible inference server
(e.g. llama.cpp on owner's Windows machine). No cloud fallback, payment, model
download, auto-installation, hidden remote access or shell execution.

This provider returns generated TEXT for an independently authorized executor;
generated claims are NOT proof of project progress or permission to run tools.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_LOCAL = {"127.0.0.1", "::1", "localhost"}


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """A local inference server must never redirect a prompt outside loopback."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code,
            "local_inference_redirect_forbidden", headers, fp)



@dataclass(frozen=True)
class LocalModelConfig:
    endpoint: str = "http://127.0.0.1:8080/v1/chat/completions"
    model: str = "local"
    timeout_s: int = 90
    max_tokens: int = 2048
    temperature: float = 0.2
    system_instruction: str = (
        "You are Asterion's locally hosted development reasoning model. "
        "Only tool receipts and independent tests establish completed work. "
        "Do not fabricate files, commits, builds, installs or tool results."
    )

    def __post_init__(self):
        parsed = urllib.parse.urlsplit(self.endpoint)
        if (parsed.scheme != "http" or parsed.hostname not in _LOCAL or
                parsed.username is not None or parsed.password is not None or
                parsed.path != "/v1/chat/completions" or
                parsed.query or parsed.fragment or
                parsed.port is None or not (1 <= parsed.port <= 65535)):
            raise ValueError("local_inference_endpoint_must_be_loopback")
        if not _MODEL.fullmatch(self.model):
            raise ValueError("invalid_local_model_id")
        if not 5 <= self.timeout_s <= 600:
            raise ValueError("invalid_local_timeout")
        if not 16 <= self.max_tokens <= 8192:
            raise ValueError("invalid_output_token_budget")
        if not 0 <= self.temperature <= 1:
            raise ValueError("invalid_temperature")
        if not isinstance(self.system_instruction,str) or not 20 <= len(
            self.system_instruction) <= 4000:
            raise ValueError("invalid_local_system_instruction")


class LocalModelProvider:
    """Callable provider compatible with overnight_supervisor.advance_once."""

    def __init__(self, config: LocalModelConfig):
        self.config = config
        # Never honor HTTP(S)_PROXY, which could turn a local request into an
        # unexpected external paid/privacy-sensitive network operation.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPHandler(),
            _RefuseRedirect())

    def __call__(self, prompt: str, request_id: str) -> dict:
        if not isinstance(prompt, str) or not 20 <= len(prompt) <= 24000:
            raise ValueError("invalid_local_model_prompt")
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_.-]{7,99}", request_id):
            raise ValueError("invalid_model_turn_request_id")
        # Actual inference is never simulated. If the local server is absent,
        # this raises and the supervisor marks dispatch outcome as uncertain.
        data = json.dumps({
            "model": self.config.model,
            "stream": False,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {"role": "system", "content": self.config.system_instruction},
                {"role": "user", "content": prompt},
            ],
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            self.config.endpoint, data=data, method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "X-Asterion-Request-ID": request_id})
        with self.opener.open(req, timeout=self.config.timeout_s) as resp:
            if resp.status != 200:
                raise RuntimeError("local_model_http_error")
            limit = 2_000_000
            raw = resp.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("local_model_output_too_large")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("invalid_local_model_response")
        choices = obj.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("local_model_missing_choices")
        first = choices[0]
        if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
            raise ValueError("local_model_missing_message")
        answer = first["message"].get("content")
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 500000:
            raise ValueError("local_model_no_text_response")
        receipt = obj.get("id")
        if not isinstance(receipt, str) or not 8 <= len(receipt) <= 200:
            # Actual complete bytes can still supply a unique durable receipt
            # when a standards-compatible local engine omits optional "id".
            receipt = "local-sha256-" + hashlib.sha256(
                request_id.encode("utf-8") + b"\0" + raw).hexdigest()
        return {"message_id": receipt, "content": answer,
                "origin": "owner_local_loopback_inference",
                "model": self.config.model, "paid_cloud_used": False}
