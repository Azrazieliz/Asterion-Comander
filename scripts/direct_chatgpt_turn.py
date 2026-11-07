"""One-shot owner-controlled ChatGPT continuation through actual phone UI.
Not a checkpoint queue or autonomous response synthesizer. No user message stored.
Usage: --prepare, then --send --message TEXT --send-x X --send-y Y.
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse, ipaddress
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--prepare',action='store_true')
    ap.add_argument('--send',action='store_true')
    ap.add_argument('--message',default='')
    ap.add_argument('--send-x',type=int,default=976)
    ap.add_argument('--send-y',type=int,default=1490)
    args=ap.parse_args()
    paired=json.loads((Path(os.getenv('ASTERION_CONTROL_STATE',str(Path.home()/'.asterion-control')))/'phone-pairing.json').read_text('utf-8'))
    base=paired['base_url'].rstrip('/')
    p=urllib.parse.urlparse(base);ip=ipaddress.ip_address(p.hostname or '')
    if p.scheme!='http' or not (ip.is_private or ip in ipaddress.ip_network('100.64.0.0/10')):
        raise ValueError('Paired private phone endpoint required')
    def call(path,payload=None):
        raw=None if payload is None else json.dumps(payload).encode('utf-8')
        headers={'Authorization':'Bearer '+paired['token'],'Accept':'application/json'}
        if raw is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(base+path,headers=headers,data=raw,method='POST' if raw is not None else 'GET')
        with urllib.request.urlopen(req,timeout=12) as response:return json.load(response)
    def ui():
        d=call('/ui')
        return d.get('foreground_package'),d.get('keyboard') or {},d.get('root') or {}
    foreground,keyboard,root=ui()
    if foreground!='com.openai.chatgpt':
        result=call('/apps/launch',{'package':'com.openai.chatgpt'})
        print('APP_LAUNCH',json.dumps(result,separators=(',',':')))
        for _ in range(15):
            time.sleep(.35)
            foreground,keyboard,root=ui()
            if foreground=='com.openai.chatgpt':break
    if foreground!='com.openai.chatgpt':
        raise RuntimeError('ChatGPT not foreground; no input performed')
    if not (keyboard.get('active') and keyboard.get('editor_package')=='com.openai.chatgpt'):
        # Tap the actual writing-bar area, never the trailing Send arrow.
        health=call('/health')
        w=int(health.get('screen_width',1080));h=int(health.get('screen_height',2340))
        call('/input',{'action':'tap','x':round(w*.39),'y':round(h*.935)})
        for _ in range(12):
            time.sleep(.25)
            foreground,keyboard,root=ui()
            if keyboard.get('active') and keyboard.get('editor_package')=='com.openai.chatgpt':break
    if not (foreground=='com.openai.chatgpt' and keyboard.get('active') and keyboard.get('editor_package')=='com.openai.chatgpt'):
        raise RuntimeError('Writing bar not focused and keyboard not visible')
    if keyboard.get('draft_empty') is not True:
        raise RuntimeError('Existing draft preserved: empty writing bar not verified')
    if args.prepare:
        print('DIRECT_PREPARE_OK',json.dumps({'foreground':foreground,'keyboard':keyboard,
            'root_bounds':root.get('bounds')},separators=(',',':')))
        return 0
    if not args.send or not args.message or len(args.message)>3800:
        raise ValueError('Explicit direct send and 1-3800 character message required')
    result=call('/input',{'action':'type','text':args.message})
    if not result.get('ok'):
        raise RuntimeError('Keyboard did not verify the typed message; no Send tap')
    _,after,_=ui()
    if after.get('draft_empty') is True:
        raise RuntimeError('Typed text not retained; no Send tap')
    tapped=call('/input',{'action':'tap','x':args.send_x,'y':args.send_y})
    if not tapped.get('ok'):
        raise RuntimeError('Blue Send tap not dispatched')
    time.sleep(1.0)
    now,final,_=ui()
    print('DIRECT_SEND_RESULT',json.dumps({'tap_completed':True,'foreground':now,
        'keyboard':final,'draft_cleared':final.get('draft_empty') is True},separators=(',',':')))
    if final.get('draft_empty') is not True:
        raise RuntimeError('Send not proven: writing bar did not clear; do not retry blindly')
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print('DIRECT_INPUT_ERROR',type(exc).__name__,str(exc)[:240]);sys.exit(2)
