"""Asterion Control: standalone Windows + connected Android REST API and PWA.

Not affiliated with, or dependent on, Desktop Commander.
For devices owned by the operator or explicitly authorized for remote access.
"""
from __future__ import annotations

import io
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .security import configured_token, require_token
from .native_routes import router as phone_router
from .recovery import router as recovery_router
from .pairing import router as pairing_router, start_discovery, stop_discovery, create_code
from .live_stream import install_stream
from .control_services import ScriptRun, BatchRequest, script_command, script_list, host_health

ROOT = Path(os.getenv('ASTERION_REMOTE_ROOT', str(Path.home()))).expanduser().resolve()
EXTRA_ROOTS = [Path(x).expanduser().resolve() for x in os.getenv('ASTERION_ALLOWED_ROOTS', '').split(os.pathsep) if x.strip()]
RUNTIME = Path(os.getenv('ASTERION_REMOTE_RUNTIME', str(Path.home() / '.asterion-remote'))).expanduser()
ALLOW_SHELL = os.getenv('ASTERION_ALLOW_SHELL', '0') == '1'
ALLOW_ADB_SHELL = os.getenv('ASTERION_ALLOW_ANDROID_SHELL', '0') == '1'
ADB_EXE = os.getenv('ASTERION_ADB', 'adb')
MAX_READ = 2_000_000
MAX_UPLOAD = int(os.getenv('ASTERION_UPLOAD_LIMIT_BYTES', '0'))  # 0 disables size limit; streamed to disk
COMMAND_LOCK = Lock()
COMMANDS: dict[str, dict] = {}
STATIC = Path(__file__).parent / 'static'

app = FastAPI(title='Asterion Control', version='0.8.0', docs_url='/docs', redoc_url=None)
app.mount('/static', StaticFiles(directory=STATIC), name='static')
app.include_router(phone_router)
app.include_router(recovery_router)
app.include_router(pairing_router)


@app.on_event('startup')
def check_config():
    configured_token()
    if os.getenv('ASTERION_ENABLE_DISCOVERY') == '1':
        create_code()
        start_discovery()
    if not ROOT.is_dir():
        raise RuntimeError(f'ASTERION_REMOTE_ROOT not a directory: {ROOT}')


def safe_path(value: str) -> Path:
    p = Path(value).expanduser()
    resolved = (p if p.is_absolute() else ROOT / p).resolve()
    if not any(resolved.is_relative_to(root) for root in [ROOT, *EXTRA_ROOTS]):
        raise HTTPException(403, 'Path outside configured roots')
    return resolved


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def api_error(e: Exception, feature: str) -> HTTPException:
    return HTTPException(503, f'{feature} unavailable: {type(e).__name__}')


