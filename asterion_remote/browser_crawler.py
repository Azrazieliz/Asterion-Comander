"""Asterion Browser public-page crawler and evidence extractor.

Purposefully separate from the interactive Android WebView browser and every
specialist app parser. A crawl is read-only, robots-aware, bounded and explicitly
marked as static HTML (not proof that JavaScript was rendered). Connections are
TLS-verified and pinned to a prevalidated PUBLIC IP to reject local-network
and DNS-rebinding SSRF targets. No cookies, credentials or paid service.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .security import require_token

router = APIRouter(prefix="/api/v1/browser", dependencies=[Depends(require_token)])
USER_AGENT = "AsterionBrowser/1.0 (+owner-requested-public-research)"
MAX_BODY = 1_500_000
MAX_ROBOTS = 262_144
_MIN_HOST_INTERVAL = 1.0
_rate_lock = threading.Lock()
_last_request: dict[str, float] = {}


class CaptureRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    text_limit: int = Field(default=20_000, ge=1000, le=50_000)


@dataclass(frozen=True)
class Fetched:
    status: int
    content: bytes
    headers: dict[str, str]


class _PinnedHttps(http.client.HTTPSConnection):
    """Dial a validated numeric address while TLS verifies the original host."""
    def __init__(self, host: str, ip: str, timeout: float):
        super().__init__(host, port=443, timeout=timeout,
                         context=ssl.create_default_context())
        self._verified_ip = ip

    def connect(self):
        plain = socket.create_connection((self._verified_ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(plain, server_hostname=self.host)
        except Exception:
            plain.close()
            raise


def validated_public_https(url: str) -> tuple[str, str, str]:
    if not isinstance(url, str) or len(url) > 2048 or any(ord(x) < 32 for x in url):
        raise HTTPException(422, "Invalid public HTTPS URL")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(422, "Malformed public URL") from exc
    if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password:
        raise HTTPException(422, "Only credential-free HTTPS websites are crawlable")
    if port not in (None, 443):
        raise HTTPException(422, "Nonstandard website ports are not crawlable")
    if parsed.fragment:
        parsed = parsed._replace(fragment="")
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise HTTPException(502, "Public website DNS lookup failed") from exc
    resolved = [row[4][0] for row in addresses]
    if not resolved or any(not ipaddress.ip_address(ip).is_global for ip in resolved):
        raise HTTPException(403, "Private, reserved or mixed-address hosts are not crawlable")
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return host, resolved[0], path


def _rate(host: str) -> None:
    with _rate_lock:
        now = time.monotonic()
        delay = _MIN_HOST_INTERVAL - (now - _last_request.get(host, now - _MIN_HOST_INTERVAL))
        _last_request[host] = now + max(0.0, delay)
    if delay > 0:
        time.sleep(delay)


def _fetch(url: str, limit: int) -> Fetched:
    host, ip, path = validated_public_https(url)
    _rate(host)
    conn = _PinnedHttps(host, ip, timeout=9.0)
    try:
        conn.request("GET", path, headers={
            "Host": host, "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8,*/*;q=0.1",
            "Accept-Encoding": "identity",
            "Cookie": "",
        })
        response = conn.getresponse()
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise HTTPException(413, "Public page exceeds bounded capture size")
        headers = {k.lower(): v for k, v in response.getheaders()}
        return Fetched(response.status, raw, headers)
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise HTTPException(502, "Verified public website request failed: "
                            + type(exc).__name__) from exc
    finally:
        conn.close()


class _Extract(HTMLParser):
    def __init__(self, origin: str):
        super().__init__(convert_charrefs=True)
        self.origin = origin
        self.title: list[str] = []
        self.words: list[str] = []
        self.links: list[dict] = []
        self.media: list[dict] = []
        self.published: str | None = None
        self._title = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            return
        if tag == "title":
            self._title = True
        if tag == "meta" and attrs.get("property", "").lower() in (
                "article:published_time", "article:modified_time"):
            self.published = self.published or attrs.get("content")
        if tag == "a" and len(self.links) < 60 and attrs.get("href"):
            url = urljoin(self.origin, attrs["href"])
            if urlsplit(url).scheme in ("http", "https"):
                self.links.append({"url": url, "label": (attrs.get("title") or "")[:120]})
        if tag in ("img", "video", "audio", "source") and len(self.media) < 50:
            raw = attrs.get("src") or attrs.get("data-src")
            if raw:
                url = urljoin(self.origin, raw)
                if urlsplit(url).scheme in ("http", "https"):
                    self.media.append({"kind": tag, "url": url,
                                       "alt": (attrs.get("alt") or "")[:160]})

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)
        if tag == "title":
            self._title = False

    def handle_data(self, data):
        if self._skip:
            return
        val = " ".join(data.split())
        if not val:
            return
        if self._title:
            self.title.append(val)
        else:
            self.words.append(val)


def _robots(url: str) -> str:
    parsed = urlsplit(url)
    robots_url = urlunsplit(("https", parsed.netloc, "/robots.txt", "", ""))
    response = _fetch(robots_url, MAX_ROBOTS)
    if response.status in (404, 410):
        return "not_present"
    if response.status != 200:
        raise HTTPException(403, "Robots policy not readable; crawl declined")
    reader = RobotFileParser()
    reader.parse(response.content.decode("utf-8", "replace").splitlines())
    if not reader.can_fetch(USER_AGENT, url):
        raise HTTPException(403, "Website robots policy disallows this crawler")
    return "allowed"


def capture_public(url: str, text_limit: int = 20_000) -> dict:
    """Bounded public HTTP capture. Does NOT execute JavaScript or submit forms."""
    original = url
    visited: set[str] = set()
    redirects = 0
    for _ in range(5):
        validated_public_https(url)
        if url in visited:
            raise HTTPException(409, "Website redirect loop")
        visited.add(url)
        robots = _robots(url)
        fetched = _fetch(url, MAX_BODY)
        if fetched.status in (301, 302, 303, 307, 308):
            location = fetched.headers.get("location", "")
            if not location:
                raise HTTPException(502, "Redirect missing destination")
            url = urljoin(url, location)
            redirects += 1
            continue
        if fetched.status != 200:
            raise HTTPException(502, "Remote HTTP status " + str(fetched.status)
                                + "; not classified as geographic blocking")
        content_type = fetched.headers.get("content-type", "").lower()
        if not any(kind in content_type for kind in ("text/html", "application/xhtml+xml", "text/plain")):
            raise HTTPException(415, "Non-document media belongs to the partner app or Download Manager")
        charset = "utf-8"
        match = re.search(r"charset=([a-z0-9_-]+)", content_type)
        if match:
            charset = match.group(1)
        try:
            decoded = fetched.content.decode(charset, "replace")
        except LookupError:
            decoded = fetched.content.decode("utf-8", "replace")
        extraction = _Extract(url)
        if "text/html" in content_type or "xhtml" in content_type:
            extraction.feed(decoded)
            title = " ".join(extraction.title)[:300]
            text = " ".join(extraction.words)
        else:
            title = urlsplit(url).hostname or ""
            text = decoded
        text = text[:text_limit]
        return {
            "ok": True,
            "original_url": original,
            "source_url": url,
            "source_host": urlsplit(url).hostname,
            "captured_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "http_status": fetched.status,
            "redirects": redirects,
            "robots": robots,
            "rendering": "static_http_no_javascript",
            "javascript_required_suspected": bool("<script" in decoded.lower() and len(text) < 120),
            "title": title,
            "text": text,
            "links": extraction.links,
            "media": extraction.media,
            "published_claim": extraction.published,
            "content_sha256": hashlib.sha256(fetched.content).hexdigest(),
            "extraction_method": "htmlparser_visible_text_v1",
            "identity_authenticated": False,
            "provenance": "observed_http_content_not_verified_truth",
        }
    raise HTTPException(409, "Too many website redirects")


@router.post("/capture")
def public_capture(req: CaptureRequest):
    return capture_public(req.url, req.text_limit)
