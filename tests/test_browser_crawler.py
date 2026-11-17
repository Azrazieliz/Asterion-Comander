"""Browser crawler acceptance: real parsing, robots gate, metadata and SSRF policy."""
import hashlib
import socket

import pytest
from fastapi import HTTPException
from asterion_remote import browser_crawler as browser


def test_reject_private_and_privilege_bearing_urls():
    for url in ("http://example.com/", "file:///etc/passwd",
                "https://127.0.0.1/", "https://192.168.1.10/",
                "https://8.8.8.8:8995/", "https://user:pass@example.com/"):
        with pytest.raises(HTTPException):
            browser.validated_public_https(url)


def test_reject_dns_answer_containing_private_address(monkeypatch):
    def answers(*a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    monkeypatch.setattr(browser.socket, "getaddrinfo", answers)
    with pytest.raises(HTTPException) as exc:
        browser.validated_public_https("https://research.example/post")
    assert exc.value.status_code == 403


def test_static_html_capture_has_exact_provenance(monkeypatch):
    monkeypatch.setattr(browser, "validated_public_https",
                        lambda url: ("research.example", "8.8.8.8", "/post"))
    page = (b"<html><head><title>Research evidence</title>"
            b'<meta property="article:published_time" content="2026-11-17">'
            b"</head><body>Hello searchable page"
            b'<script>private = "not visible"</script>'
            b'<a href="/next" title="Next">Continue</a>'
            b'<img src="/photo.jpg" alt="Portrait">'
            b"</body></html>")
    calls = []
    def fetch(url, limit):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return browser.Fetched(404, b"", {})
        return browser.Fetched(200, page, {"content-type": "text/html; charset=utf-8"})
    monkeypatch.setattr(browser, "_fetch", fetch)
    report = browser.capture_public("https://research.example/post")
    assert report["ok"] is True
    assert report["title"] == "Research evidence"
    assert "Hello searchable page" in report["text"]
    assert "not visible" not in report["text"]
    assert report["published_claim"] == "2026-11-17"
    assert report["content_sha256"] == hashlib.sha256(page).hexdigest()
    assert report["rendering"] == "static_http_no_javascript"
    assert report["links"][0]["url"] == "https://research.example/next"
    assert report["media"][0]["url"] == "https://research.example/photo.jpg"
    assert calls == ["https://research.example/robots.txt",
                     "https://research.example/post"]


def test_robots_denial_prevents_target_fetch(monkeypatch):
    monkeypatch.setattr(browser, "validated_public_https",
                        lambda url: ("blocked.example", "8.8.8.8", "/"))
    urls = []
    def fetch(url, limit):
        urls.append(url)
        if url.endswith("/robots.txt"):
            return browser.Fetched(200, b"User-agent: *\nDisallow: /\n", {})
        raise AssertionError("Disallowed body fetched")
    monkeypatch.setattr(browser, "_fetch", fetch)
    with pytest.raises(HTTPException) as exc:
        browser.capture_public("https://blocked.example/secret")
    assert exc.value.status_code == 403
    assert urls == ["https://blocked.example/robots.txt"]


def test_redirect_must_validate_public_destination(monkeypatch):
    def fake_fetch(url, limit):
        if url.endswith("/robots.txt"):
            return browser.Fetched(404, b"", {})
        return browser.Fetched(302, b"", {"location": "https://127.0.0.1/health"})
    monkeypatch.setattr(browser, "_fetch", fake_fetch)
    monkeypatch.setattr(browser.socket, "getaddrinfo",
        lambda host,*a,**kw:[(socket.AF_INET,socket.SOCK_STREAM,6,"",
            ("127.0.0.1" if host=="127.0.0.1" else "8.8.8.8",443))])
    with pytest.raises(HTTPException) as exc:
        browser.capture_public("https://public.example/source")
    assert exc.value.status_code == 403


def test_robots_server_error_is_not_treated_as_allowed(monkeypatch):
    monkeypatch.setattr(browser, "validated_public_https",
                        lambda url: ("site.example", "8.8.8.8", "/"))
    monkeypatch.setattr(browser, "_fetch",
                        lambda url, limit:browser.Fetched(503,b"",{}))
    with pytest.raises(HTTPException) as exc:
        browser.capture_public("https://site.example/")
    assert exc.value.status_code == 403
