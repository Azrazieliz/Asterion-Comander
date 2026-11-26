"""Private Asterion Control Git transport without GitHub REST API limits.
Uses the authorized Windows Control API; Android remains the controller.
"""
from __future__ import annotations
import json,os,subprocess,time,ipaddress,re,urllib.error
from urllib.parse import urlsplit
from pathlib import Path
from . import github_bridge
from .github_bridge import NAME,local_token,run
from .bridge_worker_lock import worker_process_lock, WorkerAlreadyRunning

REPO='Azrazieliz/Asterion-Control-Bridge'
URL='https://github.com/'+REPO+'.git'
ROOT=Path(os.environ.get('ASTERION_BRIDGE_GIT_WORKTREE',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl' / 'private-bridge-repo')))
STAMP=ROOT.parent/'git-bridge-migration-v1.done'
# Stable owner-state lock, independent of optional worktree overrides.
WORKER_LOCK=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'AsterionControl' / 'control-git-bridge-worker.lock'

# Persistent, sanitized liveness journal. The watchdog must check progress,
# not merely the existence of a python.exe process. Never write credentials,
# request arguments, user files, network endpoints or command stdout here.
HEALTH=ROOT.parent/'control-git-bridge-health.json'
HEALTH_STATE={'phase':'starting','last_sync_utc':None,'last_publish_utc':None,
              'inflight_id':None,'pending_count':None,'consecutive_errors':0}
HEALTH_PHASES={'starting','setup','syncing','idle','processing','publishing',
               'retrying','startup_error'}
def _utc_now():
    from datetime import datetime,timezone
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def health(phase,**fields):
    if phase not in HEALTH_PHASES:
        raise ValueError('Unsupported transport health phase')
    allowed={'last_sync_utc','last_publish_utc','inflight_id',
             'pending_count','consecutive_errors','error_kind'}
    if set(fields)-allowed:
        raise ValueError('Unsupported transport health metadata')
    HEALTH_STATE.update(fields)
    HEALTH_STATE.update(phase=phase,heartbeat_utc=_utc_now(),
                        schema=1,transport='private_git',pid=os.getpid())
    HEALTH.parent.mkdir(parents=True,exist_ok=True)
    temp=HEALTH.with_suffix('.tmp')
    try:
        with temp.open('w',encoding='utf8') as target:
            json.dump(HEALTH_STATE,target,sort_keys=True,separators=(',',':'))
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp,HEALTH)
    finally:
        if temp.exists():
            temp.unlink()



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

# A long backlog of accepted PC jobs must not starve newly authorized
# commands or require thousands of sequential native status roundtrips.
# Rotate checks without ever reexecuting a submitted side effect.
_RECONCILE_CURSOR = 0
RECONCILE_PER_CYCLE = 3

def reconcile_slice(pending):
    global _RECONCILE_CURSOR
    if not pending:
        _RECONCILE_CURSOR = 0
        return []
    start = _RECONCILE_CURSOR % len(pending)
    size = min(RECONCILE_PER_CYCLE, len(pending))
    batch = [pending[(start + k) % len(pending)] for k in range(size)]
    _RECONCILE_CURSOR = (start + size) % len(pending)
    return batch


_RECEIPT_CACHE_ROOT=None
_RECEIPT_CACHE={}

def outstanding_jobs():
    """Only parse changed receipts, not every historical JSON on every poll.

    File fingerprints include inode, timestamps and size; atomic replacement
    invalidates a prior receipt even if its length is unchanged. The cache is
    memory-only and is rebuilt on restart or root change.
    """
    global _RECEIPT_CACHE_ROOT,_RECEIPT_CACHE
    folder=ROOT/'results'
    if _RECEIPT_CACHE_ROOT!=folder:
        _RECEIPT_CACHE_ROOT=folder
        _RECEIPT_CACHE={}
    if not folder.is_dir():
        _RECEIPT_CACHE={}
        return []
    found={}
    pending=[]
    with os.scandir(folder) as entries:
        for entry in entries:
            if not entry.name.endswith('.json') or not NAME.fullmatch(entry.name[:-5]):
                continue
            try:
                if not entry.is_file(follow_symlinks=False):continue
                info=entry.stat(follow_symlinks=False)
                fingerprint=(info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
                old=_RECEIPT_CACHE.get(entry.name)
                path=Path(entry.path)
                if old is not None and old[0]==fingerprint:
                    receipt=old[1]
                else:
                    value=json.loads(path.read_text('utf8'))
                    receipt=value if isinstance(value,dict) and value.get('status') in ('accepted','running') else None
                found[entry.name]=(fingerprint,receipt)
                if receipt is not None:pending.append((path,receipt))
            except (ValueError,OSError):continue
    _RECEIPT_CACHE=found
    return sorted(pending,key=lambda item:item[0].name)


def reconcile_jobs(key,pending,*,publish_now=True):
    """Preserve uncertain execution without replaying side-effecting commands."""
    changed=[]
    def record(identity,response):
        if write_result(identity,response,publish_now=publish_now):
            changed.append(Path('results')/(identity+'.json'))
    for path,receipt in pending:
        identity=path.stem
        if receipt.get('status')=='running':
            record(identity,dict(receipt,ok=False,status='uncertain',
                error='Previous Control worker stopped before a durable job receipt'))
            continue
        remote=receipt.get('result',{})
        ident=remote.get('id','') if isinstance(remote,dict) else ''
        if not isinstance(ident,str) or len(ident)!=32:
            record(identity,dict(receipt,ok=False,status='uncertain',
                error='Native job identifier unavailable'))
            continue
        try:
            if receipt.get('operation')=='phone_transfer_start':
                job=run({'op':'phone_transfer_status','params':{'transfer_id':ident}},key)
            else:
                job=run({'op':'pc_job_status','params':{'job_id':ident}},key)
        except Exception as exc:
            if '404' in str(exc) or 'Unknown job' in str(exc):
                record(identity,dict(receipt,ok=False,status='uncertain',
                    error='Agent restarted and lost job state; inspect saved build artifacts'))
                continue
            # A transient query failure for an old job must not starve fresh
            # commands. Keep its accepted receipt and revisit on rotation.
            print('Native job reconciliation deferred:',type(exc).__name__,flush=True)
            continue
        if receipt.get('operation')=='phone_transfer_start':
            if not isinstance(job,dict) or job.get('id')!=ident:continue
            state=job.get('state')
            if state=='outcome_unknown' and job.get('worker_active') is not False:continue
            if state not in ('completed','failed','cancelled','outcome_unknown'):continue
            result=job.get('result')
            verified=(state=='completed' and isinstance(result,dict) and
                result.get('verified') is True and type(result.get('size')) is int and
                result['size']==job.get('size')==job.get('bytes_sent') and
                isinstance(result.get('sha256'),str) and
                re.fullmatch('[a-f0-9]{64}',result['sha256']) is not None and
                isinstance(result.get('location'),str) and
                result['location'].startswith('Downloads/Asterion Control/') and
                isinstance(result.get('android_uri'),str) and result['android_uri'].startswith('content://'))
            terminal='complete' if verified else ('error' if state in ('failed','cancelled') else 'uncertain')
            record(identity,dict(receipt,ok=verified,status=terminal,
                result={'id':ident,'state':state,'receipt':result if verified else None},
                error='' if verified else 'Native transfer '+state+'; no verified publication'))
            continue
        if not isinstance(job,dict) or job.get('status')!='finished':continue
        code=job.get('exit_code')
        good=code==0
        record(identity,dict(receipt,ok=good,
            status='complete' if good else 'error',
            result={'id':ident,'exit_code':code,
                    'output_tail':str(job.get('output',''))[-1600:]},
            error='' if good else 'Native Control command exited unsuccessfully'))
    return changed


def git(*args,timeout=60,env=None):
    p=subprocess.run(['git',*args],cwd=ROOT if ROOT.is_dir() else None,
        text=True,capture_output=True,timeout=timeout,check=False,env=env)
    if p.returncode:
        raise RuntimeError('Git transport error '+str(p.returncode)+': '+(p.stderr or p.stdout)[-450:])
    return p.stdout.strip()

def preserve_dirty_receipts():
    """Preserve local result journals before a fetch/rebase, never reset them.

    A finished Windows job can update an already-tracked accepted receipt. If
    the process restarts before publishing it, git rebase otherwise refuses
    to start and the supervisor repeatedly launches an unusable worker.
    """
    # The shared git() helper strips leading whitespace. Porcelain's first
    # column can be a space (e.g. " M results/foo.json"), so read raw output.
    probe=subprocess.run(['git','status','--porcelain','--untracked-files=all'],
        cwd=ROOT,text=True,capture_output=True,timeout=60,check=False)
    if probe.returncode:
        raise RuntimeError('Unable to inspect local bridge receipts: '+probe.stderr[-300:])
    status=probe.stdout
    candidates=[]
    for row in status.splitlines():
        flags,path=row[:2],row[3:]
        # Unrelated untracked files do not need intervention.
        # Keep incomplete atomic journal markers (.pending) and other
        # untracked auxiliary files untouched; only JSON receipts are synced.
        if flags=='??' and not (path.startswith('results/') and path.endswith('.json')):
            continue
        if (flags not in (' M','M ','MM','??','A ','AM') or
            not path.startswith('results/') or not path.endswith('.json') or
            not NAME.fullmatch(Path(path).stem)):
            raise RuntimeError('Unsafe local bridge change; left untouched: '+path[:160])
        candidate=ROOT/path
        try:
            value=json.loads(candidate.read_text(encoding='utf8'))
            if value.get('id')!=candidate.stem or not isinstance(value.get('status'),str):
                raise ValueError('Result identity/status mismatch')
        except (OSError,ValueError,AttributeError) as exc:
            raise RuntimeError('Invalid local result; left untouched: '+path) from exc
        candidates.append((path,candidate))
    if not candidates:return 0
    # The existing Git object store is the durable journal. Do not duplicate
    # receipts into an extra PC directory; commit before moving any ref.
    git('add','--',*[path for path,_ in candidates])
    git('-c','user.name=Asterion Control',
        '-c','user.email=asterion-control@users.noreply.github.com',
        'commit','--quiet','-m','Recover durable local Asterion Control result receipts')
    print('Bridge preserved',len(candidates),'dirty receipt(s) before remote sync',flush=True)
    return len(candidates)


def recover_interrupted_rebase():
    """Preserve committed receipt history before aborting a failed Git rebase.

    An interrupted rebase can leave .git/rebase-merge across worker restarts.
    Until cleared, every new startup fails before command polling begins.
    No original command is rerun; local commits remain under a recovery ref.
    """
    markers=[ROOT/'.git'/'rebase-merge',ROOT/'.git'/'rebase-apply']
    if not any(p.exists() for p in markers):
        return False
    branch_head=git('rev-parse','refs/heads/main')
    git('update-ref','refs/asterion-recovery/aborted-'+branch_head[:16],branch_head)
    git('rebase','--abort')
    if any(p.exists() for p in markers):
        raise RuntimeError('Git rebase metadata still present after safe abort')
    return True


def _compact_unpublished_receipts():
    """Reconcile divergent receipt commits using the existing Git object store.

    Create the complete replacement tree and commit BEFORE moving the worktree.
    The original commit remains under a recovery ref. No external receipt
    directory, checkout, or backup repository is created.
    """
    original=git('rev-parse','HEAD')
    remote=git('rev-parse','origin/main')
    git('update-ref','refs/asterion-recovery/unpublished-'+original[:16],original)
    changes=sorted(set(p.strip() for p in
        git('log','--format=','--name-only',remote+'..'+original).splitlines()
        if p.strip()))
    if not changes or any(not p.startswith('results/') or
                          not p.endswith('.json') or
                          not NAME.fullmatch(Path(p).stem) for p in changes):
        raise RuntimeError('Unpublished non-receipt commit; refusing worktree reset')
    terminal={'complete','error','uncertain','failed','skipped'}
    restore={}
    for relative in changes:
        path=ROOT/relative
        if not path.is_file():
            raise RuntimeError('Unpublished receipt missing; refusing reset: '+relative)
        try:
            local=json.loads(path.read_bytes())
            if not isinstance(local,dict) or local.get('id')!=path.stem or not isinstance(local.get('status'),str):
                raise ValueError('Receipt id/status invalid')
        except (ValueError,TypeError,UnicodeDecodeError) as exc:
            raise RuntimeError('Invalid unpublished receipt; refusing reset: '+relative) from exc
        if git('ls-tree','-r','--name-only',remote,'--',relative)==relative:
            published=subprocess.run(['git','show',remote+':'+relative],
                              cwd=ROOT,check=True,capture_output=True,timeout=30).stdout
            try:
                existing=json.loads(published)
                if not isinstance(existing,dict) or existing.get('id')!=path.stem:
                    raise ValueError('Remote receipt identity mismatch')
            except (ValueError,UnicodeDecodeError) as exc:
                raise RuntimeError('Invalid remote receipt; refusing reset: '+relative) from exc
            if existing.get('status') in terminal or local['status'] not in terminal:
                continue
        restore[relative]=git('rev-parse',original+':'+relative)
    # Use one transient index INSIDE the existing Git metadata. Its contents
    # are reconstructable; an interrupted run leaves HEAD and receipts intact.
    index=Path(git('rev-parse','--absolute-git-dir'))/'asterion-reconcile-index'
    env=dict(os.environ,GIT_INDEX_FILE=str(index))
    try:
        index.unlink(missing_ok=True)
        index.with_name(index.name+'.lock').unlink(missing_ok=True)
        git('read-tree',remote,env=env)
        for relative,blob in restore.items():
            git('update-index','--add','--cacheinfo','100644,'+blob+','+relative,env=env)
        tree=git('write-tree',env=env)
        if tree==git('rev-parse',remote+'^{tree}'):
            replacement=remote
        else:
            replacement=git('-c','user.name=Asterion Control',
                '-c','user.email=asterion-control@users.noreply.github.com',
                'commit-tree',tree,'-p',remote,'-m','Reconcile preserved Control receipts',env=env)
        # Commit and original recovery ref are both durable before reset.
        git('reset','--hard',replacement)
    finally:
        index.unlink(missing_ok=True)
        index.with_name(index.name+'.lock').unlink(missing_ok=True)
    return len(restore)


def sync_remote():
    """Safely converge private bridge receipt history without conflicting rebases."""
    recover_interrupted_rebase()
    preserve_dirty_receipts()
    for attempt in range(10):
        git('fetch','--quiet','origin','main')
        unpublished=int(git('rev-list','--count','origin/main..HEAD'))
        if not unpublished:
            git('merge','--ff-only','origin/main')
            return
        # Even fast-forward publication must never upload arbitrary local files.
        changed=git('log','--format=','--name-only','origin/main..HEAD').splitlines()
        paths={p.strip() for p in changed if p.strip()}
        if not paths or any(not p.startswith('results/') or not p.endswith('.json') or
                            not NAME.fullmatch(Path(p).stem) for p in paths):
            raise RuntimeError('Unpublished non-receipt commit; refusing publication')
        # Normal publishing is a fast-forward. Only reconcile if another
        # project actually advanced the remote after our base snapshot.
        if int(git('rev-list','--count','HEAD..origin/main')):
            _compact_unpublished_receipts()
            if int(git('rev-list','--count','origin/main..HEAD'))==0:
                return
        try:
            git('push','--quiet','origin','HEAD:main')
            return
        except RuntimeError:
            if attempt==9:
                raise
            time.sleep(min(10,1+attempt))


def setup():
    ROOT.parent.mkdir(parents=True,exist_ok=True)
    if not (ROOT/'.git').exists():
        git('clone','--quiet','--depth','1','--single-branch',
            '--branch','main',URL,str(ROOT),timeout=120)
    remote=git('remote','get-url','origin').rstrip('/')
    if remote.lower()!=URL.lower():
        raise RuntimeError('Unexpected bridge remote: refusing to execute')
    sync_remote()

def publish(paths):
    """Publish receipts through the same conflict-safe convergence as startup.

    A direct git rebase here previously stranded the relay in rebase-merge
    whenever independent Asterion projects published competing receipts.
    Converge via the validated receipt-preserving algorithm instead; no
    command is executed a second time after a failed publication.
    """
    git('add','--',*[str(p) for p in paths])
    if not git('diff','--cached','--name-only'):
        return
    git('-c','user.name=Asterion Control','-c','user.email=asterion-control@users.noreply.github.com',
        'commit','--quiet','-m','Asterion Control private bridge results')
    sync_remote()

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
    # Do not use git(): it calls .strip(), which removes the first leading
    # status-column space in porcelain output. A single modified result then
    # becomes "M results/...", and slicing row[3:] silently drops the "r".
    # That strands a completed receipt after a failed publish/restart.
    probe=subprocess.run(
        ['git','status','--porcelain=v1','--untracked-files=all','--','results'],
        cwd=ROOT,text=True,capture_output=True,timeout=60,check=False)
    if probe.returncode:
        raise RuntimeError('Unable to inspect unpublished result receipts: '+
                           (probe.stderr or probe.stdout)[-300:])
    changes=probe.stdout
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
        # A modified local filename is not sufficient authorization to
        # publish a result. Require the exact immutable command identity and
        # known terminal status; never turn a malformed/unknown receipt into
        # apparent success or re-execute its originating phone operation.
        if not isinstance(receipt,dict) or receipt.get('id')!=candidate.stem:
            continue
        if receipt.get('status') not in ('complete','error','uncertain',
                                         'failed','skipped'):
            continue
        ready.append(candidate)
    if ready:
        publish(ready)
    return len(ready)

def pending_in(folder,recorded=None):
    """Return only unknown commands; never replay a recorded running/error receipt."""
    results=ROOT/'results'
    results.mkdir(exist_ok=True)
    if not folder.is_dir():return []
    # One directory enumeration rather than a separate filesystem existence
    # lookup for every historical command. Durable receipts still gate replay.
    if recorded is None:recorded={p.name for p in results.glob('*.json')}
    return [p for p in sorted(folder.glob('*.json'))
            if NAME.fullmatch(p.stem) and p.name not in recorded]

def entries():
    """Explicit active queue survives first-start legacy-command migration.

    An older REST relay may have left ambiguous root-level commands. New,
    explicitly authorized Control commands use commands/active and are never
    preemptively classified as a pre-migration replay.
    """
    commands=ROOT/'commands'
    chosen=[];seen=set()
    recorded={p.name for p in (ROOT/'results').glob('*.json')}
    for file in pending_in(commands/'active',recorded)+pending_in(commands,recorded):
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
    health('syncing',inflight_id=None)
    sync_remote()
    health('idle',last_sync_utc=_utc_now(),consecutive_errors=0,error_kind=None)
    tasks=entries()
    unfinished=outstanding_jobs()
    health('idle',pending_count=len(tasks)+len(unfinished))
    if tasks or unfinished:
        ensure_agent(key)
    # Already-durable previous results are publication-only, never replayed.
    recover_unpublished()
    # Coalesce finished historical jobs with new command results into a single
    # Git publication. A failed publication is still recovered on next sync.
    batch=reconcile_jobs(key,reconcile_slice(unfinished),publish_now=False) if unfinished else []
    reconciled=len(batch)
    processed=0
    for request in tasks[:12]:
        identity=request.stem
        health('processing',inflight_id=identity)
        # This receipt prevents replay after crashes but is not a success claim.
        if not write_result(identity,{'id':identity,'ok':False,'status':'running'},publish_now=False):
            # Even an unexpectedly discovered receipt must suppress dispatch.
            health('idle',inflight_id=None)
            continue
        started=time.monotonic()
        try:
            task=json.loads(request.read_text('utf8'))
            if task.get('id')!=identity or not isinstance(task.get('op'),str):
                raise ValueError('Invalid request identity')
            response=run(task,key)
            asynchronous=task['op'] in ('pc_command','phone_transfer_start')
            expected='queued' if task['op']=='phone_transfer_start' else 'running'
            accepted=(asynchronous and isinstance(response,dict)
                and response.get('status')==expected
                and isinstance(response.get('id'),str)
                and len(response['id'])==32)
            if asynchronous and not accepted:
                reply={'id':identity,'ok':False,'status':'uncertain',
                       'error':'No durable asynchronous job id from native Control',
                       'result':response}
            else:
                reply={'id':identity,'ok':True,
                       'status':'accepted' if accepted else 'complete',
                       'result':response}
            if accepted and task['op']=='phone_transfer_start':
                reply['operation']='phone_transfer_start'
            reply['elapsed_ms']=round((time.monotonic()-started)*1000)
        except urllib.error.HTTPError as exc:
            reply={'id':identity,'ok':False,'status':'error',
                   'elapsed_ms':round((time.monotonic()-started)*1000),
                   'error':'Native Control HTTP '+str(exc.code),'http_status':exc.code}
            if exc.code==429:
                # The native capacity check happens before starting the job.
                # Explicit rejection is not an ambiguous transfer or outage.
                reply['retryable']=True
                reply['error_code']='native_capacity_rejected'
        except Exception as exc:
            reply={'id':identity,'ok':False,'status':'error',
                   'elapsed_ms':round((time.monotonic()-started)*1000),
                   'error':str(exc)[:500]}
        write_result(identity,reply,publish_now=False)
        health('idle',inflight_id=None)
        batch.append(Path('results')/(identity+'.json'))
        processed+=1
        print('Asterion Control',identity,reply['status'],flush=True)
    if batch:
        health('publishing',inflight_id=None)
        publish(batch)
        health('idle',last_publish_utc=_utc_now(),
               pending_count=max(0,len(tasks)+len(unfinished)-processed-reconciled),inflight_id=None)
    return processed

def _run_owned_worker():
    health('starting')
    try:
        health('setup')
        setup()
        migrate()
        secret=local_token()
    except Exception as exc:
        health('startup_error',error_kind=type(exc).__name__)
        # Keep a durable owner-local startup traceback; the Windows launcher
        # reopens stdout/stderr on each retry, erasing previous crash output.
        # Never log tokens, command payloads or phone screenshots.
        try:
            import traceback
            error_file=HEALTH.parent/'control-git-bridge-startup-last-error.log'
            with error_file.open('w',encoding='utf8') as stream:
                stream.write(traceback.format_exc()[-6000:])
        except OSError:
            pass
        raise
    print('Asterion Control private Git transport active; no REST quota',flush=True)
    failures=0
    while True:
        try:
            processed=cycle(secret)
            failures=0
            # A short command burst keeps interactive control responsive.
            time.sleep(2 if processed else 3)
        except KeyboardInterrupt:
            health('idle',inflight_id=None)
            return
        except Exception as exc:
            failures+=1
            # Preserve the current inflight_id when an operation is uncertain:
            # the watchdog must never restart/replay a side effect blindly.
            health('retrying',consecutive_errors=failures,
                   error_kind=type(exc).__name__)
            print('Bridge retry:',type(exc).__name__,str(exc)[:180],flush=True)
            time.sleep(min(45,failures*5))

def main():
    try:
        with worker_process_lock(WORKER_LOCK):
            _run_owned_worker()
    except WorkerAlreadyRunning:
        # Never overwrite the real owner's heartbeat or result journal.
        print('Asterion Control relay already owns the queue; duplicate refused',flush=True)

if __name__=='__main__':main()

