"""Non-disruptive real Control benchmark from the already-paired Windows worker.

Measures worker-local authenticated Windows and Android read-only API response
latency. Does not claim to measure ChatGPT decision/connector time.
Never moves input, changes apps, displays secrets or requires screen capture.
"""
from __future__ import annotations
import asyncio
import json
import os
import statistics
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx


def pct(values, fraction):
    if not values:
        return None
    values=sorted(values)
    index=max(0,min(len(values)-1,int((len(values)-1)*fraction)))
    return round(values[index],1)


async def main():
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    url=(state/"agent-host.txt").read_text(encoding="utf8").strip()
    token=(state/"control-token.txt").read_text(encoding="utf8").strip()
    parsed=urlsplit(url)
    if parsed.scheme!="http" or parsed.port!=8911 or not parsed.hostname:
        raise RuntimeError("Existing private Control worker endpoint unavailable")
    if len(token)<32:
        raise RuntimeError("Existing owner authentication unavailable")
    route={"/api/v1/health":"pc_health",
           "/api/v1/phone/ui":"phone_ui",
           "/api/v1/phone":"phone_health"}
    results={value:[] for value in route.values()}
    failures={value:[] for value in route.values()}
    async with httpx.AsyncClient(base_url=url,
       headers={"Authorization":"Bearer "+token},trust_env=False,
       timeout=httpx.Timeout(5.0,connect=3.0),
       limits=httpx.Limits(max_connections=10,max_keepalive_connections=6)) as client:
        for i in range(20):
            for path,kind in route.items():
                start=time.perf_counter()
                try:
                    response=await client.get(path)
                    elapsed=(time.perf_counter()-start)*1000
                    if response.status_code!=200:
                        failures[kind].append("HTTP_"+str(response.status_code))
                        continue
                    value=response.json()
                    if kind=="phone_ui" and not value.get("foreground_package"):
                        failures[kind].append("missing_foreground")
                        continue
                    if kind=="phone_health" and not value.get("reachable"):
                        failures[kind].append("not_reachable")
                        continue
                    results[kind].append(elapsed)
                except (httpx.HTTPError,ValueError) as e:
                    failures[kind].append(type(e).__name__)
            await asyncio.sleep(.08)
    report={"test":"actual_persistent_worker_readonly_pc_phone",
            "actions_per_kind":20,
            "scope":"worker_to_device_round_trip_only",
            "chatgpt_inclusive":False,
            "measured":{k:{"success":len(v),"failed":len(failures[k]),
                           "median_ms":round(statistics.median(v),1) if v else None,
                           "p95_ms":pct(v,.95),
                           "max_ms":round(max(v),1) if v else None,
                           "failure_types":sorted(set(failures[k]))}
                        for k,v in results.items()}}
    print(json.dumps(report,separators=(",",":")))


if __name__=="__main__":
    asyncio.run(main())
