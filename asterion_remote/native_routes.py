"""Read-only phone telemetry and explicit input proxy over private network/VPN."""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from .security import require_token
from .phone_bridge import PairPhone, PhoneInput, register, request, load
from .native_transfer import TransferRequest, start_transfer, transfer_status, cancel_transfer

router = APIRouter(prefix='/api/v1', dependencies=[Depends(require_token)])

@router.post('/phone/register')
def register_phone(data:PairPhone): return register(data)

@router.get('/phone')
def phone_status():
    pairing=load()
    if not pairing: return {'paired':False}
    try:
        h=request('/health').json()
        return {'paired':True,'reachable':True,'device':pairing['device'],'info':h}
    except Exception:
        return {'paired':True,'reachable':False,'device':pairing['device']}

@router.get('/phone/health')
def phone_health():return request('/health').json()

@router.get('/phone/ui')
def phone_ui():return request('/ui').json()

@router.post('/phone/input')
def phone_input(data:PhoneInput):return request('/input','POST',data.model_dump(exclude_none=True)).json()

@router.get('/phone/screen')
def phone_screen():return Response(request('/screen').content,media_type='image/jpeg',headers={'Cache-Control':'no-store'})

# Direct private-Wi-Fi file transfer. Source paths are confined to the authorized PC root.
@router.post('/phone/transfers')
def submit_phone_transfer(data: TransferRequest):
    from .app import safe_path
    return start_transfer(data,safe_path)

@router.get('/phone/transfers/{key}')
def phone_transfer_status(key: str):
    return transfer_status(key)

@router.post('/phone/transfers/{key}/cancel')
def phone_transfer_cancel(key: str):
    return cancel_transfer(key)

# A session executes explicitly authorized UI steps locally without a ChatGPT turn per gesture.
from .interaction_sessions import SessionRequest, start as start_session, status as session_status, cancel as cancel_session

@router.post('/sessions')
def submit_control_session(data: SessionRequest):
    return start_session(data)

@router.get('/sessions/{key}')
def get_control_session(key: str):
    return session_status(key)

@router.post('/sessions/{key}/cancel')
def stop_control_session(key: str):
    return cancel_session(key)

# Checkpoint messages are stored and sent by the Android head, never by PC AI.
from pydantic import BaseModel, Field
from typing import Literal

class ContinuationRequest(BaseModel):
    project: str = Field(min_length=3,max_length=70)
    checkpoint_id: str = Field(min_length=3,max_length=100)
    priority_tier: Literal['5*','6*','7*']
    spec_reference: str = Field(min_length=3,max_length=250)
    message: str = Field(min_length=1,max_length=3800)

@router.get('/phone/continuation/status')
def phone_continuation_status():
    return request('/continuation/status').json()

@router.post('/phone/continuation/queue')
def phone_continuation_queue(data:ContinuationRequest):
    return request('/continuation/queue','POST',data.model_dump(),timeout=6.0).json()

@router.post('/phone/continuation/dispatch')
def phone_continuation_dispatch():
    return request('/continuation/dispatch','POST',{},timeout=15.0).json()

@router.get('/phone/observation/status')
def phone_observation_status():
    return request('/observation/status').json()

@router.get('/phone/observation/events')
def phone_observation_events():
    return request('/observation/events').json()

@router.get('/phone/observation/frame')
def phone_observation_frame():
    return Response(request('/observation/frame').content,media_type='image/jpeg',
                    headers={'Cache-Control':'no-store'})

class VoiceQuestion(BaseModel):
    text: str = Field(min_length=1,max_length=700)
    locale: str = Field(default='en-US',pattern=r'^[a-z]{2}(-[A-Z]{2})?$')

@router.get('/phone/voice/status')
def phone_voice_status():
    return request('/voice/status').json()

@router.post('/phone/voice/question')
def phone_voice_question(data:VoiceQuestion):
    return request('/voice/question','POST',data.model_dump(),timeout=10.0).json()

# Generic application transport for authorized Asterion projects.
# The Android app must be foreground before dispatching launch intents.
class AppLaunch(BaseModel):
    package: str = Field(min_length=3,max_length=180,pattern=r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*){1,12}$')

@router.get('/phone/apps')
def phone_apps():
    return request('/apps').json()

@router.post('/phone/apps/launch')
def phone_app_launch(data:AppLaunch):
    return request('/apps/launch','POST',data.model_dump(),timeout=7.0).json()

class CheckpointAcknowledgment(BaseModel):
    checkpoint_id: str = Field(min_length=3,max_length=100,pattern=r'^[A-Za-z0-9_.-]+$')
    response_receipt: str = Field(min_length=8,max_length=512)

@router.post('/phone/continuation/ack')
def phone_continuation_ack(data:CheckpointAcknowledgment):
    return request('/continuation/ack','POST',data.model_dump(),timeout=6.0).json()

@router.post('/phone/continuation/cancel')
def phone_continuation_cancel():
    return request('/continuation/cancel','POST',{},timeout=6.0).json()

@router.get('/phone/bridge/status')
def phone_bridge_status():
    return request('/github-bridge/status').json()

@router.post('/phone/chat/new')
def phone_chat_new():
    """Request a new ChatGPT conversation; this does not prove navigation."""
    return request('/chat/new','POST',{},timeout=12.0).json()

@router.get('/phone/observation/timeline')
def phone_observation_timeline():
    return request('/observation/timeline').json()

@router.get('/phone/observation/frames/{frame_id}')
def phone_observation_get_frame(frame_id: str):
    # phone_bridge validates the entire URL suffix; no path traversal allowed.
    return Response(request('/observation/frame/'+frame_id).content,
                    media_type='image/jpeg',headers={'Cache-Control':'no-store'})
