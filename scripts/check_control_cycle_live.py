"""Single-shot installed-phone cycle acceptance. No external Python modules."""
import json, os, sys, urllib.request, urllib.parse, ipaddress
from pathlib import Path

def main():
    directory=Path(os.getenv('ASTERION_CONTROL_STATE',str(Path.home()/'.asterion-control'))).expanduser()
    pairing=json.loads((directory/'phone-pairing.json').read_text(encoding='utf-8'))
    base=pairing['base_url'].rstrip('/')
    parsed=urllib.parse.urlparse(base)
    ip=ipaddress.ip_address(parsed.hostname or '')
    if parsed.scheme!='http' or not (ip.is_private or ip in ipaddress.ip_network('100.64.0.0/10')):
        raise ValueError('Private pairing endpoint required')
    token=pairing['token']
    req=urllib.request.Request(base+'/cycles/status',headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=8) as reply:
        data=json.load(reply); code=reply.status
    checkpoint=data.get('checkpoint',{})
    cycle=data.get('cycle',{})
    if not isinstance(cycle,dict): cycle={}
    if not isinstance(checkpoint,dict): checkpoint={'state':str(checkpoint)}
    print(json.dumps({
       'phone_api_http':code,
       'controller':data.get('controller'),
       'android_autonomous_cycle':data.get('android_autonomous_cycle',False),
       'cycle_active':cycle.get('active',False),
       'cycle_id':cycle.get('cycle_id',''),
       'project':cycle.get('project',''),
       'last_error':str(cycle.get('last_error',''))[:250],
       'cycle_state':cycle.get('state',''),
       'cycle_index':cycle.get('index',0),
       'checkpoint_state':checkpoint.get('state',checkpoint if isinstance(checkpoint,str) else '')
    },separators=(',',':')))
    if code!=200 or data.get('android_autonomous_cycle') is not True:
        print('ACCEPTANCE_FAIL: installed phone API is not v0.9.13 cycle-capable')
        return 2
    print('ACCEPTANCE_PASS: installed phone exposes native autonomous cycle endpoints')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('ACCEPTANCE_ERROR:'+type(e).__name__+':'+str(e)[:130])
        sys.exit(3)
