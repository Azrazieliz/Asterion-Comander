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
    spec('remote_pc_window','Observe the actual Windows foreground app title and PID'),
    spec('remote_pc_input', 'Send a mouse, keyboard or text action to the PC',
         {'action': {'type': 'string', 'enum': ['click','double_click','right_click','move','drag','scroll','type','hotkey','press','mouse_down','mouse_up']},
          'x':INT,'y':INT,'to_x':INT,'to_y':INT,'text':STR,'keys':{'type':'array','items':STR},'amount':INT, 'monitor':INT}, ['action']),
    spec('control_phone_status','Read paired native Android agent status; requires no ADB'),
    spec('control_phone_health','Read native Android CPU, memory, battery and thermal indicators'),
    spec('control_phone_screen','Capture a single current native Android MediaProjection frame'),
    spec('control_phone_ui','Read native Android accessibility UI hierarchy'),
    spec('control_phone_input','Send action to the authorized Android agent without ADB',
         {'action': {'type':'string','enum':['tap','swipe','long_press','back','home','recents','notifications','type','click_text']},
          'x':INT,'y':INT,'x2':INT,'y2':INT,'duration_ms':INT,'text':STR},['action']),
    spec('control_phone_voice_status','Read permissioned Android foreground voice dialogue state and transcript'),
    spec('control_phone_voice_question','Speak a bounded question on Samsung, then listen once using on-device recognition',
         {'text':STR,'locale':STR},['text']),
    spec('control_phone_observation_status','Read user-selected Asterion game observation state on Samsung'),
    spec('control_phone_observation_events','Read timestamped event metadata from the user-selected Asterion app'),
    spec('control_phone_observation_frame','Read the latest recorded native Android gameplay frame'),
    spec('control_phone_continuation_status','Inspect the Android-owned checkpoint lifecycle (requires device opt-in)'),
    spec('control_phone_continuation_queue','Queue one spec-referenced ChatGPT app continuation on the phone; requires owner opt-in',
         {'project':STR,'checkpoint_id':STR,'priority_tier':{'type':'string','enum':['5*','6*','7*']},
          'spec_reference':STR,'message':STR},['project','checkpoint_id','priority_tier','spec_reference','message']),
    spec('control_phone_continuation_dispatch','Attempt guarded queued checkpoint submission in foreground ChatGPT'),
    spec('control_session_start','Start a bounded persistent Control-side interaction session (no ChatGPT turn per gesture)',
        {'device':{'type':'string','enum':['phone','pc']},
         'steps':{'type':'array','minItems':1,'maxItems':80,'items':{
             'type':'object','properties':{
                 'kind':{'type':'string','enum':['input','wait','assert_text','capture','health','window','assert_window']},
                 'payload':{'type':'object'},'wait_ms':INT,'text':STR},
             'required':['kind']}},
         'timeout_s':INT,'stop_on_error':{'type':'boolean'}},['device','steps']),
    spec('control_session_status','Read progress, observations, and step timing for a running Control session',
         {'id':STR},['id']),
    spec('control_session_cancel','Interrupt a running Control session at its next safe step boundary',
         {'id':STR},['id']),
    spec('control_phone_send_file','Transfer an authorized PC file directly to Android Downloads over private Wi-Fi',
         {'pc_path':STR,'name':STR},['pc_path']),
    spec('control_phone_transfer_status','Check native Android Wi-Fi file transfer and its SHA-256 receipt',
         {'id':STR},['id']),
    spec('control_phone_transfer_cancel','Cancel ongoing private Wi-Fi file transfer',
         {'id':STR},['id']),
    spec('control_scripts','List externally authored deterministic saved scripts'),
    spec('control_script_run','Run a saved script through the existing bounded PC executor',
         {'script_id':STR,'arguments':{'type':'array','items':STR},'cwd':STR},['script_id']),
    spec('control_script_parallel','Launch up to four saved scripts in parallel',
         {'jobs':{'type':'array','items':{'type':'object','properties':{'script_id':STR,'arguments':{'type':'array','items':STR},'cwd':STR},'required':['script_id']}},'mode':STR},['jobs']),

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
    if name == 'remote_pc_window':
        from .desktop_observe import foreground
        return foreground()
    if name == 'remote_pc_input': return remote.desktop_input(remote.DesktopInput(**args))
    if name == 'control_phone_status':
        from .native_routes import phone_status
        return phone_status()
    if name == 'control_phone_health':
        from .native_routes import phone_health
        return phone_health()
    if name == 'control_phone_screen':
        from .native_routes import phone_screen
        return phone_screen()
    if name == 'control_phone_ui':
        from .native_routes import phone_ui
        return phone_ui()
    if name == 'control_phone_input':
        from .native_routes import phone_input
        from .phone_bridge import PhoneInput
        return phone_input(PhoneInput(**args))
    if name == 'control_phone_voice_status':
        from .native_routes import phone_voice_status
        return phone_voice_status()
    if name == 'control_phone_voice_question':
        from .native_routes import phone_voice_question, VoiceQuestion
        return phone_voice_question(VoiceQuestion(**args))
    if name == 'control_phone_observation_status':
        from .native_routes import phone_observation_status
        return phone_observation_status()
    if name == 'control_phone_observation_events':
        from .native_routes import phone_observation_events
        return phone_observation_events()
    if name == 'control_phone_observation_frame':
        from .native_routes import phone_observation_frame
        return phone_observation_frame()
    if name == 'control_phone_continuation_status':
        from .native_routes import phone_continuation_status
        return phone_continuation_status()
    if name == 'control_phone_continuation_queue':
        from .native_routes import phone_continuation_queue, ContinuationRequest
        return phone_continuation_queue(ContinuationRequest(**args))
    if name == 'control_phone_continuation_dispatch':
        from .native_routes import phone_continuation_dispatch
        return phone_continuation_dispatch()
    if name == 'control_session_start':
        from .interaction_sessions import SessionRequest, start
        return start(SessionRequest(**args))
    if name == 'control_session_status':
        from .interaction_sessions import status
        return status(args['id'])
    if name == 'control_session_cancel':
        from .interaction_sessions import cancel
        return cancel(args['id'])
    if name == 'control_phone_send_file':
        from .native_transfer import TransferRequest, start_transfer
        return start_transfer(TransferRequest(**args),remote.safe_path)
    if name == 'control_phone_transfer_status':
        from .native_transfer import transfer_status
        return transfer_status(args['id'])
    if name == 'control_phone_transfer_cancel':
        from .native_transfer import cancel_transfer
        return cancel_transfer(args['id'])
    if name == 'control_scripts': return remote.internal_scripts()
    if name == 'control_script_run':
        from .control_services import ScriptRun
        return remote.run_saved_script(ScriptRun(**args))
    if name == 'control_script_parallel':
        from .control_services import BatchRequest
        return remote.run_saved_scripts(BatchRequest(**args))
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
                    'serverInfo':{'name':'asterion-control','version':'0.8.5'},
                    'instructions':'Asterion Control operates only authorized devices. Native Android requires explicit accessibility and screen capture approval.'}
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