def run_external(args: list[str], timeout: int = 20, raw: bool = False):
    try:
        cp = subprocess.run(args, capture_output=True, timeout=timeout, check=False,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as exc:
        raise HTTPException(503, detail=f'Tool unavailable or timed out: {type(exc).__name__}') from exc
    if cp.returncode:
        detail = cp.stderr.decode('utf-8', 'replace')[-1200:] or cp.stdout.decode('utf-8', 'replace')[-1200:]
        raise HTTPException(502, detail=f'Command failed ({cp.returncode}): {detail}')
    return cp.stdout if raw else cp.stdout.decode('utf-8', errors='replace')


@app.get('/')
def home():
    return FileResponse(STATIC / 'index.html', headers={'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy':
        "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})


@app.get('/manifest.webmanifest')
def manifest():
    return FileResponse(STATIC / 'manifest.webmanifest', media_type='application/manifest+json')


@app.get('/api/v1/discovery')
def private_discovery(request: Request):
    # Return no credentials, file listings or system paths.
    from .pairing import private_peer
    if not request.client or not private_peer(request.client.host):
        raise HTTPException(403, 'Discovery requires a private LAN or VPN peer')
    return {'service':'asterion-control','version':1,'port':8911,'name':platform.node()}


@app.get('/api/v1/health', dependencies=[Depends(require_token)])
def health():
    return {'ok': True, 'app': 'Asterion Control', 'version': '0.8.0', 'os': platform.system(),
            'host': platform.node(), 'root': str(ROOT), 'shell': ALLOW_SHELL,
            'android_shell': ALLOW_ADB_SHELL,
            'capabilities': ['files', 'commands', 'processes', 'system', 'desktop_screen',
                             'desktop_input', 'android_adb', 'android_screen', 'android_input', 'native_android_agent', 'live_websocket_stream']}


@app.get('/api/v1/system', dependencies=[Depends(require_token)])
def system():
    try:
        import psutil
        p = psutil.virtual_memory()
        drives = []
        for disk in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(disk.mountpoint)
                drives.append({'mount': disk.mountpoint, 'total': usage.total, 'free': usage.free})
            except (OSError, PermissionError):
                pass
        return {'host': platform.node(), 'os': platform.platform(), 'cpu_percent': psutil.cpu_percent(interval=None),
                'memory': {'total': p.total, 'available': p.available, 'percent': p.percent},
                'disks': drives, 'uptime': int(time.time() - psutil.boot_time())}
    except ImportError:
        raise HTTPException(503, 'Install psutil for system monitoring')


@app.get('/api/v1/processes', dependencies=[Depends(require_token)])
def processes(limit: int = Query(100, ge=1, le=500)):
    try:
        import psutil
        rows = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status']):
            try:
                v = proc.info
                rows.append({'pid': v['pid'], 'name': v['name'], 'cpu': v['cpu_percent'],
                             'memory': v['memory_info'].rss if v['memory_info'] else 0,
                             'status': v['status']})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        rows.sort(key=lambda x: x['memory'], reverse=True)
        return {'items': rows[:limit], 'total': len(rows)}
    except ImportError:
        raise HTTPException(503, 'Install psutil for process management')


@app.post('/api/v1/processes/{pid}/terminate', dependencies=[Depends(require_token)])
def terminate_process(pid: int):
    if pid <= 1 or pid == os.getpid():
        raise HTTPException(403, 'Cannot terminate protected server PID')
    try:
        import psutil
        proc = psutil.Process(pid)
        proc.terminate()
        return {'ok': True, 'pid': pid}
    except psutil.NoSuchProcess:
        raise HTTPException(404, 'Process not found')
    except psutil.AccessDenied:
        raise HTTPException(403, 'OS denied process termination')


@app.get('/api/v1/files', dependencies=[Depends(require_token)])
def list_files(path: str = '.'):
    p = safe_path(path)
    if not p.is_dir():
        raise HTTPException(404, 'Directory not found')
    items = []
    try:
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))[:1000]:
            resolved = entry.resolve()
            if not any(resolved.is_relative_to(root) for root in [ROOT, *EXTRA_ROOTS]):
                continue
            items.append({'name': entry.name, 'path': relative(resolved), 'directory': entry.is_dir(),
                          'size': entry.stat().st_size if entry.is_file() else None})
    except PermissionError:
        raise HTTPException(403, 'Directory access denied')
    return {'path': relative(p), 'items': items}


@app.get('/api/v1/files/read', dependencies=[Depends(require_token)])
def read_file(path: str):
    p = safe_path(path)
    if not p.is_file():
        raise HTTPException(404, 'File not found')
    if p.stat().st_size > MAX_READ:
        raise HTTPException(413, 'Text file exceeds 2 MB')
    try:
        return {'path': relative(p), 'content': p.read_text('utf-8')}
    except (UnicodeError, PermissionError):
        raise HTTPException(422, 'Cannot read file as UTF-8')


@app.get('/api/v1/files/download', dependencies=[Depends(require_token)])
def download_file(path: str):
    p = safe_path(path)
    if not p.is_file():
        raise HTTPException(404, 'File not found')
    return FileResponse(p, filename=p.name, headers={'Cache-Control': 'no-store'})


class FileWrite(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field(max_length=MAX_READ)
    overwrite: bool = False


@app.put('/api/v1/files/write', dependencies=[Depends(require_token)])
def write_file(data: FileWrite):
    p = safe_path(data.path)
    if not p.parent.is_dir():
        raise HTTPException(404, 'Parent directory missing')
    if p.exists() and (not data.overwrite or not p.is_file()):
        raise HTTPException(409, 'Exists, set overwrite=true for file')
    try:
        p.write_text(data.content, encoding='utf-8') if data.overwrite else _exclusive_write(p, data.content)
    except FileExistsError:
        raise HTTPException(409, 'File already exists')
    return {'ok': True, 'path': relative(p)}


def _exclusive_write(p: Path, content: str):
    with p.open('x', encoding='utf-8') as f:
        f.write(content)


class PathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


@app.post('/api/v1/files/mkdir', dependencies=[Depends(require_token)])
def make_directory(data: PathRequest):
    p = safe_path(data.path)
    p.mkdir(parents=True, exist_ok=True)
    return {'ok': True, 'path': relative(p)}


class MoveRequest(BaseModel):
    source: str
    destination: str


@app.post('/api/v1/files/move', dependencies=[Depends(require_token)])
def move_file(data: MoveRequest):
    src, dest = safe_path(data.source), safe_path(data.destination)
    if not src.exists():
        raise HTTPException(404, 'Source not found')
    if dest.exists():
        raise HTTPException(409, 'Destination exists')
    if not dest.parent.is_dir():
        raise HTTPException(404, 'Destination parent missing')
    src.rename(dest)
    return {'ok': True, 'path': relative(dest)}


@app.delete('/api/v1/files', dependencies=[Depends(require_token)])
def remove_file(path: str):
    p = safe_path(path)
    if p == ROOT or not p.exists():
        raise HTTPException(403, 'Cannot delete root or missing path')
    if p.is_dir():
        p.rmdir()  # nonempty directories intentionally cannot be deleted recursively
    else:
        p.unlink()
    return {'ok': True}


@app.put('/api/v1/files/upload', dependencies=[Depends(require_token)])
async def upload_file(request: Request, path: str, overwrite: bool = False):
    p = safe_path(path)
    if not p.parent.is_dir():
        raise HTTPException(404, 'Parent directory missing')
    if p.exists() and not overwrite:
        raise HTTPException(409, 'Destination exists')
    size = 0
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=p.parent) as f:
            tmp = Path(f.name)
            async for chunk in request.stream():
                size += len(chunk)
                if MAX_UPLOAD and size > MAX_UPLOAD:
                    raise HTTPException(413, 'Configured upload size limit exceeded')
                f.write(chunk)
        if p.exists() and p.is_dir():
            raise HTTPException(409, 'Destination is a directory')
        if not overwrite and p.exists():
            raise HTTPException(409, 'Destination appeared during upload')
        tmp.replace(p)
        return {'ok': True, 'path': relative(p), 'bytes': size}
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


@app.get('/api/v1/files/search', dependencies=[Depends(require_token)])
def search_files(q: str = Query(min_length=1, max_length=120), path: str = '.', limit: int = Query(100, ge=1, le=500)):
    base = safe_path(path)
    if not base.is_dir():
        raise HTTPException(404, 'Directory not found')
    hits = []
    scanned = 0
    for directory, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if any((Path(directory) / d).resolve().is_relative_to(root) for root in [ROOT, *EXTRA_ROOTS])]
        for name in dirs + files:
            scanned += 1
            if q.casefold() in name.casefold():
                entry = (Path(directory) / name).resolve()
                if any(entry.is_relative_to(root) for root in [ROOT, *EXTRA_ROOTS]):
                    hits.append({'path': relative(entry), 'directory': entry.is_dir()})
                    if len(hits) >= limit:
                        break
        if len(hits) >= limit or scanned >= 50000:
            break
    return {'items': hits, 'scanned': scanned, 'truncated': len(hits) >= limit or scanned >= 50000}


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    cwd: str = '.'


