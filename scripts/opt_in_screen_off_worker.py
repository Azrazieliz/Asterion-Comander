"""Optional, explicitly started screen-independent developer worker.

Uses a SEPARATE OpenAI Responses API conversation (not the ChatGPT app thread).
No subscription/API credential is taken from ChatGPT. Does nothing without
OPENAI_API_KEY. Max steps/tool actions are bounded; no scheduled auto-start.
All edits are confined to one clean, non-production Git work branch.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.openai.com/v1/responses"
MODEL = os.getenv("ASTERION_WORKER_MODEL", "gpt-5.5")
NO_FILE = {".git", ".env", ".ssh", "node_modules", "build", ".gradle", "__pycache__"}
SECRET_SUFFIX = (".keystore", ".jks", ".p12", ".pfx", ".pem", ".key", ".apk", ".aab")
MAX_READ = 40000
MAX_WRITE = 64000

def git(root: Path, *argv: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *argv],
        capture_output=True, text=True, timeout=50, check=False)
    if result.returncode:
        raise RuntimeError(("Git " + argv[0] + ": " + result.stderr.strip())[:400])
    return result.stdout.strip()

def safe_path(root: Path, path: str, *, new: bool = False) -> Path:
    if not isinstance(path, str) or not path or len(path) > 260:
        raise ValueError("Invalid repository path")
    if Path(path).is_absolute() or any(x in ("", ".", "..") for x in Path(path).parts):
        raise ValueError("Path must be a relative project file")
    parts = Path(path).parts
    if any(x.lower() in NO_FILE for x in parts):
        raise ValueError("Sensitive/build directory not available")
    if Path(path).suffix.lower() in SECRET_SUFFIX or Path(path).name.startswith(".env"):
        raise ValueError("Sensitive or compiled file denied")
    full = root.joinpath(*parts).resolve(strict=False)
    if not full.is_relative_to(root) or full.is_symlink():
        raise ValueError("Path escapes canonical repository")
    if not new and not full.is_file():
        raise FileNotFoundError("Project file does not exist")
    return full

def rpc(key: str, payload: dict) -> dict:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(API, data=raw, method="POST",
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=105) as result:
            obj = json.load(result)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Responses API returned HTTP " + str(exc.code)) from None
    except Exception as exc:
        raise RuntimeError("Responses API outcome uncertain; no automatic retry (" +
                           type(exc).__name__ + ")") from None
    if not isinstance(obj, dict) or not isinstance(obj.get("id"), str):
        raise RuntimeError("Responses API returned no durable response ID")
    return obj

def definitions(write: bool, push: bool) -> list[dict]:
    def t(name: str, description: str, props: dict, required: list[str]) -> dict:
        return {"type": "function", "name": name, "description": description,
          "parameters": {"type":"object","properties":props,
            "required":required,"additionalProperties":False},"strict": True}
    string = {"type":"string"}
    result = [
      t("repo_status","Inspect current git branch, HEAD, and tracked changes",{},[]),
      t("repo_list","List bounded tracked repository files under subdir",
        {"subdir":string},["subdir"]),
      t("repo_read","Read an existing UTF-8 project file, max 40k characters",
        {"path":string},["path"]),
    ]
    if write:
        result += [
          t("repo_write","Atomically write one permitted project source/text file",
            {"path":string,"content":string},["path","content"]),
          t("repo_commit","Commit only files written by this worker",
            {"message":string},["message"]),
        ]
        if push:
            result.append(t("repo_push","Fast-forward push approved work branch (never force)",
              {},[]))
    return result

class Workspace:
    def __init__(self, root: Path, write: bool, push: bool):
        self.root = root.resolve(strict=True)
        if not (self.root / ".git").exists():
            raise ValueError("A local Git repository is required")
        self.branch = git(self.root, "branch", "--show-current")
        if not self.branch.startswith("work/"):
            raise ValueError("Refuse non-work Git branch: " + self.branch)
        self.write, self.push = write, push
        self.changed: set[str] = set()
        if write and git(self.root, "status", "--porcelain"):
            raise ValueError("Repo is already dirty; preserve existing user edits")
    def call(self, name: str, args: dict) -> dict:
        try:
            if name == "repo_status":
                return {"ok":True,"branch":self.branch,
                    "head":git(self.root,"rev-parse","HEAD"),
                    "status":git(self.root,"status","--short")[:1800]}
            if name == "repo_list":
                path = args["subdir"]
                if path:
                    safe_path(self.root,path,new=True)
                names = (git(self.root,"ls-files","--",path) if path
                         else git(self.root,"ls-files")).splitlines()
                return {"ok":True,"paths":names[:220],"truncated":len(names)>220}
            if name == "repo_read":
                path = safe_path(self.root,args["path"])
                content = path.read_text(encoding="utf-8")
                return {"ok":True,"path":args["path"],
                    "content":content[:MAX_READ],
                    "truncated":len(content)>MAX_READ}
            if name == "repo_write" and self.write:
                path = safe_path(self.root,args["path"],new=True)
                value=args["content"]
                if not isinstance(value,str) or len(value)>MAX_WRITE:
                    raise ValueError("Source content exceeds limit")
                path.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="w",dir=path.parent,
                     encoding="utf-8",delete=False) as tmp:
                    tmp.write(value);target=Path(tmp.name)
                target.replace(path)
                self.changed.add(str(path.relative_to(self.root)))
                return {"ok":True,"path":args["path"],"bytes":len(value.encode())}
            if name == "repo_commit" and self.write:
                if not self.changed: return {"ok":False,"reason":"Nothing written"}
                message=args["message"]
                if not 5<=len(message)<=180:raise ValueError("Invalid commit message")
                git(self.root,"add","--",*sorted(self.changed))
                git(self.root,"-c","user.name=Asterion API Worker","-c",
                    "user.email=asterion-api-worker@users.noreply.github.com",
                    "commit","-m",message)
                self.changed.clear()
                return {"ok":True,"head":git(self.root,"rev-parse","HEAD")}
            if name == "repo_push" and self.write and self.push:
                if self.changed:raise ValueError("Commit your changes first")
                git(self.root,"push","origin","HEAD:refs/heads/"+self.branch)
                return {"ok":True,"branch":self.branch}
            return {"ok":False,"error":"Operation not approved"}
        except Exception as exc:
            return {"ok":False,"error":type(exc).__name__,
                "reason":str(exc)[:320]}

def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2),encoding="utf-8")
    tmp.replace(path)

def main() -> int:
    ap=argparse.ArgumentParser(description="Explicit opt-in screen-independent API worker")
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--task",required=True)
    ap.add_argument("--write",action="store_true")
    ap.add_argument("--push",action="store_true")
    ap.add_argument("--max-responses",type=int,default=12)
    ap.add_argument("--max-tools",type=int,default=40)
    ap.add_argument("--state",type=Path,default=None)
    args=ap.parse_args()
    if args.push and not args.write:ap.error("--push requires --write")
    if not 1<=args.max_responses<=30 or not 1<=args.max_tools<=90:
        ap.error("Bounded limits required")
    api_key=os.getenv("OPENAI_API_KEY","").strip()
    if len(api_key)<20:
        print("DISABLED: OPENAI_API_KEY not configured; no API call, no charges")
        return 3
    repo=Workspace(args.repo,args.write,args.push)
    state=args.state or repo.root.parent/".asterion-control-worker"/(repo.root.name+".json")
    if state.exists():
        print("STOP: previous worker state exists; inspect/archive before a new run")
        return 4
    tools=definitions(args.write,args.push)
    instructions = (
      "You are a bounded developer worker operating only on an authorized Git work branch. "
      "Use repo tools to inspect real files, make minimal correct changes when allowed, "
      "test only through the supplied tools, and commit real progress. "
      "Never invent a compilation, installation, approval, test or completion. "
      "Avoid changes unrelated to the task. Stop when no further real work can be "
      "completed with the available tools. This API conversation is SEPARATE from "
      "consumer ChatGPT and does not submit messages into its UI."
    )
    state_data={"repo":str(repo.root),"branch":repo.branch,"model":MODEL,
        "task":args.task,"status":"running","last_response_id":None,
        "responses":0,"tool_actions":0,"events":[]}
    atomic_json(state,state_data)
    next_input=[{"role":"user","content":args.task}]
    previous=None
    try:
        for i in range(args.max_responses):
            if state.with_suffix(".stop").exists():
                state_data["status"]="stopped_by_owner";break
            payload={"model":MODEL,"instructions":instructions,"input":next_input,
                "tools":tools,"store":True,"max_output_tokens":2400}
            if previous: payload["previous_response_id"]=previous
            result=rpc(api_key,payload)
            previous=result["id"]
            state_data["last_response_id"]=previous
            state_data["responses"]=i+1
            calls=[item for item in result.get("output",[])
                   if isinstance(item,dict) and item.get("type")=="function_call"]
            if not calls:
                state_data["status"]="completed_response"
                state_data["answer"]=str(result.get("output_text") or "")[:8000]
                if not state_data["answer"]:
                    state_data["answer"]=json.dumps(result.get("output",[]))[:8000]
                break
            next_input=[]
            for item in calls:
                if state_data["tool_actions"]>=args.max_tools:
                    state_data["status"]="tool_limit_reached"
                    break
                try:parameters=json.loads(item.get("arguments") or "{}")
                except json.JSONDecodeError:parameters={}
                receipt=repo.call(item.get("name",""),parameters)
                state_data["tool_actions"]+=1
                state_data["events"].append({"tool":item.get("name"),
                  "ok":receipt.get("ok",False),
                  "reason":receipt.get("reason","")[:160]})
                next_input.append({"type":"function_call_output",
                    "call_id":item["call_id"],"output":json.dumps(receipt)})
            atomic_json(state,state_data)
            if state_data["status"]=="tool_limit_reached":break
        else:
            state_data["status"]="response_limit_reached"
    except Exception as exc:
        state_data["status"]="uncertain_or_failed"
        state_data["error"]=str(exc)[:400]
    finally:
        atomic_json(state,state_data)
    print(json.dumps({"status":state_data["status"],"responses":state_data["responses"],
       "tool_actions":state_data["tool_actions"],
       "branch":repo.branch,"head":git(repo.root,"rev-parse","HEAD"),
       "state":str(state)},ensure_ascii=False))
    return 0 if state_data["status"]=="completed_response" else 6

if __name__=="__main__":
    sys.exit(main())
