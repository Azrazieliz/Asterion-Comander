"""Bounded live phone acceptance for exact two-turn ChatGPT keyboard cycle and voice readiness."""
import json, os, sys, urllib.request, urllib.parse, ipaddress, urllib.error
from pathlib import Path

def main():
    state=Path(os.getenv('ASTERION_CONTROL_STATE',str(Path.home()/'.asterion-control'))).expanduser()
    pairing=json.loads((state/'phone-pairing.json').read_text(encoding='utf-8'))
    base=pairing['base_url'].rstrip('/')
    addr=urllib.parse.urlparse(base)
    ip=ipaddress.ip_address(addr.hostname or '')
    if addr.scheme!='http' or not (ip.is_private or ip in ipaddress.ip_network('100.64.0.0/10')):
        raise ValueError('Only paired private phone endpoints supported')
    token=pairing['token']
    def call(route,body=None):
        raw=None if body is None else json.dumps(body,separators=(',',':')).encode()
        head={'Authorization':'Bearer '+token,'Accept':'application/json'}
        if raw is not None:head['Content-Type']='application/json'
        req=urllib.request.Request(base+route,headers=head,data=raw,method='POST' if raw is not None else 'GET')
        try:
            with urllib.request.urlopen(req,timeout=9) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as e:
            print('PHONE_API_ERROR',e.code,route,e.read(600).decode('utf-8','replace'))
            raise
    test='control-live-keyboard-20261107'
    _,state=call('/cycles/status')
    cycle=state.get('cycle') or {}
    if '--start' in sys.argv:
        if cycle.get('active'):
            raise ValueError('Existing cycle active: will not overwrite '+str(cycle.get('cycle_id')))
        payload={'cycle_id':test,'project':'Asterion-Control','priority_tier':'7*',
            'spec_reference':'7STAR_FROZEN_MASTER.md','conversation':'same','max_cycles':2,
            'message':(
                'ASTERION CONTROL DIRECT KEYBOARD CYCLE TEST. '
                'Cycle 1: Reply only with a brief confirmation that this message was received, '
                'and put ASTERION-CYCLE-ACK:control-live-keyboard-20261107-1 on the last line. '
                'Asterion Control must autonomously write cycle 2 into the real ChatGPT writing bar '
                'through the keyboard that appears when tapped and use the visible blue Send button. '
                'Cycle 2: Reply briefly confirming that this is the SECOND separately submitted request, '
                'then end with ASTERION-CYCLE-DONE:control-live-keyboard-20261107-2 on the last line. '
                'No other work or repository changes are authorized in this acceptance test.'
            )}
        _,cycle=call('/cycles/start',payload)
        print('TEST_STARTED',test)
        _,state=call('/cycles/status')
    if '--stop' in sys.argv:
        if cycle.get('active') and cycle.get('cycle_id')==test:
            _,cycle=call('/cycles/stop',{})
            print('TEST_STOPPED',test)
        elif cycle.get('active'):
            raise ValueError('Refusing to stop unrelated cycle')
        _,state=call('/cycles/status')
    if '--tick' in sys.argv:
        _,cycle=call('/cycles/tick',{})
        _,state=call('/cycles/status')
    c=state.get('cycle') or {}
    output={'installed_cycle_api':state.get('android_autonomous_cycle'),
      'cycle_id':c.get('cycle_id'),'state':c.get('state'),'active':c.get('active'),
      'index':c.get('index'),'ack_count':c.get('ack_count'),
      'error':c.get('last_error'), 'checkpoint':state.get('checkpoint')}
    print('CYCLE',json.dumps(output,separators=(',',':')))
    if '--voice-test' in sys.argv:
        _,spoken=call('/voice/question',{'text':'Asterion Control voice test. Please answer out loud: ready.', 'locale':'en-US', 'question_id':'voice-check-20261107'})
        print('SPOKEN_TEST',json.dumps({k:spoken.get(k) for k in ('ok','question_id','phase')},separators=(',',':')))
    if '--voice-ack' in sys.argv:
        _,receipt=call('/voice/ack',{'question_id':'voice-check-20261107'})
        print('VOICE_ACK',json.dumps(receipt,separators=(',',':')))
    _,v=call('/voice/status')
    keys=('enabled','phase','microphone_active','on_device_recognition','android_system_recognition',
          'recognizer_backend','speaker_started','speaker_finished','voice','voice_quality',
          'exclusive_audio_focus','error')
    print('VOICE',json.dumps({k:v.get(k) for k in keys},separators=(',',':')))
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('PROBE_ERROR',type(e).__name__,str(e)[:220]);sys.exit(3)