@app.post('/api/v1/commands', dependencies=[Depends(require_token)])
def launch_command(data: CommandRequest):
    if not ALLOW_SHELL:
        raise HTTPException(403, 'Shell disabled: set ASTERION_ALLOW_SHELL=1')
    cwd = safe_path(data.cwd)
    if not cwd.is_dir():
        raise HTTPException(404, 'Working directory not found')
    with COMMAND_LOCK:
        if sum(1 for row in COMMANDS.values() if row['proc'].poll() is None) >= 4:
            raise HTTPException(429, 'Maximum four active shell jobs')
        jobid = uuid.uuid4().hex
        logs = RUNTIME / 'processes'
        logs.mkdir(parents=True, exist_ok=True)
        logfile = logs / f'{jobid}.log'
        with logfile.open('wb') as out:
            proc = subprocess.Popen(data.command, shell=True, cwd=cwd, stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=os.name != 'nt',
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        COMMANDS[jobid] = {'proc': proc, 'log': logfile, 'started': time.time()}
    return {'id': jobid, 'pid': proc.pid, 'status': 'running'}


@app.get('/api/v1/commands', dependencies=[Depends(require_token)])
def list_commands():
    with COMMAND_LOCK:
        return {'items': [{'id': k, 'pid': v['proc'].pid,
                           'status': 'running' if v['proc'].poll() is None else 'finished'}
                          for k, v in COMMANDS.items()]}


@app.get('/api/v1/commands/{jobid}', dependencies=[Depends(require_token)])
def command_status(jobid: str):
    with COMMAND_LOCK:
        row = COMMANDS.get(jobid)
    if not row:
        raise HTTPException(404, 'Unknown job')
    proc, log = row['proc'], row['log']
    with log.open('rb') as f:
        f.seek(max(0, log.stat().st_size - 64000))
        output = f.read().decode('utf-8', 'replace')
    return {'id': jobid, 'pid': proc.pid, 'status': 'running' if proc.poll() is None else 'finished',
            'exit_code': proc.poll(), 'output': output}


@app.post('/api/v1/commands/{jobid}/stop', dependencies=[Depends(require_token)])
def stop_command(jobid: str):
    with COMMAND_LOCK:
        row = COMMANDS.get(jobid)
    if not row:
        raise HTTPException(404, 'Unknown job')
    if row['proc'].poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(row['proc'].pid), '/T', '/F'],
                           capture_output=True, timeout=10,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            import signal
            os.killpg(row['proc'].pid, signal.SIGTERM)
    return {'ok': True}



