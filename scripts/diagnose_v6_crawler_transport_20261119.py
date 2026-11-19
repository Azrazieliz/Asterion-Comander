"""Safe source-only crawler transport diagnostic (never logs proxy credentials)."""
from __future__ import annotations
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asterion_remote.browser_crawler import _fetch, validated_public_https
from fastapi import HTTPException
import httpx

host="https://example.org/"
evidence={"target":"public_example_org","no_site_content_logged":True}
try:
    domain,ip,path=validated_public_https(host)
    evidence["dns_validated_global"]=True
    evidence["dns_ip_version"]=6 if ":" in ip else 4
except Exception as e:
    evidence["dns_validated_global"]=False
    evidence["dns_error_class"]=type(e).__name__
try:
    res=_fetch(host,100000)
    evidence["pinned_tls"]={"status":res.status,"bytes":len(res.content),"ok":res.status==200}
except HTTPException as e:
    evidence["pinned_tls"]={"http_status":e.status_code,
       "classification":str(e.detail)[:130]}
except Exception as e:
    evidence["pinned_tls"]={"classification":type(e).__name__}
for name,trust in (("windows_environment_https",True),("direct_https",False)):
    try:
        with httpx.Client(timeout=8,trust_env=trust,
                          follow_redirects=False) as c:
            r=c.get(host,headers={"User-Agent":"AsterionBrowser/1.0"})
            evidence[name]={"status":r.status_code,"tls_usable":r.status_code<500}
    except Exception as e:
        evidence[name]={"exception":type(e).__name__}
print(json.dumps(evidence,sort_keys=True,separators=(",",":")))
