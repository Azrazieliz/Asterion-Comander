"""Dependency-free MCP-compatible JSON-RPC bridge (stdio and HTTP).

Tools are executed in-process against the same capabilities as REST, with
Bearer authentication required for HTTP. No vendor MCP subscription is needed.
"""
import base64
import json
import os
import sys
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from . import app as remote
from .security import require_token

PROTOCOL = '2025-11-25'


def spec(name, description, props=None, required=None):
    return {'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': props or {}, 'required': required or []}}

STR = {'type': 'string'}
INT = {'type': 'integer'}
TOOLS = [
    spec('remote_health', 'Inspect the Asterion Remote agent and its capabilities'),
    spec('remote_system', 'Read PC CPU, memory, disk and uptime metrics'),
    spec('remote_processes', 'List processes running on the connected PC'),
    spec('remote_list_files', 'Browse files inside the configured PC root', {'path': STR}),
    spec('remote_search_files', 'Search filenames inside the PC root', {'q': STR, 'path': STR}, ['q']),
    spec('remote_read_file', 'Read a UTF-8 file inside the allowed PC root', {'path': STR}, ['path']),
    spec('remote_write_file', 'Write a text file inside the allowed PC root',
         {'path': STR, 'content': STR, 'overwrite': {'type':'boolean'}}, ['path','content']),
    spec('remote_run_command', 'Execute a shell command on PC (only if shell enabled in agent)',
         {'command': STR, 'cwd': STR}, ['command']),
    spec('remote_command_status', 'Read output of a launched PC command', {'job_id': STR}, ['job_id']),
    spec('remote_stop_command', 'Terminate a launched PC job', {'job_id': STR}, ['job_id']),
    spec('remote_pc_screen', 'Capture the PC desktop screen as an image', {'monitor': INT}),
    spec('remote_pc_input', 'Send a mouse, keyboard or text action to the PC',
         {'action': {'type': 'string', 'enum': ['click','double_click','right_click','move','drag','scroll','type','hotkey','press','mouse_down','mouse_up']},
          'x':INT,'y':INT,'to_x':INT,'to_y':INT,'text':STR,'keys':{'type':'array','items':STR},'amount':INT, 'monitor':INT}, ['action']),
    spec('remote_android_devices', 'List Android phones authorized with PC ADB'),
    spec('remote_android_connect_wifi', 'Connect to an authorized Android wireless ADB device', {'address':STR},['address']),
    spec('remote_android_pair_wifi', 'Pair Android Wireless Debugging using its on-screen pairing code', {'address':STR,'code':STR},['address','code']),
    spec('remote_android_info', 'Get model, Android version, screen size and battery', {'serial': STR}, ['serial']),
    spec('remote_android_screen', 'Capture an authorized Android phone screen as PNG', {'serial': STR}, ['serial']),
    spec('remote_android_input', 'Tap, swipe, long press, type or send key to Android phone',
         {'serial': STR,'action':{'type':'string','enum':['tap','swipe','long_press','key','text']},
          'x':INT,'y':INT,'to_x':INT,'to_y':INT,'duration_ms':INT,'key':STR,'text':STR}, ['serial','action']),
    spec('remote_android_shell', 'Execute an ADB shell command on the authorized phone (only if enabled)',
         {'serial': STR,'command': STR}, ['serial','command']),
    spec('remote_android_packages', 'List installed Android application package names',
         {'serial': STR,'q': STR}, ['serial']),
    spec('remote_android_ui', 'Inspect an authorized Android phone accessibility hierarchy via UIAutomator',
         {'serial':STR}, ['serial']),
]


def plain(result):
    if isinstance(result, Response):
        if result.media_type and result.media_type.startswith('image/'):
            raw = result.body
            mime = result.media_type
            return {'content': [{'type':'image','data':base64.b64encode(raw).decode(),'mimeType':mime}]}
        return {'content':[{'type':'text','text':result.body.decode('utf-8','replace')}]}
    return {'content':[{'type':'text','text':json.dumps(result,ensure_ascii=False,default=str)}]}