# Internal-facing operations. These routes are deliberately not presented in
# the normal phone UI. Both endpoints require the same authorized bearer token.
@app.get('/api/v1/internal/scripts', dependencies=[Depends(require_token)])
def internal_scripts():
    return {'items': script_list()}


@app.post('/api/v1/internal/scripts/run', dependencies=[Depends(require_token)])
def run_saved_script(data: ScriptRun):
    if not ALLOW_SHELL:
        raise HTTPException(403, 'Shell disabled: set ASTERION_ALLOW_SHELL=1')
    cwd = safe_path(data.cwd)
    if not cwd.is_dir():
        raise HTTPException(404, 'Working directory not found')
    return _launch_argv(script_command(data.script_id, data.arguments), cwd)


@app.post('/api/v1/internal/scripts/batch', dependencies=[Depends(require_token)])
def run_saved_scripts(data: BatchRequest):
    if not ALLOW_SHELL:
        raise HTTPException(403, 'Shell disabled: set ASTERION_ALLOW_SHELL=1')
    # The existing process limit is deliberately respected. Sequence mode
    # is an explicit chain of batch jobs, not an implicit autonomous agent.
    if data.mode == 'parallel' and len(data.jobs) > 4:
        raise HTTPException(422, 'At most four simultaneous jobs supported')
    cmds = []
    for job in data.jobs:
        cwd = safe_path(job.cwd)
        if not cwd.is_dir():
            raise HTTPException(404, 'Working directory not found')
        cmds.append((script_command(job.script_id, job.arguments), cwd))
    if data.mode == 'sequential':
        # For durable unattended chaining, use a single explicitly-authored
        # Python script; sequential service orchestration is not yet implemented.
        raise HTTPException(501, 'Sequential batches not implemented; use a saved wrapper script')
    return {'jobs': [_launch_argv(argv, cwd) for argv,cwd in cmds]}


