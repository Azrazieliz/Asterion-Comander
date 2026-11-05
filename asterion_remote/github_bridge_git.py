"""Private Asterion Control Git transport without GitHub REST API limits.
Uses the authorized Windows Control API; Android remains the controller.
"""
from __future__ import annotations
import json,os,subprocess,time
from pathlib import Path
from .github_bridge import NAME,local_token,run

REPO='Azrazieliz/Asterion-Control-Bridge'
URL='https://github.com/'+REPO+'.git'
ROOT=Path(os.environ.get('ASTERION_BRIDGE_GIT_WORKTREE',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl' / 'private-bridge-repo')))
STAMP=ROOT.parent/'git-bridge-migration-v1.done'

def git(*args,timeout=60):
    p=subprocess.run(['git',*args],cwd=ROOT if ROOT.is_dir() else None,
        text=True,capture_output=True,timeout=timeout,check=False)
    if p.returncode:
        raise RuntimeError('Git transport error '+str(p.returncode)+': '+(p.stderr or p.stdout)[-450:])
    return p.stdout.strip()

def setup():
    ROOT.parent.mkdir(parents=True,exist_ok=True)
    if not (ROOT/'.git').exists():
        git('clone','--quiet','--branch','main',URL,str(ROOT),timeout=90)
    remote=git('remote','get-url','origin').rstrip('/')
    if remote.lower()!=URL.lower():
        raise RuntimeError('Unexpected bridge remote: refusing to execute')
    git('fetch','--quiet','origin','main')
    git('merge','--ff-only','origin/main')

def publish(paths):
    git('add','--',*[str(p) for p in paths])
    if not git('status','--porcelain'):return
    git('-c','user.name=Asterion Control','-c','user.email=asterion-control@users.noreply.github.com',
        'commit','--quiet','-m','Asterion Control private bridge results')
    for attempt in range(4):
        git('fetch','--quiet','origin','main')
        git('rebase','origin/main')
        try:
            git('push','--quiet','origin','HEAD:main')
            return
        except RuntimeError:
            if attempt==3:raise
            time.sleep(1+attempt)

def write_result(identity,response):
    folder=ROOT/'results';folder.mkdir(exist_ok=True)
    target=folder/(identity+'.json')
    if target.exists() and response.get('status')=='running':return False
    target.write_text(json.dumps(response,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    publish([Path('results')/(identity+'.json')])
    return True

def entries():
    commands=ROOT/'commands';results=ROOT/'results';results.mkdir(exist_ok=True)
    if not commands.is_dir():return []
    return [p for p in sorted(commands.glob('*.json')) if NAME.fullmatch(p.stem) and not (results/p.name).exists()]

def migrate():
    if STAMP.exists():return
    # Never replay unknown previous jobs left by the failing REST relay.
    paths=[]
    for request in entries():
        target=ROOT/'results'/request.name
        target.write_text(json.dumps({'id':request.stem,'ok':False,'status':'skipped',
            'error':'Previous relay stalled; resubmit this command.'}),encoding='utf8')
        paths.append(Path('results')/request.name)
    if paths:publish(paths)
    STAMP.write_text('migrated',encoding='utf8')

def cycle(key):
    git('fetch','--quiet','origin','main')
    git('merge','--ff-only','origin/main')
    tasks=entries()
    for request in tasks:
        identity=request.stem
        write_result(identity,{'id':identity,'ok':False,'status':'running'})
        started=time.monotonic()
        try:
            task=json.loads(request.read_text('utf8'))
            if task.get('id')!=identity or not isinstance(task.get('op'),str):
                raise ValueError('Invalid request identity')
            result=run(task,key)
            reply={'id':identity,'ok':True,'status':'complete',
                'elapsed_ms':round((time.monotonic()-started)*1000),'result':result}
        except Exception as exc:
            reply={'id':identity,'ok':False,'status':'error',
                'elapsed_ms':round((time.monotonic()-started)*1000),'error':str(exc)[:500]}
        write_result(identity,reply)
        print('Asterion Control',identity,reply['status'],flush=True)
    return len(tasks)

def main():
    setup()
    migrate()
    secret=local_token()
    print('Asterion Control private Git transport active; no REST quota',flush=True)
    failures=0
    while True:
        try:
            cycle(secret);failures=0;time.sleep(4)
        except KeyboardInterrupt:return
        except Exception as exc:
            failures+=1
            print('Bridge retry:',type(exc).__name__,str(exc)[:180],flush=True)
            time.sleep(min(45,failures*5))

if __name__=='__main__':main()
