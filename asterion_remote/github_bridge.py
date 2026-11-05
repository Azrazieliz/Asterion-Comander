"""Asterion Control — private GitHub command relay. No ADB, no Desktop Commander.
The only executor is the already authenticated Asterion Control Windows API.
Only operate the private repo explicitly owned by the user; no public endpoints.
"""
import base64, json, os, re, subprocess, time, urllib.request, urllib.error, urllib.parse
from pathlib import Path

REPO=os.environ.get('ASTERION_BRIDGE_REPO','Azrazieliz/Asterion-Control-Bridge')
GH='https://api.github.com/repos/'+REPO
PC=os.environ.get('ASTERION_CONTROL_HOST','http://192.168.1.133:8911').rstrip('/')
NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$')
ALLOWED={
 'pc_status':('GET','/api/v1/health'),
 'pc_health':('GET','/api/v1/device-health'),
 'pc_screen':('GET','/api/v1/screen'),
 'pc_monitors':('GET','/api/v1/monitors'),
 'pc_input':('POST','/api/v1/input'),
 'pc_command':('POST','/api/v1/commands'),
 'pc_jobs':('GET','/api/v1/commands'),
 'pc_scripts':('GET','/api/v1/internal/scripts'),
 'pc_script_run':('POST','/api/v1/internal/scripts/run'),
 'pc_script_parallel':('POST','/api/v1/internal/scripts/batch'),
 'phone_status':('GET','/api/v1/phone'),
 'phone_health':('GET','/api/v1/phone/health'),
 'phone_screen':('GET','/api/v1/phone/screen'),
 'phone_ui':('GET','/api/v1/phone/ui'),
 'phone_input':('POST','/api/v1/phone/input'),
 'phone_continuation_status':('GET','/api/v1/phone/continuation/status'),
 'phone_continuation_queue':('POST','/api/v1/phone/continuation/queue'),
 'phone_continuation_dispatch':('POST','/api/v1/phone/continuation/dispatch'),
 'phone_observation_status':('GET','/api/v1/phone/observation/status'),
 'phone_observation_events':('GET','/api/v1/phone/observation/events'),
 'phone_observation_frame':('GET','/api/v1/phone/observation/frame'),
 'phone_voice_status':('GET','/api/v1/phone/voice/status'),
 'phone_voice_question':('POST','/api/v1/phone/voice/question'),
}

def git_token():
    r=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',
                     text=True,capture_output=True,check=True,timeout=15)
    creds=dict(row.split('=',1) for row in r.stdout.splitlines() if '=' in row)
    value=creds.get('password','')
    if len(value)<20: raise ValueError('Windows Git credentials unavailable')
    return value

def local_token():
    home=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))
    for path in [home/'AsterionControl'/'control-token.txt',home/'AsterionRemote'/'token.txt']:
        if path.exists():
            key=path.read_text().strip()
            if len(key)>30: return key
    raise ValueError('Asterion Control Windows credentials unavailable')

def http(url,token,method='GET',body=None,control=False,binary=False):
    hdr={'Authorization':'Bearer '+token,'User-Agent':'Asterion-Control-Private-Bridge/0.1',
         'Accept':'application/json' if control else 'application/vnd.github+json'}
    data=None
    if body is not None:
        data=json.dumps(body,ensure_ascii=False).encode('utf-8')
        hdr['Content-Type']='application/json'
    req=urllib.request.Request(url,data=data,headers=hdr,method=method)
    with urllib.request.urlopen(req,timeout=20) as rsp:
        out=rsp.read(400000)
        if len(out)>=400000: raise ValueError('Response too large')
        if binary: return {'mime':rsp.headers.get('Content-Type','image/jpeg'),'bytes':len(out),
                           'jpeg_b64':base64.b64encode(out).decode('ascii')}
        return json.loads(out)

def gh(path,key,method='GET',body=None):
    return http(GH+path,key,method,body)

def pc(path,key,method='GET',body=None,binary=False):
    if not path.startswith('/api/v1/') or '..' in path: raise ValueError('Invalid Control path')
    return http(PC+path,key,method,body,control=True,binary=binary)

