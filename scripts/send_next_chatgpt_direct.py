"""Direct one-turn Android ChatGPT UI operator. Never queues a checkpoint.
The caller writes the NEXT real user message and invokes this once per turn.
"""
import argparse,json,os,sys,time,urllib.request,urllib.parse,urllib.error,ipaddress
from pathlib import Path
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--probe',action='store_true')
    ap.add_argument('--message',default='')
    args=ap.parse_args()
    paired=json.loads((Path(os.getenv('ASTERION_CONTROL_STATE',str(Path.home()/'.asterion-control')))/'phone-pairing.json').read_text('utf-8'))
    base=paired['base_url'].rstrip('/');u=urllib.parse.urlparse(base)
    ip=ipaddress.ip_address(u.hostname or '')
    if u.scheme!='http' or not (ip.is_private or ip in ipaddress.ip_network('100.64.0.0/10')):
        raise ValueError('Private paired phone required')
    message='' if args.probe else args.message
    if not args.probe and (not message or len(message)>3000):
        raise ValueError('Direct next-turn message required, at most 3000 characters')
    def direct():
        payload=json.dumps({'message':message}).encode('utf-8')
        req=urllib.request.Request(base+'/chat/direct',data=payload,method='POST',
          headers={'Authorization':'Bearer '+paired['token'],'Content-Type':'application/json',
                   'Accept':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=18) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:
            return error.code,json.loads(error.read(1000).decode('utf-8','replace'))
    if args.probe:
        status,data=direct()
        print('DIRECT_CAPABILITY',json.dumps({'http':status,'installed':
           status==400 and 'Direct ChatGPT message must' in str(data)},separators=(',',':')))
        return 0 if status==400 and 'Direct ChatGPT message must' in str(data) else 3
    for attempt in range(1,10):
        status,data=direct()
        stage=data.get('stage','')
        if status!=200:
            print('DIRECT_FAILED',json.dumps({'http':status,'error':str(data)[:150]}))
            return 4
        if data.get('sent'):
            print('DIRECT_SUBMITTED',json.dumps({'attempt':attempt,'stage':stage,
               'reason':data.get('reason',''),'reply_verified':False},separators=(',',':')))
            return 0
        if stage not in ('foreground_requested','writing_bar_focus_requested'):
            print('DIRECT_NOT_SENT',json.dumps({'attempt':attempt,'stage':stage,
              'reason':data.get('reason',''),'uncertain':data.get('uncertain',False)},separators=(',',':')))
            return 5
        time.sleep(.7)
    print('DIRECT_NOT_SENT: foreground or keyboard never became ready')
    return 6
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('DIRECT_ERROR',type(e).__name__,str(e)[:180]);sys.exit(7)