def _launch_argv(argv: list[str], cwd: Path) -> dict:
    with COMMAND_LOCK:
        if sum(1 for row in COMMANDS.values() if row['proc'].poll() is None) >= 4:
            raise HTTPException(429, 'Maximum four active shell jobs')
        jobid = uuid.uuid4().hex
        logs = RUNTIME / 'processes'
        logs.mkdir(parents=True, exist_ok=True)
        logfile = logs / f'{jobid}.log'
        with logfile.open('wb') as out:
            proc = subprocess.Popen(argv, shell=False, cwd=cwd, stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=os.name != 'nt',
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        COMMANDS[jobid] = {'proc': proc, 'log': logfile, 'started': time.time(), 'argv': argv}
    return {'id': jobid, 'pid': proc.pid, 'status': 'running'}


# Real Windows performance actions only touch jobs launched and tracked by Control.
# Arbitrary user processes, system services and foreground games are never killed.
class ManagedJobPriority(BaseModel):
    mode: Literal['favor_foreground','restore']


@app.get('/api/v1/performance/jobs', dependencies=[Depends(require_token)])
def managed_performance_status():
    rows = []
    with COMMAND_LOCK:
        for key, item in COMMANDS.items():
            proc = item['proc']
            if proc.poll() is None:
                rows.append({
                    'id': key, 'pid': proc.pid, 'running': True,
                    'priority_reduced_by_control': '_perf_saved_priority' in item
                })
    return {
        'ok': True, 'managed_jobs_running': len(rows), 'jobs': rows,
        'adjustment_supported': os.name == 'nt',
        'scope': 'control_started_jobs_only', 'unrelated_apps_changed': False
    }


@app.post('/api/v1/performance/jobs', dependencies=[Depends(require_token)])
def manage_performance_priority(data: ManagedJobPriority):
    if os.name != 'nt':
        raise HTTPException(503, 'Job priority adjustment is available only on Windows')
    try:
        import psutil
    except ImportError as exc:
        raise HTTPException(503, 'psutil is required for process priority control') from exc
    applied, skipped = [], []
    with COMMAND_LOCK:
        for key, item in COMMANDS.items():
            proc = item['proc']
            if proc.poll() is not None:
                continue
            try:
                target = psutil.Process(proc.pid)
                current = target.nice()
                if data.mode == 'favor_foreground':
                    if '_perf_saved_priority' not in item:
                        if current == psutil.BELOW_NORMAL_PRIORITY_CLASS:
                            skipped.append({'id': key, 'reason': 'already_lowered'})
                            continue
                        target.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                        item['_perf_saved_priority'] = current
                        applied.append({'id': key, 'pid': proc.pid, 'action': 'lowered'})
                    else:
                        skipped.append({'id': key, 'reason': 'already_managed'})
                elif '_perf_saved_priority' in item:
                    # Do not override a subsequent owner/manual change.
                    if current != psutil.BELOW_NORMAL_PRIORITY_CLASS:
                        skipped.append({'id': key, 'reason': 'priority_changed_elsewhere'})
                        continue
                    target.nice(item['_perf_saved_priority'])
                    del item['_perf_saved_priority']
                    applied.append({'id': key, 'pid': proc.pid, 'action': 'restored'})
                else:
                    skipped.append({'id': key, 'reason': 'not_managed'})
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                skipped.append({'id': key, 'reason': type(exc).__name__})
    return {
        'ok': True, 'mode': data.mode,
        'applied': applied, 'skipped': skipped,
        'scope': 'control_started_jobs_only',
        'unrelated_apps_changed': False
    }


@app.get('/api/v1/device-health', dependencies=[Depends(require_token)])
def device_health():
    return host_health()

@app.get('/api/v1/screen', dependencies=[Depends(require_token)])
def screenshot(monitor: int = Query(1, ge=0, le=16), quality: int = Query(75, ge=25, le=95)):
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            if monitor >= len(sct.monitors):
                raise HTTPException(422, 'Monitor does not exist')
            shot = sct.grab(sct.monitors[monitor])
            im = Image.frombytes('RGB', shot.size, shot.rgb)
            buffer = io.BytesIO()
            im.save(buffer, format='JPEG', quality=quality)
        return Response(buffer.getvalue(), media_type='image/jpeg', headers={'Cache-Control': 'no-store'})
    except HTTPException:
        raise
    except Exception as exc:
        raise api_error(exc, 'Desktop screen capture')


@app.get('/api/v1/monitors', dependencies=[Depends(require_token)])
def monitors():
    try:
        import mss
        with mss.mss() as sct:
            return {'items': [{'index': i, 'left': m['left'], 'top': m['top'],
                               'width': m['width'], 'height': m['height']}
                              for i,m in enumerate(sct.monitors)]}
    except Exception as exc:
        raise api_error(exc, 'Monitor enumeration')


class DesktopInput(BaseModel):
    action: Literal['click', 'double_click', 'right_click', 'move', 'drag', 'scroll',
                    'type', 'hotkey', 'press', 'mouse_down', 'mouse_up']
    monitor: int = Field(default=1, ge=0, le=16)
    x: int = 0
    y: int = 0
    to_x: int = 0
    to_y: int = 0
    seconds: float = Field(default=0.4, ge=0, le=5)
    amount: int = Field(default=0, ge=-100, le=100)
    text: str = Field(default='', max_length=2000)
    keys: list[str] = Field(default_factory=list, max_length=6)


@app.post('/api/v1/input', dependencies=[Depends(require_token)])
def desktop_input(data: DesktopInput):
    try:
        import pyautogui as pg
        pg.FAILSAFE = True  # mouse upper-left corner aborts
        offset_x=offset_y=0
        if data.action in ('click','double_click','right_click','move','drag','mouse_down','mouse_up'):
            import mss
            with mss.mss() as sct:
                if data.monitor >= len(sct.monitors):
                    raise HTTPException(422, 'Monitor does not exist')
                offset_x=sct.monitors[data.monitor]['left']
                offset_y=sct.monitors[data.monitor]['top']
        x,y=data.x+offset_x,data.y+offset_y
        to_x,to_y=data.to_x+offset_x,data.to_y+offset_y
        if data.action in ('click', 'double_click', 'right_click', 'move', 'drag', 'mouse_down', 'mouse_up'):
            if data.x < 0 or data.y < 0 or data.to_x < 0 or data.to_y < 0:
                raise HTTPException(422, 'Negative screen coordinate')
            if data.action == 'click': pg.click(x, y)
            elif data.action == 'double_click': pg.doubleClick(x, y)
            elif data.action == 'right_click': pg.click(x, y, button='right')
            elif data.action == 'move': pg.moveTo(x, y)
            elif data.action == 'drag': pg.moveTo(x, y); pg.dragTo(to_x, to_y, duration=data.seconds)
            elif data.action == 'mouse_down': pg.mouseDown(x, y)
            elif data.action == 'mouse_up': pg.mouseUp(x, y)
        elif data.action == 'scroll': pg.scroll(data.amount)
        elif data.action == 'type': pg.write(data.text, interval=0.005)
        elif data.action in ('press', 'hotkey'):
            if not data.keys or any(not re.fullmatch(r'[a-zA-Z0-9_]+', k) for k in data.keys):
                raise HTTPException(422, 'Invalid key name')
            if data.action == 'press': pg.press(data.keys[0])
            else: pg.hotkey(*data.keys)
        return {'ok': True}
    except HTTPException:
        raise
    except Exception as exc:
        raise api_error(exc, 'Desktop input')


# Android requires a trusted ADB pairing with the user's device; never bypass Android authorization.
SERIAL_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9:._-]{0,127}$')


