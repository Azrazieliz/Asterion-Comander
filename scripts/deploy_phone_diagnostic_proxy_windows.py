"""Add scoped partner diagnostic proxy routes to the established deployed worker.

The installed Windows worker has local source differences from the staging
branch. This script APPENDS only verified new API endpoints and allowlist paths,
preserves all existing content, backs up exact bytes, and never re-pairs.
Default dry-run; --apply requires a clean Python parse.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path

EXTRA_PATHS=("/app-bridge/apps","/app-bridge/invoke","/app-bridge/operation",
             "/diagnostics/events","/diagnostics/exit-history",
             "/diagnostics/security","/diagnostics/permissions")

ROUTES = '''

# Owner-approved diagnostic extensions; original /api/v1 endpoints preserved.
class OwnerPartnerActionV2(BaseModel):
    package: str = Field(min_length=3,max_length=180)
    action: str = Field(min_length=1,max_length=80)
    request_id: str = Field(min_length=8,max_length=100)
    payload: dict = Field(default_factory=dict)

class OwnerPartnerOperationV2(BaseModel):
    package: str = Field(min_length=3,max_length=180)
    request_id: str = Field(min_length=8,max_length=100)
    cancel: bool = False

@router.get('/phone/app-bridge/apps')
def read_approved_partner_bridges_v2():
    return request('/app-bridge/apps').json()

@router.post('/phone/app-bridge/invoke')
def invoke_approved_partner_bridge_v2(data:OwnerPartnerActionV2):
    return request('/app-bridge/invoke','POST',data.model_dump(),timeout=11).json()

@router.post('/phone/app-bridge/operation')
def read_partner_operation_v2(data:OwnerPartnerOperationV2):
    return request('/app-bridge/operation','POST',data.model_dump(),timeout=11).json()

@router.get('/phone/diagnostics/events')
def read_control_phone_events_v2(since:int=0,limit:int=100):
    if not 0<=since<2**62 or not 1<=limit<=200:
        raise HTTPException(422,'Invalid event query')
    return request('/diagnostics/events','POST',{'since':since,'limit':limit},timeout=6).json()

@router.get('/phone/diagnostics/exit-history')
def read_control_phone_exits_v2():
    return request('/diagnostics/exit-history',timeout=6).json()

@router.get('/phone/diagnostics/security')
def read_control_phone_security_v2():
    return request('/diagnostics/security',timeout=6).json()

@router.get('/phone/diagnostics/permissions')
def read_control_phone_permissions_v2():
    return request('/diagnostics/permissions',timeout=6).json()
'''

def digest(data):return hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    arg=parser.parse_args()
    if os.name!="nt":raise RuntimeError("Windows environment required")
    root=Path(os.environ.get("ASTERION_DEPLOYED_CONTROL","D:/AsterionControlRelease"))
    src=root/"asterion_remote"
    routes=src/"native_routes.py"
    phone=src/"phone_bridge.py"
    old1=routes.read_bytes(); old2=phone.read_bytes()
    text1=old1.decode("utf8").replace("\r\n","\n")
    text2=old2.decode("utf8").replace("\r\n","\n")
    if "OwnerPartnerActionV2" in text1:
        new1=text1
    else:
        if "@router.get('/phone/app-bridge/apps')" in text1 or \
           "class OwnerPartnerActionV2" in text1 or \
           "router = APIRouter" not in text1 or \
           "from pydantic import BaseModel, Field" not in text1 or \
           "from fastapi import APIRouter" not in text1:
            raise RuntimeError("Unexpected production route structure; refusing merge")
        new1=text1.rstrip()+ROUTES+"\n"
    if "if path not in {" not in text2 or "def request(" not in text2:
        raise RuntimeError("Unexpected paired phone client structure")
    first="if path not in {"
    missing=[path for path in EXTRA_PATHS if "'"+path+"'" not in text2]
    prefix=",".join(repr(x) for x in missing)
    new2=text2.replace(first,first+prefix+("," if missing else ""),1)
    ast.parse(new1);ast.parse(new2)
    if "\r\n" in old1.decode("utf8"):new1=new1.replace("\n","\r\n")
    if "\r\n" in old2.decode("utf8"):new2=new2.replace("\n","\r\n")
    result={"mode":"apply" if arg.apply else "dry_run",
            "router_changed":old1!=new1.encode("utf8"),
            "phone_client_changed":old2!=new2.encode("utf8"),
            "routes_sha256":digest(new1.encode("utf8")),
            "client_sha256":digest(new2.encode("utf8")),
            "permissions_changed":False,"pairing_preserved":True,
            "service_restarted":False}
    if not arg.apply:
        print(json.dumps(result));return
    backup=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/"deployment-backups"
    backup.mkdir(parents=True,exist_ok=True)
    written=[]
    try:
        for dest,old,contents in ((routes,old1,new1.encode("utf8")),
                                  (phone,old2,new2.encode("utf8"))):
            if old==contents:continue
            target=backup/(dest.name+"-"+digest(old)+".backup")
            if not target.exists():
                with target.open("xb") as output:
                    output.write(old);output.flush();os.fsync(output.fileno())
            elif target.read_bytes()!=old:
                raise RuntimeError("Backup integrity mismatch")
            temp=dest.with_name(dest.name+".scoped-new")
            temp.write_bytes(contents);temp.replace(dest)
            written.append((dest,old))
            if dest.read_bytes()!=contents:raise RuntimeError("Write integrity mismatch")
    except BaseException:
        for dest,old in reversed(written):dest.write_bytes(old)
        raise
    result["installed_files"]=[str(x.relative_to(root)) for x,_ in written]
    result["backup_verified"]=True
    print(json.dumps(result))

if __name__=="__main__":main()
