"""Asterion Shared Browser: actual, bounded external webpage reading.

A common research/navigation engine for Intelligence, Game/Codex and other
owner-approved apps. It intentionally does NOT implement Rounder's editor,
Downloader's media extractors or model-training data collection.

HTTPS is certificate-verified; the DNS-selected public address is pinned for
the TCP connection (rather than resolved a second time for the socket),
blocking private/LAN/localhost SSRF and common DNS rebinding. Redirects
are individually reauthorized. HTML/scripts are never executed server-side.

.onion URLs are never sent to DNS or clearnet. They require an already running
owner-configured *local Tor SOCKS5* process and the Tor mode flag; a missing
Tor process fails closed. No Tor exit node/location or anonymity is promised.
"""
from __future__ import annotations

import hashlib
import html
import http.client
from html.parser import HTMLParser
import ipaddress
import os
import re
import socket
import ssl
import struct
import time
from typing import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

_ALLOWED_CONTENT=("text/html","text/plain","application/json",
                  "application/xml","text/xml","application/xhtml+xml")
_MAX_URL=2048
_MAX_BODY=1_000_000
_MAX_REDIRECTS=3
_MAX_LINKS=35
_MAX_TEXT=12000
_USER_AGENT="AsterionControlBrowser/1.0 (owner-initiated research)"
_ONION=re.compile(r"^[a-z2-7]{56}\.onion$",re.IGNORECASE)
_HOST=re.compile(r"^[a-z0-9.-]{1,253}$",re.I)


def _url(value:str, *, onion_mode:bool)->tuple[str,str,int,str]:
    if not isinstance(value,str) or not 8<=len(value)<=_MAX_URL:
        raise ValueError("invalid_browser_url")
    parts=urlsplit(value)
    if (parts.scheme not in {"http","https"} or not parts.hostname or
        parts.username is not None or parts.password is not None or
        parts.fragment or "\\" in value or
        any(ord(c)<32 for c in value)):
        raise ValueError("untrusted_browser_url")
    try:
        hostname=parts.hostname.encode("idna").decode("ascii").lower()
    except (UnicodeError,ValueError) as exc:
        raise ValueError("invalid_browser_hostname") from exc
    if not _HOST.fullmatch(hostname) or ".." in hostname or hostname.endswith("."):
        raise ValueError("invalid_browser_hostname")
    is_onion=hostname.endswith(".onion")
    if is_onion and not _ONION.fullmatch(hostname):
        raise ValueError("invalid_tor_onion_address")
    if onion_mode!=is_onion:
        raise ValueError("tor_and_clearnet_modes_must_be_separate")
    if hostname in {"localhost","localhost.localdomain"}:
        raise PermissionError("localhost_browser_access_forbidden")
    try:port=parts.port or (443 if parts.scheme=="https" else 80)
    except ValueError as exc:raise ValueError("invalid_browser_port") from exc
    if port not in {80,443}:
        raise ValueError("browser_port_not_authorized")
    path=parts.path or "/"
    if parts.query:path+="?"+parts.query
    if len(path)>1800:
        raise ValueError("browser_request_path_too_long")
    url=urlunsplit((parts.scheme,hostname+(
        ":"+str(port) if port not in {80 if parts.scheme=="http" else 443}
        else ""),parts.path or "/",parts.query,""))
    return url,hostname,port,path


def _public_addresses(host:str,port:int,
                      resolver:Callable|None=None)->list[str]:
    # Don't allow known "private" DNS domains to leak into local resolvers.
    if host.endswith((".local",".localhost",".internal",".test",".invalid")):
        raise PermissionError("local_domain_forbidden")
    try:
        literal=ipaddress.ip_address(host)
        addresses=[literal]
    except ValueError:
        resolve=resolver or socket.getaddrinfo
        try:
            records=resolve(host,port,type=socket.SOCK_STREAM)
        except (OSError,ValueError) as exc:
            raise RuntimeError("browser_public_dns_resolution_failed") from exc
        addresses=[]
        for record in records:
            try:addresses.append(ipaddress.ip_address(record[4][0]))
            except (ValueError,IndexError,TypeError):
                raise ValueError("browser_dns_invalid_record")
    if not addresses or any(not a.is_global for a in addresses):
        raise PermissionError("browser_dns_includes_nonpublic_address")
    return [str(a) for a in addresses]