def adb(serial: str | None, *args: str, timeout: int = 20, raw: bool = False):
    cmd = [ADB_EXE]
    if serial:
        if not SERIAL_RE.fullmatch(serial):
            raise HTTPException(422, 'Invalid Android device ID')
        cmd.extend(['-s', serial])
    cmd.extend(args)
    return run_external(cmd, timeout, raw)


@app.get('/api/v1/android/devices', dependencies=[Depends(require_token)])
def android_devices():
    data = adb(None, 'devices', '-l')
    devices = []
    for line in data.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            devices.append({'serial': parts[0], 'state': parts[1], 'description': ' '.join(parts[2:])})
    return {'items': devices}


class WifiTarget(BaseModel):
    address: str = Field(min_length=3, max_length=255)


def validate_adb_target(addr: str):
    # ADB accepts private-IP or host:port endpoints; no shell or whitespace.
    if not re.fullmatch(r'[A-Za-z0-9.:-]+', addr) or addr.startswith('-'):
        raise HTTPException(422, 'Invalid wireless ADB address')


@app.post('/api/v1/android/connect', dependencies=[Depends(require_token)])
def connect_android(data: WifiTarget):
    validate_adb_target(data.address)
    return {'output': adb(None, 'connect', data.address, timeout=30)}


class PairTarget(WifiTarget):
    code: str = Field(min_length=6, max_length=12, pattern=r'^[0-9]+$')


