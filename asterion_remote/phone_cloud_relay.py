"""Owner-authenticated HTTPS fallback for Android away from home.

When the paired Samsung is on cellular or another Wi-Fi network, the direct
LAN socket is unreachable. The phone already polls a private GitHub repository
over outbound HTTPS. This module sends bounded allowlisted commands through
that same queue and waits for durable results. No public phone port, PC-to-phone
tunnel, or Android USB connection is required.

The gateway hosting this module is optional; ChatGPT's GitHub connector may
also write to the same private queue when the PC is off.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid

import httpx
from fastapi import HTTPException

REPO="Azrazieliz/Asterion-Control-Bridge"
API="https://api.github.com/repos/"+REPO+"/contents/"
PREFIX="phone-"
MAX_PAYLOAD=20000
MAX_RESULT=1000000
MAX_WAIT_SECONDS=39
ALLOW={
    "status","bridge_status","health","network_status","ui","input",
    "screen","observation_frame","observation_get_frame",
    "apps","app_launch","chat_new","continuation_status",
    "continuation_queue","continuation_dispatch","continuation_ack",
    "continuation_cancel","cycle_status","cycle_start","cycle_pause",
    "cycle_resume","cycle_stop","cycle_confirm_new_chat",
    "observation_status","observation_events","observation_timeline",
    "voice_status","voice_question","voice_ack"
}

def route_for(name:str)->str:
    if not isinstance(name,str) or not name.startswith("control_phone_"):
        raise ValueError("Not a native phone tool")
    suffix=name[len("control_phone_"):]
    if suffix not in ALLOW:
        raise ValueError("This Android operation has no private cloud relay")
    return "phone_"+suffix

def get_token()->str:
    from .github_bridge import git_token
    token=git_token()
    if not isinstance(token,str) or len(token)<20:
        raise RuntimeError("Authorized private GitHub credentials unavailable")
    return token

def url(kind:str, identity:str)->str:
    if not identity.startswith(PREFIX) or len(identity)!=38 or not all(
        char in "0123456789abcdef" for char in identity[6:]
    ):
        raise ValueError("Invalid immutable cloud command ID")
    if kind not in ("commands","results"):
        raise ValueError("Invalid cloud queue")
    return API+kind+"/android/"+identity+".json"

def decode_file(response:httpx.Response)->dict|None:
    if response.status_code==404:return None
    if response.status_code!=200:
        raise RuntimeError("Private Control result is unavailable")
    if len(response.content)>MAX_RESULT*2:
        raise RuntimeError("Remote result exceeded cap")
    item=response.json()
    encoded=item.get("content","")
    if len(encoded)>MAX_RESULT*2:
        raise RuntimeError("Remote result exceeded cap")
    return json.loads(base64.b64decode(encoded))

def wrap_result(identifier,receipt):
    if not isinstance(receipt,dict):
        raise RuntimeError("Malformed private Control response")
    if receipt.get("id")!=identifier:
        raise RuntimeError("Private Control response ID does not match")
    status=receipt.get("status")
    if status=="complete" and receipt.get("ok") is False:
        status="failed"
    if status in ("uncertain","failed","error","expired","cancelled"):
        message=str(receipt.get("error","Native Android operation not completed"))[:250]
        return {"jsonrpc":"2.0","id":identifier,
                "error":{"code":-32009,"message":status+": "+message}}
    if status not in ("complete",):
        return {"jsonrpc":"2.0","id":identifier,
                "error":{"code":-32010,"message":"Android command still pending: "+identifier}}
    value=receipt.get("result",{})
    if isinstance(value,dict) and "jpeg_b64" in value:
        result={"content":[{"type":"image",
            "mimeType":value.get("mime","image/jpeg"),
            "data":value["jpeg_b64"]}]}
    else:
        result={"content":[{"type":"text","text":json.dumps(value,separators=(",",":"))}]}
    return {"jsonrpc":"2.0","id":identifier,"result":result}

async def submit(name:str, arguments:dict, response_id, *, timeout=MAX_WAIT_SECONDS)->dict:
    operation=route_for(name)
    if not isinstance(arguments,dict):
        raise ValueError("Android tool arguments must be an object")
    identifier=PREFIX+uuid.uuid4().hex
    now=int(time.time()*1000)
    instruction={"id":identifier,"op":operation,"params":arguments,
                 "created_at_ms":now,"expires_at_ms":now+65000}
    value=json.dumps(instruction,separators=(",",":")).encode("utf8")
    if len(value)>MAX_PAYLOAD:
        raise ValueError("Cloud operation exceeds bounded GitHub request size")
    token=await asyncio.to_thread(get_token)
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "User-Agent":"Asterion-Control-Private-Relay",
             "X-GitHub-Api-Version":"2022-11-28"}
    document={"message":"Asterion Control owner-authorized remote phone tool "+identifier,
              "content":base64.b64encode(value).decode("ascii"),"branch":"main"}
    async with httpx.AsyncClient(timeout=12.0,trust_env=False,follow_redirects=False) as client:
        sent=await client.put(url("commands",identifier),headers=headers,json=document)
        if sent.status_code not in (200,201):
            raise RuntimeError("GitHub rejected native phone command")
        until=time.monotonic()+min(max(timeout,1),MAX_WAIT_SECONDS)
        while time.monotonic()<until:
            response=await client.get(url("results",identifier),headers=headers)
            receipt=decode_file(response)
            if receipt is not None and receipt.get("status") not in ("running","accepted"):
                wrapped=wrap_result(identifier,receipt)
                wrapped["id"]=response_id
                return wrapped
            await asyncio.sleep(2.0)
    # Preserve an immutable cloud command ID in a typed result. This is
    # pending, NEVER claim that an Android action succeeded without a receipt.
    return {"jsonrpc":"2.0","id":response_id,
            "result":{"content":[{"type":"text",
                "text":json.dumps({"status":"pending","id":identifier,
                  "executed":False,"next_action":"control_phone_cloud_receipt"},
                  separators=(",",":"))}]}}

async def receipt(identity:str,response_id):
    if not identity.startswith(PREFIX):
        raise ValueError("Invalid cloud ID")
    token=await asyncio.to_thread(get_token)
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "User-Agent":"Asterion-Control-Private-Relay"}
    async with httpx.AsyncClient(timeout=10,trust_env=False,follow_redirects=False) as client:
        response=await client.get(url("results",identity),headers=headers)
    found=decode_file(response)
    if found is None:
        return {"jsonrpc":"2.0","id":response_id,
                "result":{"content":[{"type":"text","text":"Pending or not yet received"}]}}
    result=wrap_result(identity,found)
    result["id"]=response_id
    return result