def run(request,key):
    op=request['op']
    args=request.get('params',{})
    if not isinstance(args,dict): raise ValueError('Invalid arguments')
    if op=='pc_job_status':
        ident=args.get('job_id','')
        if not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError('Invalid job ID')
        return pc('/api/v1/commands/'+ident,key)
    if op not in ALLOWED:raise ValueError('Unsupported operation')
    method,path=ALLOWED[op]
    if method=='GET' and args:raise ValueError('GET takes no body')
    if op=='pc_command' and (not isinstance(args.get('command'),str) or len(args['command'])>8192):
        raise ValueError('Invalid command')
    if op=='pc_input' and args.get('action') not in ('click','double_click','right_click','move','drag',
                                                     'scroll','type','hotkey','press','mouse_down','mouse_up'):
        raise ValueError('Invalid PC action')
    if op=='phone_input' and args.get('action') not in ('tap','swipe','long_press','back','home','recents',
                                                        'notifications','type','click_text'):
        raise ValueError('Invalid Android action')
    return pc(path,key,method,args if method=='POST' else None,
              binary=op in ('pc_screen','phone_screen','phone_observation_frame'))

def content_get(folder,name,key):
    item=gh('/contents/'+folder+'/'+urllib.parse.quote(name)+'?ref=main',key)
    raw=base64.b64decode(item['content'])
    if len(raw)>24000:raise ValueError('Command too large')
    return json.loads(raw)

def content_put(folder,name,value,key,sha=None):
    body={'message':'Asterion Control '+folder+': '+name,
          'content':base64.b64encode(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).decode(),
          'branch':'main'}
    if sha:body['sha']=sha
    return gh('/contents/'+folder+'/'+name,key,'PUT',body)

def cycle(github,local):
    """Two directory reads per scan; no O(N) per-command GitHub requests.

    The previous implementation requested a separate result for *every* historical
    command on *every* poll, rapidly exhausted GitHub API quotas, and starved
    new Control requests. Existing result files remain the durable execution log.
    """
    try:
        items=gh('/contents/commands?ref=main',github)
    except urllib.error.HTTPError as exc:
        if exc.code==404:return 0
        raise
    try:
        prior=gh('/contents/results?ref=main',github)
    except urllib.error.HTTPError as exc:
        if exc.code==404:prior=[]
        else:raise
    completed_names={entry.get('name') for entry in prior if isinstance(entry,dict)}
    completed=0
    for item in items:
        filename=item.get('name','')
        ident=filename[:-5] if filename.endswith('.json') else ''
        if not NAME.fullmatch(ident) or filename in completed_names:
            continue
        content_put('results',filename,{'id':ident,'ok':False,'status':'running'},github)
        completed_names.add(filename)
        start=time.monotonic()
        try:
            request=content_get('commands',filename,github)
            if request.get('id')!=ident or not isinstance(request.get('op'),str):
                raise ValueError('Request identity mismatch')
            result=run(request,local)
            final={'id':ident,'ok':True,'status':'complete',
                   'elapsed_ms':int((time.monotonic()-start)*1000),'result':result}
        except Exception as exc:
            final={'id':ident,'ok':False,'status':'error',
                   'elapsed_ms':int((time.monotonic()-start)*1000),
                   'error':str(exc)[:500]}
        old=gh('/contents/results/'+filename+'?ref=main',github)
        content_put('results',filename,final,github,old['sha'])
        print('Completed',ident,final['status'],flush=True)
        completed+=1
    return completed

def main():
    github=git_token()
    meta=gh('',github)
    if meta.get('full_name','').lower()!=REPO.lower() or not meta.get('private',False):
        raise ValueError('Bridge repository MUST be private and owner-authorized')
    key=local_token()
    print('Asterion Control private GitHub bridge ready:',REPO,flush=True)
    errors=0
    while True:
        try:
            cycle(github,key)
            errors=0
            time.sleep(5)
        except KeyboardInterrupt:return
        except Exception as exc:
            errors+=1
            print('Bridge temporarily unavailable:',type(exc).__name__,str(exc)[:100],flush=True)
            time.sleep(min(60,5*(errors+1)))

if __name__=='__main__':main()