def _socks5_onion(host:str,port:int,timeout_s:float)->socket.socket:
    if os.getenv("ASTERION_TOR_ENABLED","0")!="1":
        raise RuntimeError("owner_tor_proxy_not_enabled")
    proxy=os.getenv("ASTERION_TOR_SOCKS_HOST","127.0.0.1")
    if proxy not in {"127.0.0.1","::1"}:
        raise ValueError("tor_proxy_must_be_local_loopback")
    try:proxy_port=int(os.getenv("ASTERION_TOR_SOCKS_PORT","9050"))
    except ValueError as exc:raise ValueError("invalid_tor_proxy_port") from exc
    if not 1<=proxy_port<=65535:
        raise ValueError("invalid_tor_proxy_port")
    sock=socket.create_connection((proxy,proxy_port),timeout=timeout_s)
    sock.settimeout(timeout_s)
    try:
        sock.sendall(b"\x05\x01\x00")
        if _recv(sock,2)!=b"\x05\x00":
            raise RuntimeError("tor_socks5_no_auth_handshake_failed")
        name=host.encode("ascii")
        sock.sendall(b"\x05\x01\x00\x03"+bytes([len(name)])+
                     name+struct.pack("!H",port))
        head=_recv(sock,4)
        if head[:2]!=b"\x05\x00":
            raise RuntimeError("tor_onion_connection_failed")
        if head[3]==1:_recv(sock,4)
        elif head[3]==3:_recv(sock,_recv(sock,1)[0])
        elif head[3]==4:_recv(sock,16)
        else:raise RuntimeError("tor_socks5_invalid_bind_address")
        _recv(sock,2)
        return sock
    except BaseException:
        sock.close()
        raise


def _recv(sock:socket.socket,count:int)->bytes:
    result=b""
    while len(result)<count:
        chunk=sock.recv(count-len(result))
        if not chunk:raise RuntimeError("truncated_browser_transport")
        result+=chunk
    return result


class _Extract(HTMLParser):
    def __init__(self,base:str):
        super().__init__(convert_charrefs=True)
        self.base=base
        self.title=[]
        self.links=[]
        self.words=[]
        self._title=False
        self._hidden=0
        self._tags=[]
    def handle_starttag(self,tag,attrs):
        self._tags.append(tag)
        if tag=="title":self._title=True
        if tag in {"script","style","svg","template"}:self._hidden+=1
        if tag=="a" and len(self.links)<_MAX_LINKS:
            link=dict(attrs).get("href")
            if link and len(link)<1000:
                absolute=urljoin(self.base,link)
                try:_url(absolute,onion_mode=self.base.endswith(".onion"))
                except (ValueError,PermissionError):continue
                self.links.append(absolute)
    def handle_endtag(self,tag):
        if tag=="title":self._title=False
        if tag in {"script","style","svg","template"} and self._hidden:
            self._hidden-=1
        if self._tags:self._tags.pop()
    def handle_data(self,data):
        if self._hidden:return
        clean=" ".join(data.split())
        if not clean:return
        if self._title and sum(map(len,self.title))<250:self.title.append(clean[:250])
        if sum(map(len,self.words))<_MAX_TEXT:self.words.append(clean[:_MAX_TEXT])


