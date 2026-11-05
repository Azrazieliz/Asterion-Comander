"""Measure authenticated Asterion Control MCP call latency (native route, not GitHub polling).

No tokens, screen data, or host credentials are printed or committed.
Tests are READ-ONLY. The user has separately authorized harmless input acceptance.
"""
from __future__ import annotations
import json,os,statistics,time,urllib.request,urllib.error
from pathlib import Path

state=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl'
key=(state/'mcp-gateway-token.txt').read_text(encoding='utf8').strip()
urlfile=state/'mcp-tunnel-url.txt'
url=urlfile.read_text(encoding='utf8').strip().rstrip('/')+'/mcp' if urlfile.exists() else None
internal='http://127.0.0.1:8995/mcp'
body=json.dumps({'jsonrpc':'2.0','id':62,'method':'tools/call',
  'params':{'name':'control_phone_status','arguments':{}}}).encode()
def probe(endpoint,iterations=12):
    lat=[];errors=[];statuses=[]
    for i in range(iterations):
        req=urllib.request.Request(endpoint,data=body,method='POST',
          headers={'Authorization':'Bearer '+key,'Accept':'application/json, text/event-stream',
                   'Content-Type':'application/json'})
        t0=time.perf_counter()
        try:
            with urllib.request.urlopen(req,timeout=15) as rsp:
                data=json.loads(rsp.read(200000))
                ms=(time.perf_counter()-t0)*1000
                value=data.get('result',{})
                if 'isError' in value and value['isError']:raise RuntimeError('Control MCP tool error')
                lat.append(round(ms,1));statuses.append(rsp.status)
        except Exception as e:
            errors.append(type(e).__name__+': '+str(e)[:80])
    if lat:
        ordered=sorted(lat)
        print(json.dumps({'route':endpoint.split('/mcp')[0].split('://')[0]+' ('+
              ('loopback' if '127.0.0.1' in endpoint else 'public-HTTPS')+')',
              'runs':iterations,'succeeded':len(lat),'failed':len(errors),
              'median_ms':round(statistics.median(lat),1),
              'p95_ms':ordered[min(len(ordered)-1,int((len(ordered)-1)*.95))],
              'min_ms':ordered[0],'max_ms':ordered[-1],
              'samples_ms':lat,'first_error':errors[0] if errors else None}))
    else:
        print(json.dumps({'route':'loopback' if '127.0.0.1' in endpoint else 'public-HTTPS',
             'runs':iterations,'succeeded':0,'failed':len(errors),
             'first_error':errors[0] if errors else 'unavailable'}))
probe(internal)
if url:probe(url)
else:print('Public HTTPS tunnel URL file missing')