@app.post('/api/v1/android/pair', dependencies=[Depends(require_token)])
def pair_android(data: PairTarget):
    validate_adb_target(data.address)
    return {'output': adb(None, 'pair', data.address, data.code, timeout=30)}


@app.get('/api/v1/android/{serial}/info', dependencies=[Depends(require_token)])
def android_info(serial: str):
    model = adb(serial, 'shell', 'getprop', 'ro.product.model').strip()
    version = adb(serial, 'shell', 'getprop', 'ro.build.version.release').strip()
    battery = adb(serial, 'shell', 'dumpsys', 'battery', timeout=15)[-2000:]
    dimensions = adb(serial, 'shell', 'wm', 'size').strip()
    return {'serial': serial, 'model': model, 'android_version': version,
            'size': dimensions, 'battery': battery}


@app.get('/api/v1/android/{serial}/screen', dependencies=[Depends(require_token)])
def android_screen(serial: str):
    png = adb(serial, 'exec-out', 'screencap', '-p', timeout=20, raw=True)
    if not png.startswith(b'\x89PNG\r\n\x1a\n'):
        raise HTTPException(502, 'Device did not return a PNG screenshot')
    return Response(png, media_type='image/png', headers={'Cache-Control': 'no-store'})


class AndroidInput(BaseModel):
    action: Literal['tap', 'swipe', 'key', 'text', 'long_press']
    x: int = Field(default=0, ge=0, le=10000)
    y: int = Field(default=0, ge=0, le=10000)
    to_x: int = Field(default=0, ge=0, le=10000)
    to_y: int = Field(default=0, ge=0, le=10000)
    duration_ms: int = Field(default=400, ge=100, le=10000)
    key: str = Field(default='KEYCODE_BACK', max_length=60)
    text: str = Field(default='', max_length=1000)


@app.post('/api/v1/android/{serial}/input', dependencies=[Depends(require_token)])
def android_input(serial: str, data: AndroidInput):
    if data.action == 'tap':
        args = ['shell', 'input', 'tap', str(data.x), str(data.y)]
    elif data.action == 'long_press':
        args = ['shell', 'input', 'swipe', str(data.x), str(data.y), str(data.x), str(data.y), str(data.duration_ms)]
    elif data.action == 'swipe':
        args = ['shell', 'input', 'swipe', str(data.x), str(data.y), str(data.to_x), str(data.to_y), str(data.duration_ms)]
    elif data.action == 'key':
        if not re.fullmatch(r'(KEYCODE_[A-Z0-9_]+|[0-9]{1,3})', data.key):
            raise HTTPException(422, 'Invalid Android key code')
        args = ['shell', 'input', 'keyevent', data.key]
    else:
        if any(ord(c) < 32 or ord(c) > 126 for c in data.text):
            raise HTTPException(422, 'ADB input text supports ASCII only; use clipboard/IME for Unicode')
        # ADB input text treats %s as spaces. Escape shell metacharacters by passing
        # a single shell-quoted string to the Android shell.
        import shlex
        escaped = data.text.replace('%', '%25').replace(' ', '%s')
        args = ['shell', f'input text {shlex.quote(escaped)}']
    adb(serial, *args)
    return {'ok': True}


