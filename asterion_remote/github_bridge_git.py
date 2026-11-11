"""Private Asterion Control Git transport without GitHub REST API limits.
Uses the authorized Windows Control API; Android remains the controller.
"""
from __future__ import annotations
import json,os,subprocess,time,ipaddress
from urllib.parse import urlsplit
from pathlib import Path
from . import github_bridge
from .github_bridge import NAME,local_token,run

REPO='Azrazieliz/Asterion-Control-Bridge'
URL='https://github.com/'+REPO+'.git'
ROOT=Path(os.environ.get('ASTERION_BRIDGE_GIT_WORKTREE',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl' / 'private-bridge-repo')))
STAMP=ROOT.parent/'git-bridge-migration-v1.done'


def agent_host():
    """Follow the native Control host across private LAN changes."""
    state=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl'
    address_file=state/'agent-host.txt'
    address=(address_file.read_text('utf8').strip() if address_file.exists()
             else os.environ.get('ASTERION_CONTROL_HOST',''))
    parsed=urlsplit(address)
    try:
        ip=ipaddress.ip_address(parsed.hostname or '')
        port=parsed.port
    except (ValueError,TypeError) as exc:
        raise RuntimeError('Native Control agent endpoint not initialized') from exc
    cgnat=ip in ipaddress.ip_network('100.64.0.0/10')
    if (parsed.scheme!='http' or port!=8911 or parsed.username or
        parsed.password or parsed.path not in ('','/') or parsed.query or
        parsed.fragment or ip.is_unspecified or ip.is_multicast or
        ip.is_link_local or not (ip.is_private or ip.is_loopback or cgnat)):
        raise RuntimeError('Control endpoint is not an authorized private IP')
    host=('['+str(ip)+']') if ip.version==6 else str(ip)
    return 'http://'+host+':8911'

def ensure_agent(key):
    """Do not consume commands until the native Windows Control API answers."""
    github_bridge.PC=agent_host()
    response=github_bridge.pc('/api/v1/health',key)
    if not isinstance(response,dict) or not response.get('ok'):
        raise RuntimeError('Native Control agent is not healthy yet')
    return response

def outstanding_jobs():
    """Load only native job receipts that lack a final exit status."""
    folder=ROOT/'results'
    if not folder.is_dir():return []
    pending=[]
    for path in sorted(folder.glob('*.json')):
        if not NAME.fullmatch(path.stem):continue
        try: receipt=json.loads(path.read_text('utf8'))
        except (ValueError,OSError):continue
        if receipt.get('status') in ('accepted','running'):
            pending.append((path,receipt))
    return pending

def reconcile_jobs(key,pending):
    """Preserve uncertain execution without replaying side-effecting commands."""
    for path,receipt in pending:
        identity=path.stem
        if receipt.get('status')=='running':
            write_result(identity,dict(receipt,ok=False,status='uncertain',
                error='Previous Control worker stopped before a durable job receipt'))
            continue
        remote=receipt.get('result',{})
        ident=remote.get('id','') if isinstance(remote,dict) else ''
        if not isinstance(ident,str) or len(ident)!=32:
            write_result(identity,dict(receipt,ok=False,status='uncertain',
                error='Native job identifier unavailable'))
            continue
        try:
            job=run({'op':'pc_job_status','params':{'job_id':ident}},key)
        except Exception as exc:
            if '404' in str(exc) or 'Unknown job' in str(exc):
                write_result(identity,dict(receipt,ok=False,status='uncertain',
                    error='Agent restarted and lost job state; inspect saved build artifacts'))
                continue
            raise
        if job.get('status')!='finished':continue
        code=job.get('exit_code')
        good=code==0
        write_result(identity,dict(receipt,ok=good,
            status='complete' if good else 'error',
            result={'id':ident,'exit_code':code,
                    'output_tail':str(job.get('output',''))[-1600:]},
            error='' if good else 'Native Control command exited unsuccessfully'))

def git(*args,timeout=60):
    p=subprocess.run(['git',*args],cwd=ROOT if ROOT.is_dir() else None,
        text=True,capture_output=True,timeout=timeout,check=False)
    if p.returncode:
        raise RuntimeError('Git transport error '+str(p.returncode)+': '+(p.stderr or p.stdout)[-450:])
    return p.stdout.strip()

def sync_remote():
    """Recover committed, unpublished receipts after competing Git writers.

    A failed push can leave HEAD ahead of origin/main. An ff-only merge alone
    then blocks every future command, even while the native agent is healthy.
    Never drop local commits or replay an already journaled phone action.
    """
    git('fetch','--quiet','origin','main')
    unpublished=int(git('rev-list','--count','origin/main..HEAD'))
    if not unpublished:
        git('merge','--ff-only','origin/main')
        return
    paths=[p.strip() for p in git('log','--format=','--name-only',
                                  'origin/main..HEAD').splitlines() if p.strip()]
    if not paths or any(not p.startswith('results/') or not p.endswith('.json')
                        for p in paths):
        raise RuntimeError('Local bridge commits contain non-receipt changes; preserve and inspect')
    for attempt in range(10):
        git('fetch','--quiet','origin','main')
        git('rebase','origin/main')
        try:
            git('push','--quiet','origin','HEAD:main')
            return
        except RuntimeError:
            if attempt==9:raise
            time.sleep(min(10,1+attempt))


def setup():
    ROOT.parent.mkdir(parents=True,exist_ok=True)
    if not (ROOT/'.git').exists():
        git('clone','--quiet','--branch','main',URL,str(ROOT),timeout=90)
    remote=git('remote','get-url','origin').rstrip('/')
    if remote.lower()!=URL.lower():
        raise RuntimeError('Unexpected bridge remote: refusing to execute')
    sync_remote()

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

def write_result(identity,response,*,publish_now=True):
    folder=ROOT/'results';folder.mkdir(exist_ok=True)
    target=folder/(identity+'.json')
    if target.exists() and response.get('status')=='running':return False
    # Save a durable local in-flight marker BEFORE the native side effect.
    # Do not publish the intermediate "running" state: that used to require
    # an entire extra GitHub commit, fetch/rebase and push for every action.
    pending=folder/(identity+'.pending')
    with pending.open('w',encoding='utf8') as out:
        out.write(json.dumps(response,ensure_ascii=False,separators=(',',':')))
        out.flush()
        os.fsync(out.fileno())
    os.replace(pending,target)
    if publish_now:
        publish([Path('results')/(identity+'.json')])
    return True


def recover_unpublished():
    """Publish complete local receipts after a failed push, never replay them.

    Any unfinished local "running" receipt is handled by reconcile_jobs()
    and is marked uncertain without replaying a potentially executed action.
    """
    changes=git('status','--porcelain','--untracked-files=all','--','results')
    ready=[]
    for row in changes.splitlines():
        path=row[3:]
        if not path.startswith('results/') or not path.endswith('.json'):
            continue
        candidate=Path(path)
        if not NAME.fullmatch(candidate.stem):
            continue
        try:
            receipt=json.loads((ROOT/candidate).read_text(encoding='utf8'))
        except (ValueError,OSError):
            continue
        if receipt.get('status') in ('running','accepted'):
            continue
        ready.append(candidate)
    if ready:
        publish(ready)
    return len(ready)

def pending_in(folder):
    """Return only unknown commands; never replay a recorded running/error receipt."""
    results=ROOT/'results'
    results.mkdir(exist_ok=True)
    if not folder.is_dir():return []
    return [p for p in sorted(folder.glob('*.json'))
            if NAME.fullmatch(p.stem) and not (results/p.name).exists()]

def entries():
    """Explicit active queue survives first-start legacy-command migration.

    An older REST relay may have left ambiguous root-level commands. New,
    explicitly authorized Control commands use commands/active and are never
    preemptively classified as a pre-migration replay.
    """
    commands=ROOT/'commands'
    chosen=[];seen=set()
    for file in pending_in(commands/'active')+pending_in(commands):
        if file.stem in seen:continue
        chosen.append(file)
        seen.add(file.stem)
    return chosen

def migrate():
    if STAMP.exists():return
    # Never replay unknown previous jobs left by the failing REST relay.
    paths=[]
    # Explicit owner reauthorization in commands/active takes precedence over
    # an older root-level request with the same immutable checkpoint ID.
    authorized={p.stem for p in pending_in(ROOT/'commands'/'active')}
    for request in pending_in(ROOT/'commands'):
        if request.stem in authorized:continue
        target=ROOT/'results'/request.name
        target.write_text(json.dumps({'id':request.stem,'ok':False,'status':'skipped',
            'error':'Previous relay stalled; resubmit this command.'}),encoding='utf8')
        paths.append(Path('results')/request.name)
    if paths:publish(paths)
    STAMP.write_text('migrated',encoding='utf8')

def cycle(key):
    sync_remote()
    tasks=entries()
    unfinished=outstanding_jobs()
    if tasks or unfinished:
        ensure_agent(key)
    if unfinished:
        reconcile_jobs(key,unfinished)
    # A finished receipt written just before a previous push failed is
    # publication-only: NEVER execute the corresponding operation again.
    recover_unpublished()
    # Execute a bounded command burst against one already-fetched snapshot.
    # Each result is durably journaled before the next action, then ALL receipts
    # share one Git commit/fetch/rebase/push instead of one per command.
    # On a publishing failure recover_unpublished() publishes without replay.
    batch=[]
    for request in tasks[:12]:
        identity=request.stem
        # This receipt prevents replay after crashes but is not a success claim.
        write_result(identity,{'id':identity,'ok':False,'status':'running'},publish_now=False)
        started=time.monotonic()
        try:
            task=json.loads(request.read_text('utf8'))
            if task.get('id')!=identity or not isinstance(task.get('op'),str):
                raise ValueError('Invalid request identity')
            response=run(task,key)
            accepted=(task['op']=='pc_command' and isinstance(response,dict)
                and response.get('status')=='running'
                and isinstance(response.get('id'),str)
                and len(response['id'])==32)
            if task['op']=='pc_command' and not accepted:
                reply={'id':identity,'ok':False,'status':'uncertain',
                       'error':'No durable Windows job id from native Control',
                       'result':response}
            else:
                reply={'id':identity,'ok':True,
                       'status':'accepted' if accepted else 'complete',
                       'result':response}
            reply['elapsed_ms']=round((time.monotonic()-started)*1000)
        except Exception as exc:
            reply={'id':identity,'ok':False,'status':'error',
                   'elapsed_ms':round((time.monotonic()-started)*1000),
                   'error':str(exc)[:500]}
        write_result(identity,reply,publish_now=False)
        batch.append(Path('results')/(identity+'.json'))
        print('Asterion Control',identity,reply['status'],flush=True)
    if batch:
        publish(batch)
    return len(batch)

def main():
    setup()
    migrate()
    secret=local_token()
    print('Asterion Control private Git transport active; no REST quota',flush=True)
    failures=0
    while True:
        try:
            processed=cycle(secret)
            failures=0
            # A short command burst keeps interactive control responsive;
            # idle polling remains bounded, without GitHub REST API quotas.
            time.sleep(2 if processed else 3)
        except KeyboardInterrupt:return
        except Exception as exc:
            failures+=1
            print('Bridge retry:',type(exc).__name__,str(exc)[:180],flush=True)
            time.sleep(min(45,failures*5))

if __name__=='__main__':main()
