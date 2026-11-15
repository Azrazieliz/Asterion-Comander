"""Real-owner Windows Control diagnostic SSE acceptance, read-only plus synthetic markers.

Starts authenticated streams over the existing native Windows Control API,
adds bounded synthetic self-test events and confirms receipt/cursor resume.
Does not claim partner-app crashes or downloaded output were observed.
"""
from __future__ import annotations
import asyncio
import json
import os
import pathlib
import statistics
import time
import uuid
import httpx


async def roundtrip(client: httpx.AsyncClient, index:int):
    prefix="/api/v1/diagnostics"
    health=(await client.get(prefix+"/health"))
    health.raise_for_status()
    cursor=int(health.json()["latest_sequence"])
    trace_id="acceptance-"+uuid.uuid4().hex
    ready=asyncio.Event()
    received={}
    async def listener():
        start=time.perf_counter()
        async with client.stream("GET",prefix+"/stream",
                   params={"since":cursor,"trace_id":trace_id}) as rsp:
            rsp.raise_for_status()
            event_name=""
            async for line in rsp.aiter_lines():
                if line.startswith("event: "):
                    event_name=line[7:]
                elif line.startswith("data: ") and event_name=="ready":
                    ready.set()
                elif line.startswith("data: ") and event_name=="event":
                    obj=json.loads(line[6:])
                    if obj.get("trace_id")==trace_id:
                        received.update({"event_id":obj.get("event_id"),
                                         "sequence":obj.get("seq"),
                                         "received_ms":round((time.perf_counter()-start)*1000,1)})
                        return
    task=asyncio.create_task(listener())
    try:
        await asyncio.wait_for(ready.wait(),timeout=5)
        sent=time.perf_counter()
        response=await client.post(prefix+"/events",json={
            "kind":"acceptance_ping","component":"operator_acceptance",
            "trace_id":trace_id,"state":"observed",
            "attributes":{"stage":"synthetic_acceptance","event_source":"operator_test"}})
        response.raise_for_status()
        recorded=response.json()
        await asyncio.wait_for(task,timeout=8)
        return {"index":index,"ok":bool(received.get("event_id")==recorded["event_id"]),
                "event_delivery_from_post_ms":round((time.perf_counter()-sent)*1000,1),
                "cursor":received.get("sequence"),"persisted":recorded.get("sequence")==received.get("sequence")}
    finally:
        if not task.done():task.cancel()
        try:await task
        except asyncio.CancelledError:pass


async def main():
    state=pathlib.Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    url=(state/"agent-host.txt").read_text().strip()
    token=(state/"control-token.txt").read_text().strip()
    async with httpx.AsyncClient(base_url=url,headers={"Authorization":"Bearer "+token},
          timeout=httpx.Timeout(15.0,read=12.0),trust_env=False,
          limits=httpx.Limits(max_connections=8,max_keepalive_connections=4)) as client:
        unauthorized=await client.get("/api/v1/diagnostics/health",
                                     headers={"Authorization":"Bearer wrong"})
        if unauthorized.status_code!=401:raise RuntimeError("Security failure: unapproved reader admitted")
        results=[]
        for i in range(3):
            results.append(await roundtrip(client,i+1))
        good=all(row["ok"] and row["persisted"] for row in results)
        durations=[row["event_delivery_from_post_ms"] for row in results]
        print(json.dumps({"test":"real_authenticated_diagnostic_stream",
                          "passed":good,
                          "unauthorized_reader_rejected":True,
                          "roundtrips":results,
                          "median_delivery_from_post_ms":round(statistics.median(durations),1),
                          "scope":"Windows worker SSE + durable self-test events; no partner engine"},
                          separators=(",",":")))


if __name__=="__main__":
    asyncio.run(main())