@app.get('/api/v1/android/{serial}/packages', dependencies=[Depends(require_token)])
def android_packages(serial: str, q: str = ''):
    output = adb(serial, 'shell', 'pm', 'list', 'packages', timeout=35)
    packages = [line.removeprefix('package:').strip() for line in output.splitlines() if line.startswith('package:')]
    return {'items': [p for p in packages if q.casefold() in p.casefold()][:3000], 'total': len(packages)}


class LaunchApp(BaseModel):
    package: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_.]{2,199}$')


@app.post('/api/v1/android/{serial}/launch', dependencies=[Depends(require_token)])
def launch_android_app(serial: str, data: LaunchApp):
    adb(serial, 'shell', 'monkey', '-p', data.package, '-c', 'android.intent.category.LAUNCHER', '1')
    return {'ok': True}


@app.get('/api/v1/android/{serial}/ui', dependencies=[Depends(require_token)])
def android_ui_hierarchy(serial: str):
    # User has authorized USB debugging, so UIAutomator can inspect the active screen.
    adb(serial, 'shell', 'uiautomator', 'dump', '/sdcard/window.xml', timeout=35)
    xml = adb(serial, 'exec-out', 'cat', '/sdcard/window.xml', timeout=20)
    return Response(xml, media_type='application/xml')


class AndroidShell(BaseModel):
    command: str = Field(min_length=1, max_length=2000)


@app.post('/api/v1/android/{serial}/shell', dependencies=[Depends(require_token)])
def android_shell(serial: str, data: AndroidShell):
    if not ALLOW_ADB_SHELL:
        raise HTTPException(403, 'Android shell disabled: set ASTERION_ALLOW_ANDROID_SHELL=1')
    out = adb(serial, 'shell', data.command, timeout=30)
    return {'output': out[-64000:]}


class AndroidTransfer(BaseModel):
    pc_path: str = Field(min_length=1, max_length=4096)
    android_path: str = Field(min_length=1, max_length=4096)


def check_android_path(p: str):
    if '\x00' in p or '\r' in p or '\n' in p or not p.startswith('/'):
        raise HTTPException(422, 'Android path must be absolute')


@app.post('/api/v1/android/{serial}/push', dependencies=[Depends(require_token)])
def android_push(serial: str, data: AndroidTransfer):
    pc_path = safe_path(data.pc_path)
    if not pc_path.is_file():
        raise HTTPException(404, 'Local file not found')
    check_android_path(data.android_path)
    result = adb(serial, 'push', str(pc_path), data.android_path, timeout=120)
    return {'ok': True, 'output': result[-1200:]}


@app.post('/api/v1/android/{serial}/pull', dependencies=[Depends(require_token)])
def android_pull(serial: str, data: AndroidTransfer):
    pc_path = safe_path(data.pc_path)
    if pc_path.exists():
        raise HTTPException(409, 'Destination already exists')
    if not pc_path.parent.is_dir():
        raise HTTPException(404, 'Parent directory missing')
    check_android_path(data.android_path)
    result = adb(serial, 'pull', data.android_path, str(pc_path), timeout=120)
    return {'ok': True, 'output': result[-1200:]}


class AndroidInstall(BaseModel):
    pc_apk: str


@app.post('/api/v1/android/{serial}/install', dependencies=[Depends(require_token)])
def android_install(serial: str, data: AndroidInstall):
    p = safe_path(data.pc_apk)
    if not p.is_file() or p.suffix.lower() != '.apk':
        raise HTTPException(422, 'A valid .apk inside the root is required')
    result = adb(serial, 'install', '-r', str(p), timeout=120)
    return {'ok': True, 'output': result[-1200:]}


# Authenticated continuous frame transport: one WebSocket handshake, not repeated screenshot requests.
def _desktop_jpeg(monitor: int):
    return screenshot(monitor=monitor,quality=67).body

def _desktop_ws_input(payload: dict):
    return desktop_input(DesktopInput(**payload))

install_stream(app, _desktop_jpeg, _desktop_ws_input)

@app.on_event('shutdown')
def stop_lan_discovery():
    stop_discovery()
