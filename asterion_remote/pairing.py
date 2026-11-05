"""Deterministic local discovery and one-time phone pairing. No ADB or Desktop Commander."""
from __future__ import annotations
import hashlib, hmac, ipaddress, json, os, platform, secrets, socket, threading, time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

PORT=8912
DISCOVER=b'ASTERION_CONTROL_DISCOVER_V1'
STATE=Path(os.getenv('ASTERION_CONTROL_STATE',str(Path.home()/'.asterion-control'))).expanduser()
PAIRED=STATE/'authorized-devices.json'
PIN_FILE=STATE/'pairing-code.txt'
_lock=threading.RLock()
_pin=None
_expires=0
_attempts:dict[str,list[float]]={}
_listener=None
router=APIRouter(prefix='/api/v1/pair',tags=['pairing'])

class Join(BaseModel):
    code:str=Field(min_length=8,max_length=8,pattern=r'^\d{8}$')
    name:str=Field(min_length=1,max_length=80)

def private_peer(ip:str)->bool:
    try:
        address=ipaddress.ip_address(ip)
        if address.is_multicast or address.is_unspecified or address.is_link_local or address==ipaddress.ip_address('255.255.255.255'):
            return False
        return address.is_private or address.is_loopback or address in ipaddress.ip_network('100.64.0.0/10')
    except ValueError:return False

def create_code(seconds:int=600)->str:
    global _pin,_expires
    with _lock:
        STATE.mkdir(parents=True,exist_ok=True)
        _pin=f'{secrets.randbelow(100_000_000):08d}'
        _expires=time.monotonic()+seconds
        PIN_FILE.write_text(_pin,encoding='utf8')
        if os.name!='nt':os.chmod(PIN_FILE,0o600)
        return _pin

def is_authorized(token:str)->bool:
    if not token:return False
    try:
        devices=json.loads(PAIRED.read_text('utf-8'))
        digest=hashlib.sha256(token.encode('utf8')).hexdigest()
        return any(hmac.compare_digest(item.get('hash',''),digest) for item in devices)
    except (OSError,ValueError,TypeError):return False

def authorized_devices()->list[dict]:
    with _lock:
        try:return [{k:v for k,v in d.items() if k!='hash'} for d in json.loads(PAIRED.read_text('utf-8'))]
        except (OSError,ValueError,TypeError):return []

def _exchange(code:str,name:str,peer:str)->dict:
    global _pin,_expires
    if not private_peer(peer):raise HTTPException(403,'Pairing requires private LAN/VPN')
    with _lock:
        now=time.monotonic()
        recent=[t for t in _attempts.get(peer,[]) if now-t<600]
        if len(recent)>=6:raise HTTPException(429,'Pairing attempts exceeded')
        recent.append(now);_attempts[peer]=recent
        if _pin is None or now>_expires or not hmac.compare_digest(_pin,code):
            raise HTTPException(401,'Invalid or expired pairing code')
        token=secrets.token_urlsafe(48)
        try:records=json.loads(PAIRED.read_text('utf-8'))
        except (OSError,ValueError):records=[]
        records.append({'device':name,'created':int(time.time()),'hash':hashlib.sha256(token.encode()).hexdigest()})
        STATE.mkdir(parents=True,exist_ok=True)
        tmp=PAIRED.with_suffix('.tmp')
        tmp.write_text(json.dumps(records,indent=2),'utf-8')
        if os.name!='nt':os.chmod(tmp,0o600)
        tmp.replace(PAIRED)
        _pin=None;_expires=0;PIN_FILE.unlink(missing_ok=True)
        return {'ok':True,'token':token,'host':platform.node(),'expires':None}

@router.post('')
async def pair(data:Join,req:Request):
    return _exchange(data.code,data.name,req.client.host if req.client else '')

def _broadcast_server(stop:threading.Event)->None:
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            sock.bind(('',PORT));sock.settimeout(1)
            while not stop.is_set():
                try:
                    packet,addr=sock.recvfrom(128)
                    if packet!=DISCOVER or not private_peer(addr[0]):continue
                    response=json.dumps({'service':'asterion-control','version':1,'name':platform.node(),'port':8911},separators=(',',':')).encode()
                    sock.sendto(response,addr)
                except socket.timeout:continue
                except OSError:break
    except OSError:return

def start_discovery():
    global _listener
    if _listener is not None:return
    stop=threading.Event()
    worker=threading.Thread(target=_broadcast_server,args=(stop,),name='asterion-lan-discovery',daemon=True)
    worker.start();_listener=(stop,worker)

def stop_discovery():
    global _listener
    if _listener:_listener[0].set();_listener=None
