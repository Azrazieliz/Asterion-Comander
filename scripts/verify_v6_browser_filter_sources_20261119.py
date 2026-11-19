"""M5 genuine HTTPS EasyList/EasyPrivacy upstream compatibility acceptance.

Independent Windows-side comparison of host-anchored subset used by native
BrowserProtection; no remote page content, cookies or credentials transmitted.
Real WebView interception still requires installed Android acceptance.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from datetime import datetime,timezone
import httpx

SOURCES=(
    "https://easylist.to/easylist/easylist.txt",
    "https://easylist.to/easylist/easyprivacy.txt",
)
HOST=re.compile(r"^[a-z0-9.-]+$")
MAX_SOURCE=10*1024*1024
SKIP=("domain=","denyallow=","~third-party","redirect=","rewrite=")
SEED={
    "doubleclick.net","googlesyndication.com","googleadservices.com",
    "adnxs.com","criteo.com","taboola.com","outbrain.com",
    "scorecardresearch.com","pubmatic.com","rubiconproject.com",
    "casalemedia.com","adsrvr.org","smartadserver.com",
    "quantserve.com","adsafeprotected.com",
}

def digest_and_parse(content:bytes,blocks:set[str],excepts:set[str])->int:
    if not 30000<=len(content)<=MAX_SOURCE:raise ValueError("Invalid actual list length")
    lines=content.decode("utf8","replace").splitlines()
    count=0
    for raw in lines:
        rule=raw.strip()
        if rule.startswith(("!","[","#")):continue
        exception=rule.startswith("@@")
        if exception:rule=rule[2:]
        if not rule.startswith("||"):continue
        at=2
        while at<len(rule) and (rule[at].isalnum() or rule[at] in ".-"):
            at+=1
        if not 4<=at-2<=180:continue
        domain=rule[2:at].lower()
        if not "." in domain or ".." in domain or domain.startswith(".") or \
           domain.endswith(".") or not HOST.fullmatch(domain):continue
        suffix=rule[at:]
        if any(bad in suffix for bad in SKIP):continue
        if not(suffix=="" or suffix=="^" or suffix.startswith("^$") or suffix.startswith("$")):
            continue
        if exception:
            if suffix in ("","^"):excepts.add(domain)
        else:blocks.add(domain)
        count+=1
    return count


def main():
    blocks=set(SEED)
    excepts=set()
    reports=[]
    with httpx.Client(timeout=httpx.Timeout(20,read=35),follow_redirects=False,
                       headers={"User-Agent":"AsterionBrowser/1.0"}) as client:
        for source in SOURCES:
            r=client.get(source)
            if r.status_code!=200:
                raise RuntimeError("Browser source HTTP status "+str(r.status_code))
            n=digest_and_parse(r.content,blocks,excepts)
            reports.append({"source":source,"http":r.status_code,"bytes":len(r.content),
                            "sha256":hashlib.sha256(r.content).hexdigest(),"parsed":n,
                            "version":r.text.splitlines()[1][:90]})
    if sum(item["parsed"] for item in reports)<1200:
        raise RuntimeError("Inadequate usable URL host rules; no release acceptance")
    if not all(host in blocks for host in SEED):
        raise RuntimeError("Verified built-in ad-domain seed missing")
    print(json.dumps({"ok":True,"checked_at":datetime.now(timezone.utc).isoformat(),
          "sources":reports,"unique_domains":len(blocks),"exceptions":len(excepts),
          "browser_webview_device_verified":False},separators=(",",":")))
if __name__=="__main__":
    try:main()
    except Exception as failure:
        print(json.dumps({"ok":False,"reason":type(failure).__name__}))
        raise
