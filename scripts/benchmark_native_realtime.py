"""Measure real native Asterion Control LAN streaming and input (without GitHub).

This is a bounded acceptance test, called via an authorized Control command.
GitHub may start the script but DOES NOT carry any test frame or input action.
Secrets never appear in logs. Android remains the primary controller.
"""
from __future__ import annotations
import json, os, statistics, sys, time
from pathlib import Path
from websockets.sync.client import connect

DEFAULT_HOST=os.getenv('ASTERION_CONTROL_HOST','http://192.168.1.133:8911').rstrip('/')

def percentile(xs,n):
    seq=sorted(xs)
    return round(seq[min(len(seq)-1,round((len(seq)-1)*n/100))],1) if seq else None

def probe(source,inputs,frames=48,fps=12):
    state=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local'))) / 'AsterionControl' / 'control-token.txt'
    secret=state.read_text('utf8').strip()
    assert len(secret)>=32,'No authorized Control token'
    url=DEFAULT_HOST.replace('http://','ws://').replace('https://','wss://')+'/api/v1/stream/'+source
    frame_times=[]
    ack_times=[]
    ack_device_ms=[]
    ack_results=[]
    frame_sizes=[]
    pending={}
    with connect(url,open_timeout=8,close_timeout=3,max_size=4_200_000) as socket:
        socket.send(json.dumps({'token':secret,'fps':fps,'monitor':1}))
        started=time.perf_counter()
        done_inputs=set()
        while len(frame_times)<frames or pending:
            if time.perf_counter()-started>18:break
            value=socket.recv(timeout=8)
            now=time.perf_counter()
            if isinstance(value,bytes):
                frame_times.append(now)
                frame_sizes.append(len(value))
                for at,payload in inputs:
                    if at<=len(frame_times) and at not in done_inputs:
                        name=f"{source}-{at}"
                        pending[name]=(time.perf_counter(),payload.get('action'))
                        socket.send(json.dumps({'type':'input','id':name,'payload':payload}))
                        done_inputs.add(at)
            else:
                event=json.loads(value)
                if event.get('type')=='input_ack':
                    key=event.get('id')
                    start_action,kind=pending.pop(key,(None,None))
                    if start_action is not None:
                        ack_times.append((time.perf_counter()-start_action)*1000)
                        ack_device_ms.append(event.get('device_ms'))
                        ack_results.append({'action':kind,'ok':event.get('ok'), 
                                            'error':event.get('error')})
                elif event.get('type')=='error':
                    raise RuntimeError('Control stream error: '+str(event.get('error')))
    elapsed=frame_times[-1]-frame_times[0] if len(frame_times)>1 else None
    intervals=[(b-a)*1000 for a,b in zip(frame_times,frame_times[1:])]
    return {'source':source,
            'frames':len(frame_times),
            'frame_bytes_mean':int(statistics.mean(frame_sizes)) if frame_sizes else 0,
            'measured_fps':round((len(frame_times)-1)/elapsed,2) if elapsed and elapsed>0 else None,
            'frame_interval_p50_ms':percentile(intervals,50),
            'frame_interval_p95_ms':percentile(intervals,95),
            'input_ack_p50_ms':percentile(ack_times,50),
            'input_ack_p95_ms':percentile(ack_times,95),
            'device_input_ms':ack_device_ms,
            'actions':ack_results,
            'all_input_confirmed':bool(ack_results) and all(x['ok'] for x in ack_results)}

def main():
    tests=[]
    try:
        # Only harmless user-authorized actions, no shell or application edits.
        tests.append(probe('phone',[(4,{'action':'home'}),
                                    (20,{'action':'swipe','x':850,'y':1150,'x2':280,
                                         'y2':1150,'duration_ms':350})],frames=48,fps=12))
    except Exception as exc:
        tests.append({'source':'phone','error':type(exc).__name__+': '+str(exc)[:170]})
    try:
        tests.append(probe('desktop',[(5,{'action':'move','monitor':1,'x':180,'y':180})],
                           frames=48,fps=12))
    except Exception as exc:
        tests.append({'source':'desktop','error':type(exc).__name__+': '+str(exc)[:170]})
    print('ASTERION_NATIVE_REALTIME_BENCHMARK='+json.dumps(tests,separators=(',',':')),flush=True)
    return 0 if all(t.get('all_input_confirmed') and t.get('frames',0)>=35 for t in tests) else 2

if __name__=='__main__':sys.exit(main())
