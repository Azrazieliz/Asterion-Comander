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
    def call(endpoint,payload=None):
        raw=None if payload is None else json.dumps(payload,separators=(',',':')).encode('utf-8')
        headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
        if raw is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(base+endpoint,data=raw,headers=headers,method='POST' if raw is not None else 'GET')
        with urllib.request.urlopen(req,timeout=9) as reply:
            return reply.status,json.load(reply)
    code,data=call('/cycles/status')
    if '--stop-test' in sys.argv:
        current=data.get('cycle',{})
        if not isinstance(current,dict) or current.get('cycle_id')!='control-accept-v0913-20261107':
            raise ValueError('Refusing to stop an unrelated cycle')
        code,data=call('/cycles/stop',{})
        print('ACCEPTANCE_TEST_STOPPED:control-accept-v0913-20261107')
        code,data=call('/cycles/status')
    if '--start-test' in sys.argv:
        previous=data.get('cycle',{})
        if not isinstance(previous,dict):previous={}
        if previous.get('active',False):
            if not previous.get('cycle_id','').startswith('phone-selftest-'):
                raise ValueError('Active non-test cycle; refusing replacement')
            call('/cycles/stop',{})
        test_id='control-accept-v0913-20261107'
        payload={
            'cycle_id':test_id,
            'project':'Asterion-Control',
            'priority_tier':'7*',
            'spec_reference':'7STAR_FROZEN_MASTER.md',
            'conversation':'same',
            'max_cycles':2,
            'message':'Two-turn autonomous continuation acceptance only. No repository edits or external tasks. For cycle 1, confirm the controller has delivered the first checkpoint and explain that it must automatically enqueue cycle 2; finish with the exact ASTERION-CYCLE-ACK marker specified below. For cycle 2, confirm that this is a distinct second controller-delivered turn; finish with the ASTERION-CYCLE-DONE marker. Do not complete after only one message.'
        }
        code,data=call('/cycles/start',payload)
        print('ACCEPTANCE_TEST_STARTED:'+test_id)
        code,data=call('/cycles/status')
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
       'cycle_ack_count':cycle.get('ack_count',0),
       'checkpoint_state':checkpoint.get('state',checkpoint if isinstance(checkpoint,str) else '')
    },separators=(',',':')))
    if code!=200 or data.get('android_autonomous_cycle') is not True:
        print('INSTALL_FAIL: phone does not expose autonomous cycle API')
        return 2
    print('INSTALL_PASS: native cycle API available')
    if '--require-cycle-pass' in sys.argv:
        complete=(cycle.get('cycle_id')=='control-accept-v0913-20261107'
                  and cycle.get('state')=='finished'
                  and cycle.get('active') is False
                  and cycle.get('ack_count',0)>=2)
        if not complete:
            print('CYCLE_FAIL: two acknowledged distinct turns and completion not verified')
            return 4
        print('CYCLE_PASS: two turns acknowledged and finished')
    else:
        print('CYCLE_NOT_VERIFIED: run --require-cycle-pass for strict acceptance')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('ACCEPTANCE_ERROR:'+type(e).__name__+':'+str(e)[:130])
        sys.exit(3)