def invoke_tool(name: str, args: dict):
    if name == 'remote_health': return remote.health()
    if name == 'remote_system': return remote.system()
    if name == 'remote_processes': return remote.processes(100)
    if name == 'remote_list_files': return remote.list_files(args.get('path', '.'))
    if name == 'remote_search_files': return remote.search_files(args['q'],args.get('path','.'),100)
    if name == 'remote_read_file': return remote.read_file(args['path'])
    if name == 'remote_write_file': return remote.write_file(remote.FileWrite(**args))
    if name == 'remote_run_command': return remote.launch_command(remote.CommandRequest(**args))
    if name == 'remote_command_status': return remote.command_status(args['job_id'])
    if name == 'remote_stop_command': return remote.stop_command(args['job_id'])
    if name == 'remote_pc_screen': return remote.screenshot(args.get('monitor',1),75)
    if name == 'remote_pc_input': return remote.desktop_input(remote.DesktopInput(**args))
    if name == 'remote_android_devices': return remote.android_devices()
    if name == 'remote_android_connect_wifi': return remote.connect_android(remote.WifiTarget(**args))
    if name == 'remote_android_pair_wifi': return remote.pair_android(remote.PairTarget(**args))
    if name == 'remote_android_info': return remote.android_info(args['serial'])
    if name == 'remote_android_screen': return remote.android_screen(args['serial'])
    if name == 'remote_android_input':
        data={k:v for k,v in args.items() if k!='serial'}
        return remote.android_input(args['serial'],remote.AndroidInput(**data))
    if name == 'remote_android_shell': return remote.android_shell(args['serial'],remote.AndroidShell(command=args['command']))
    if name == 'remote_android_packages': return remote.android_packages(args['serial'],args.get('q',''))
    if name == 'remote_android_ui': return remote.android_ui_hierarchy(args['serial'])
    raise KeyError(name)


def handle_rpc(message: dict[str,Any]) -> dict | None:
    reqid=message.get('id')
    if 'method' not in message:
        return None
    if reqid is None:
        return None
    method=message['method']
    response={'jsonrpc':'2.0','id':reqid}
    try:
        if method=='initialize':
            result={'protocolVersion':PROTOCOL,
                    'capabilities':{'tools':{'listChanged':False}},
                    'serverInfo':{'name':'asterion-control','version':'0.3.0'},
                    'instructions':'Asterion Remote controls only devices authorized by the operator.'}
        elif method=='ping':
            result={}
        elif method=='tools/list':
            result={'tools':TOOLS}
        elif method=='tools/call':
            p=message.get('params') or {}
            name=p.get('name','')
            if name not in {t['name'] for t in TOOLS}:
                result={'content':[{'type':'text','text':f'Unknown tool: {name}'}],'isError':True}
                response['result']=result
                return response
            arguments=p.get('arguments') or {}
            if not isinstance(arguments,dict):
                raise ValueError('Tool arguments must be an object')
            try:
                result=plain(invoke_tool(name,arguments))
            except (HTTPException, ValidationError, OSError, KeyError, ValueError) as exc:
                result={'content':[{'type':'text','text':str(getattr(exc,'detail',exc))}], 'isError':True}
        elif method in ('resources/list','prompts/list'):
            result={'resources':[]} if method.startswith('resources') else {'prompts':[]}
        else:
            response['error']={'code':-32601,'message':'Method not found'}
            return response
        response['result']=result
        return response
    except (ValueError,TypeError) as exc:
        response['error']={'code':-32602,'message':str(exc)}
        return response


@remote.app.post('/mcp', dependencies=[Depends(require_token)])
async def mcp_http(req: Request):
    origin=req.headers.get('origin')
    permitted={v.strip() for v in os.getenv('ASTERION_ALLOWED_ORIGINS','').split(',') if v.strip()}
    # Valid origins must be explicitly permitted, preventing DNS rebinding.
    if origin and origin not in permitted:
        raise HTTPException(403, 'Untrusted Origin')
    if 'application/json' not in req.headers.get('accept','') or 'text/event-stream' not in req.headers.get('accept',''):
        raise HTTPException(406, 'MCP requires Accept: application/json, text/event-stream')
    try:
        msg=await req.json()
        if not isinstance(msg,dict):
            raise ValueError('One JSON-RPC request object required')
    except (ValueError,TypeError):
        raise HTTPException(400, 'Invalid JSON-RPC request')
    answer=handle_rpc(msg)
    if answer is None:
        return Response(status_code=202)
    return JSONResponse(answer)


def main():
    remote.check_config()
    for line in sys.stdin:
        try:
            msg=json.loads(line)
            ans=handle_rpc(msg)
            if ans is not None:
                print(json.dumps(ans,separators=(',',':'),ensure_ascii=False),flush=True)
        except Exception as e:
            print(f'Asterion MCP error: {type(e).__name__}: {e}',file=sys.stderr,flush=True)


if __name__=='__main__':
    main()