def _parse_body(content_type:str,body:bytes,url:str)->tuple[str,str,list[str]]:
    charset="utf-8"
    m=re.search(r"charset\s*=\s*['\"]?([a-zA-Z0-9_-]+)",content_type,re.I)
    if m and m.group(1).lower() in {"utf-8","iso-8859-1","windows-1252"}:
        charset=m.group(1)
    text=body.decode(charset,errors="replace")
    if "html" not in content_type.lower():
        return "",text[:_MAX_TEXT],[]
    parser=_Extract(url)
    parser.feed(text[:300_000])
    return " ".join(parser.title)[:250]," ".join(parser.words)[:_MAX_TEXT],parser.links


def fetch(url:str, *, tor:bool=False, timeout_s:float=9.0,
          resolver:Callable|None=None,
          dialer:Callable|None=None)->dict:
    """Owner-initiated actual HTTP(S) read, no JavaScript or media download.

    dialer is for isolation tests; production opens only a vetted public IP or
    the explicitly enabled local Tor SOCKS tunnel. No requests are performed
    at import or Control startup.
    """
    if not isinstance(timeout_s,(int,float)) or not 1<=timeout_s<=20:
        raise ValueError("invalid_browser_timeout")
    original,_,_,_=_url(url,onion_mode=tor)
    seen=set()
    current=original
    started=time.monotonic()
    redirects=0
    while True:
        normalized,host,port,path=_url(current,onion_mode=tor)
        if normalized in seen:raise RuntimeError("browser_redirect_loop")
        seen.add(normalized)
        if tor:
            # Never resolve .onion via system DNS or direct outgoing socket.
            create=lambda:_socks5_onion(host,port,timeout_s)
        else:
            ips=_public_addresses(host,port,resolver=resolver)
            target=ips[0]
            create=(lambda: dialer(target,port,timeout_s)) if dialer else (
                lambda:socket.create_connection((target,port),timeout=timeout_s))
        sock=create()
        try:
            sock.settimeout(timeout_s)
            if normalized.startswith("https://"):
                sock=ssl.create_default_context().wrap_socket(
                    sock,server_hostname=host)
            host_header=host if port in {80,443} else host+":"+str(port)
            request=(f"GET {path} HTTP/1.1\r\nHost: {host_header}\r\n"
                     f"User-Agent: {_USER_AGENT}\r\nAccept: text/html, "
                     "application/json, text/plain\r\n"
                     "Accept-Encoding: identity\r\nConnection: close\r\n\r\n")
            sock.sendall(request.encode("ascii",errors="strict"))
            response=http.client.HTTPResponse(sock)
            response.begin()
            status=response.status
            if status in {301,302,303,307,308}:
                location=response.getheader("Location")
                if not location or redirects>=_MAX_REDIRECTS:
                    raise RuntimeError("browser_redirect_limit_or_missing_location")
                current=urljoin(normalized,location)
                _url(current,onion_mode=tor)
                redirects+=1
                continue
            ctype=response.getheader("Content-Type","").lower()
            if status!=200:
                return {"ok":False,"status":status,"url":normalized,
                        "reason":"remote_http_status",
                        "verified_page_content":False,"tor_mode":tor}
            if not any(ctype.startswith(t) for t in _ALLOWED_CONTENT):
                raise ValueError("browser_unsupported_document_type")
            length=response.getheader("Content-Length","")
            if length.isdigit() and int(length)>_MAX_BODY:
                raise ValueError("browser_document_too_large")
            raw=response.read(_MAX_BODY+1)
            if len(raw)>_MAX_BODY:raise ValueError("browser_document_too_large")
            title,content,links=_parse_body(ctype,raw,normalized)
            return {"ok":True,"url":normalized,"http_status":status,
                    "title":title,"text":content,"links":links,
                    "content_sha256":hashlib.sha256(raw).hexdigest(),
                    "observed_bytes":len(raw),
                    "elapsed_ms":round((time.monotonic()-started)*1000,2),
                    "tor_mode":tor,
                    "page_js_executed":False,"media_downloaded":False,
                    "provenance_url":normalized,
                    "response_is_untrusted_data":True}
        finally:
            try:sock.close()
            except OSError:pass
