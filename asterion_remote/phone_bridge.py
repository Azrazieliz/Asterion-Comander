"""Explicitly paired Android LAN/VPN agent client, without an ADB dependency.
A bearer secret is never forwarded to the browser; only the Windows host may call the phone.
"""
from __future__ import annotations
import ipaddress
import re
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

_DEFAULT_STATE=(Path(os.getenv('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl' if os.name=='nt' else Path.home()/'.asterion-control')
STATE = Path(os.getenv('ASTERION_CONTROL_STATE', str(_DEFAULT_STATE))).expanduser() / 'phone-pairing.json'
_lock = threading.RLock()

class PairPhone(BaseModel):
    base_url: str = Field(max_length=180, min_length=12)
    token: str = Field(min_length=32, max_length=512)

class PhoneInput(BaseModel):
    action: str = Field(pattern='^(tap|swipe|long_press|back|home|recents|notifications|type|click_text)$')
    x: float | None = None
    y: float | None = None
    x2: float | None = None
    y2: float | None = None
    duration_ms: int | None = Field(default=None, ge=100, le=5000)
    text: str | None = Field(default=None, max_length=2000)

def validate_base(base: str) -> str:
    u = urlparse(base)
    if u.scheme != 'http' or u.username or u.password or u.path not in ('', '/') or u.query or u.fragment:
        raise HTTPException(422, 'Phone agent URL must be an HTTP IP address on the private LAN/VPN')
    try:
        ip = ipaddress.ip_address(u.hostname or '')
        port = u.port
    except (ValueError, TypeError):
        raise HTTPException(422, 'Use a private IPv4/IPv6 address and explicit port')
    cgnat = ip in ipaddress.ip_network('100.64.0.0/10')
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or not (ip.is_private or cgnat):
        raise HTTPException(422, 'Only private/VPN IP addresses allowed for direct pairing')
    if not port or not 1024 <= port <= 65535:
        raise HTTPException(422, 'Invalid agent port')
    return f'http://{u.hostname}:{port}'

def load() -> dict | None:
    with _lock:
        if not STATE.exists(): return None
        try:
            p = json.loads(STATE.read_text('utf-8'))
            p['base_url'] = validate_base(p['base_url'])
            return p if len(p.get('token','')) >= 32 else None
        except (ValueError, OSError, KeyError, HTTPException): return None

def request(path: str, method: str='GET', payload: dict | None=None, timeout: float=5.0) -> httpx.Response:
    if path not in {'/health', '/ui', '/input', '/screen', '/continuation/status', '/continuation/queue', '/continuation/dispatch', '/observation/status', '/observation/events', '/observation/frame', '/voice/status', '/voice/question', '/voice/ack', '/voice/enable', '/voice/stop', '/cycles/status', '/cycles/start', '/cycles/pause', '/cycles/resume', '/cycles/stop', '/cycles/confirm-new-chat', '/network/status', '/github-bridge/status', '/performance/status', '/performance/mode', '/performance/optimize', '/apps', '/apps/launch', '/continuation/ack', '/continuation/cancel', '/chat/new' } and not re.fullmatch(r'/observation/frame/frame-[0-9]{10,15}\.jpg',path):
        raise HTTPException(400, 'Unsupported phone API call')
    p=load()
    if not p: raise HTTPException(503, 'Phone agent not registered')
    try:
        with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            r=client.request(method,p['base_url']+path,json=payload,
                headers={'Authorization':'Bearer '+p['token']})
        if r.status_code in (401,403): raise HTTPException(502, 'Phone rejected pairing token')
        if r.status_code >= 400:
            raise HTTPException(503, f'Phone returned {r.status_code}: '+r.text[:300])
        return r
    except httpx.HTTPError as exc:
        raise HTTPException(503, f'Phone unreachable: {type(exc).__name__}') from exc

def register(p: PairPhone) -> dict:
    base = validate_base(p.base_url)
    with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as c:
        try:
            r=c.get(base+'/health',headers={'Authorization':'Bearer '+p.token})
            if r.status_code!=200: raise HTTPException(502, 'Phone agent rejected pairing')
            info=r.json()
        except httpx.HTTPError as exc:
            raise HTTPException(503, 'Phone agent not reachable at supplied private address') from exc
    STATE.parent.mkdir(parents=True, exist_ok=True)
    obj={'base_url':base,'token':p.token,'device':info.get('device','Android')}
    tmp=STATE.with_suffix('.tmp')
    with _lock:
        tmp.write_text(json.dumps(obj),'utf-8')
        if os.name != 'nt': os.chmod(tmp,0o600)
        tmp.replace(STATE)
    return {'ok':True,'device':obj['device'],'address':base,'capabilities':['health','screen','input','ui']}
