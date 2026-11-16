"""Read-only local AI discovery for the owner's existing Control computer.

Never downloads models, starts a server, calls public networks or prints user
files/tokens. Only loopback JSON model registries and known model directories
are inspected. Model presence is NOT a successful inference benchmark.
"""
from __future__ import annotations
import json, os, pathlib, urllib.request, urllib.error

def get(port,route):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}{route}",timeout=2) as response:
            if response.status!=200:return {"reachable":False,"status":response.status}
            body=response.read(262145)
            if len(body)>262144:return {"reachable":True,"valid":False}
            obj=json.loads(body)
            rows=obj.get("models",obj.get("data",[]))
            if not isinstance(rows,list):rows=[]
            models=[]
            for entry in rows[:24]:
                if isinstance(entry,dict):
                    model=entry.get("model",entry.get("name",entry.get("id","")))
                    if isinstance(model,str) and len(model)<=120:models.append(model)
            return {"reachable":True,"model_count":len(rows),
                    "model_ids":models[:12],"endpoint":route}
    except (urllib.error.URLError,TimeoutError,OSError,json.JSONDecodeError,
            ValueError) as exc:
        return {"reachable":False,"error_class":type(exc).__name__}

def main():
    base=pathlib.Path(os.environ.get("LOCALAPPDATA",str(pathlib.Path.home())))
    checks={
      "llama_cpp":get(8080,"/v1/models"),
      "ollama":get(11434,"/api/tags"),
      "configured_endpoint_present":bool(os.getenv("ASTERION_LOCAL_MODEL_ENDPOINT")),
      "configured_model_present":bool(os.getenv("ASTERION_LOCAL_MODEL_ID")),
    }
    roots=[
      base/"Ollama"/"models",
      pathlib.Path.home()/".ollama"/"models",
      pathlib.Path("D:/AsterionControlRelease/models"),
    ]
    checks["known_local_model_directories"]=[
        {"slot":index+1,"exists":path.is_dir(),
         "top_level_entries":len(list(path.iterdir())[:12]) if path.is_dir() else 0}
         for index,path in enumerate(roots)]
    print(json.dumps(checks,sort_keys=True),flush=True)

if __name__=="__main__":main()
