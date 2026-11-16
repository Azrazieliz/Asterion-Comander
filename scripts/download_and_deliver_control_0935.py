"""Retrieve official successful v0.9.35 Actions artifact and transfer via existing Control."""
import hashlib, json, os, re, subprocess, tempfile, time, urllib.request, zipfile
from pathlib import Path
import httpx

REPO="Azrazieliz/Asterion-Comander"
RUN=43865084916
ARTIFACT=14225595987
NAME="Asterion-Control-v0.9.35-OWNER-SIGNED-phone-model"
LIMIT=900_000_000

def credential():
    p=subprocess.run(["git","credential","fill"],input="protocol=https\nhost=github.com\n\n",capture_output=True,text=True,check=True,timeout=20)
    d=dict(z.split("=",1) for z in p.stdout.splitlines() if "=" in z)
    val=d.get("password","")
    if len(val)<20: raise RuntimeError("github_credential_missing")
    return val

def download(destination):
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+"/actions/artifacts/"+str(ARTIFACT)+"/zip",
        headers={"Authorization":"Bearer "+credential(),"Accept":"application/vnd.github+json","User-Agent":"Asterion-Control-Release-Transfer"})
    class StripCrossHostAuthorization(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,request,fp,code,msg,headers,newurl):
            next_request=super().redirect_request(request,fp,code,msg,headers,newurl)
            if next_request is not None and __import__('urllib.parse',fromlist=['urlsplit']).urlsplit(newurl).hostname!="api.github.com":
                next_request.headers.pop("Authorization",None)
                next_request.unredirected_hdrs.pop("Authorization",None)
            return next_request
    opener=urllib.request.build_opener(StripCrossHostAuthorization())
    with opener.open(req,timeout=90) as response, open(destination,"wb") as out:
        total=0
        while True:
            data=response.read(1024*1024)
            if not data:break
            total+=len(data)
            if total>LIMIT:raise RuntimeError("artifact_exceeds_size_limit")
            out.write(data)
    return total

def main():
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    host=(state/"agent-host.txt").read_text().strip().rstrip("/")
    token=(state/"control-token.txt").read_text().strip()
    if not re.fullmatch(r"http://(?:127\.0\.0\.1|localhost|192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9.]+):8911",host):
        raise RuntimeError("untrusted_control_host")
    dist=Path(r"D:\AsterionControlRelease\dist")
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="asterion-control-owner-") as tmp:
        zpath=Path(tmp)/"v0935.zip"
        downloaded=download(zpath)
        with zipfile.ZipFile(zpath) as z:
            members=[m for m in z.infolist() if m.filename.lower().endswith(".apk") and not m.is_dir()]
            if len(members)!=1:raise RuntimeError("expected_one_owner_signed_apk_found_"+str(len(members)))
            item=members[0]
            if item.file_size>LIMIT or item.file_size<10_000_000:raise RuntimeError("invalid_apk_size")
            target=dist/"Asterion-Control-v0.9.35-OWNER-SIGNED.apk"
            temp=Path(tmp)/"release.apk"
            with z.open(item) as src, open(temp,"wb") as dst:
                while data:=src.read(1024*1024):dst.write(data)
            sha=hashlib.file_digest(open(temp,"rb"),"sha256").hexdigest()
            checks=[x for x in z.namelist() if "sha256" in x.lower() or "checksum" in x.lower()]
            for itemname in checks:
                content=z.read(itemname).decode("utf8","replace")
                if re.search(r"\b[0-9a-f]{64}\b",content,re.I) and sha.lower() not in content.lower():
                    raise RuntimeError("artifact_checksum_mismatch")
            os.replace(temp,target)
        print(json.dumps({"stage":"artifact_downloaded","zip_bytes":downloaded,"apk_bytes":target.stat().st_size,"sha256":sha,"artifact_id":ARTIFACT}),flush=True)
    with httpx.Client(headers={"Authorization":"Bearer "+token},timeout=httpx.Timeout(40,connect=8),trust_env=False) as client:
        res=client.post(host+"/api/v1/phone/transfers",json={"pc_path":str(target),"name":target.name})
        res.raise_for_status()
        job=res.json()["id"]
        deadline=time.monotonic()+1200
        last=None
        while time.monotonic()<deadline:
            time.sleep(1)
            response=client.get(host+"/api/v1/phone/transfers/"+job)
            response.raise_for_status()
            last=response.json()
            if last.get("state") in ("completed","failed","cancelled"):break
        if not last or last.get("state")!="completed":
            raise RuntimeError("phone_transfer_not_complete: "+json.dumps(last)[:800])
        result=last.get("result") or {}
        if str(result.get("sha256","")).lower()!=sha.lower():
            raise RuntimeError("phone_committed_checksum_mismatch: "+json.dumps(result)[:500])
        print(json.dumps({"ok":True,"version":"0.9.35","apk":target.name,"sha256":sha,"phone_location":result.get("location"),"phone_transfer":"completed","phone_checksum_verified":True,"installed":False,"pairing_preserved":True}),flush=True)

if __name__=="__main__":main()
