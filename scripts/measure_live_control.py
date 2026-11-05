"""Real Control-only WebSocket frame/input benchmark, no GitHub in data path.
Uses the already authorized Windows Asterion agent and its paired native Samsung.
Never logs tokens, frames, page contents or credentials.
"""
from __future__ import annotations
import asyncio,hashlib,json,os,statistics,time
from pathlib import Path
from websockets.asyncio.client import connect

state=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl'
token=(state/'control-token.txt').read_text(encoding='utf8').strip()
uri='ws://192.168.1.133:8911/api/v1/stream/phone'
async def main():
    t_connect=time.perf_counter()
    async with connect(uri,origin='http://192.168.1.133:8911',max_size=4_200_000,open_timeout=6,close_timeout=2) as ws:
        await ws.send(json.dumps({'token':token,'monitor':1,'fps':18}))
        start=time.perf_counter()
        frames=[];sizes=[];digests=set();ack_ms=None;device_ms=None;errors=[];sent=None;timeout=start+7.5
        while time.perf_counter()<timeout and len(frames)<35:
            try:
                msg=await asyncio.wait_for(ws.recv(),timeout=3)
            except (asyncio.TimeoutError,Exception) as exc:
                errors.append(type(exc).__name__);break
            now=time.perf_counter()
            if isinstance(msg,bytes):
                frames.append(now);sizes.append(len(msg));digests.add(hashlib.sha256(msg).digest())
                if len(frames)==5 and sent is None:
                    # Harmless navigation action already accepted in prior Control-only tests.
                    sent=time.perf_counter()
                    await ws.send(json.dumps({'type':'input','id':'native-websocket-1','payload':{'action':'home'}}))
            else:
                try:message=json.loads(msg)
                except ValueError:errors.append('Invalid JSON');continue
                if message.get('type')=='input_ack' and message.get('id')=='native-websocket-1':
                    ack_ms=round((now-sent)*1000,1) if sent else None
                    device_ms=message.get('device_ms')
                    if not message.get('ok'):errors.append('input_failed:'+str(message.get('error')))
                elif message.get('type')=='error':errors.append('stream:'+str(message.get('error')))
        duration=(frames[-1]-frames[0]) if len(frames)>1 else 0
        delta=[(b-a)*1000 for a,b in zip(frames,frames[1:])]
        print(json.dumps({
          'transport':'Asterion Control authenticated native phone full-duplex WebSocket, no GitHub',
          'connect_to_first_frame_ms':round((frames[0]-t_connect)*1000,1) if frames else None,
          'frames_received':len(frames),'unique_frame_payloads':len(digests),
          'measurement_s':round(duration,2),'received_fps':round((len(frames)-1)/duration,1) if duration else 0,
          'frame_interval_median_ms':round(statistics.median(delta),1) if delta else None,
          'frame_interval_p95_ms':round(sorted(delta)[int(.95*(len(delta)-1))],1) if delta else None,
          'mean_frame_kb':round(sum(sizes)/len(sizes)/1024,1) if sizes else None,
          'native_input_ack_roundtrip_ms':ack_ms,'device_input_ms':device_ms,'errors':errors
        },separators=(',',':')))
asyncio.run(main())
