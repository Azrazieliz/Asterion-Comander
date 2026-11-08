"""Read-only phone telemetry and explicit input proxy over private network/VPN."""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Literal
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

class AppBridgeAction(BaseModel):
    package: str = Field(min_length=3,max_length=180)
    action: str = Field(min_length=1,max_length=80)
    request_id: str = Field(min_length=8,max_length=100)
    payload: dict = Field(default_factory=dict)

class AppBridgeOperation(BaseModel):
    package: str = Field(min_length=3,max_length=180)
    request_id: str = Field(min_length=8,max_length=100)
    cancel: bool = False

@router.post('/phone/app-bridge/operation')
def app_bridge_operation(data:AppBridgeOperation):
    return request('/app-bridge/operation','POST',data.model_dump(),timeout=11).json()

@router.get('/phone/app-bridge/apps')
def app_bridges():return request('/app-bridge/apps').json()

@router.post('/phone/app-bridge/invoke')
def app_bridge_invoke(data:AppBridgeAction):
    return request('/app-bridge/invoke','POST',data.model_dump(),timeout=11).json()

@router.get('/phone/logcat')
def phone_own_logcat():
    return request('/diagnostics/logcat',timeout=5).json()

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

class CycleRequest(BaseModel):
    project: str = Field(min_length=3,max_length=70)
    priority_tier: Literal['5*','6*','7*']
    spec_reference: str = Field(min_length=3,max_length=250)
    message: str = Field(min_length=1,max_length=3000)
    cycle_id: str = Field(min_length=3,max_length=66)
    conversation: Literal['same','new'] = 'same'
    voice_locale: str = Field(default='en-US',min_length=2,max_length=5)
    max_cycles: int = Field(default=0,ge=0,le=1000000)

class NewChatVerification(BaseModel):
    verification: str = Field(min_length=8,max_length=512)

class PerformanceMode(BaseModel):
    mode: Literal['automatic','foreground','full','quiet']

@router.get('/phone/performance/status')
def phone_performance_status():
    return request('/performance/status').json()

@router.post('/phone/performance/mode')
def phone_performance_mode(data: PerformanceMode):
    return request('/performance/mode','POST',data.model_dump(),timeout=7).json()

@router.post('/phone/performance/optimize')
def phone_performance_optimize():
    return request('/performance/optimize','POST',{},timeout=7).json()

@router.get('/phone/network/status')
def phone_network_status():
    return request('/network/status').json()

@router.get('/phone/cycles/status')
def phone_cycle_status():
    return request('/cycles/status').json()

@router.post('/phone/cycles/start')
def phone_cycle_start(data: CycleRequest):
    return request('/cycles/start','POST',data.model_dump(),timeout=6).json()

@router.post('/phone/cycles/pause')
def phone_cycle_pause():
    return request('/cycles/pause','POST',{},timeout=6).json()

@router.post('/phone/cycles/resume')
def phone_cycle_resume():
    return request('/cycles/resume','POST',{},timeout=6).json()

@router.post('/phone/cycles/stop')
def phone_cycle_stop():
    return request('/cycles/stop','POST',{},timeout=6).json()

@router.post('/phone/cycles/confirm-new-chat')
def phone_cycle_confirm_new_chat(data: NewChatVerification):
    return request('/cycles/confirm-new-chat','POST',data.model_dump(),timeout=6).json()

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
    question_id: str = Field(default='',max_length=100)
    locale: str = Field(default='en-US',pattern=r'^[a-z]{2}(-[A-Z]{2})?$')

class VoiceCommand(BaseModel):
    locale: str = Field(default='en-US',pattern=r'^[a-z]{2}(-[A-Z]{2})?$')

class VoiceSay(BaseModel):
    text: str = Field(min_length=1,max_length=700)
    locale: str = Field(default='en-US',pattern=r'^[a-z]{2}(-[A-Z]{2})?$')

class VoiceAcknowledgment(BaseModel):
    question_id: str = Field(min_length=3,max_length=100)

class VoiceSettings(BaseModel):
    rate: float = Field(ge=0.85,le=1.15)
    pitch: float = Field(ge=0.90,le=1.10)

@router.get('/phone/voice/settings')
def phone_voice_settings():
    return request('/voice/settings').json()

@router.post('/phone/voice/settings')
def phone_voice_configure(data: VoiceSettings):
    return request('/voice/settings','POST',data.model_dump(),timeout=7).json()

@router.post('/phone/voice/enable')
def phone_voice_enable():
    return request('/voice/enable','POST',{},timeout=8).json()

@router.post('/phone/voice/stop')
def phone_voice_stop():
    return request('/voice/stop','POST',{},timeout=7).json()

@router.post('/phone/voice/ack')
def phone_voice_ack(data: VoiceAcknowledgment):
    return request('/voice/ack','POST',data.model_dump(),timeout=7).json()

@router.get('/phone/voice/status')
def phone_voice_status():
    return request('/voice/status').json()

@router.post('/phone/voice/command')
def phone_voice_command(data:VoiceCommand):
    return request('/voice/command','POST',data.model_dump(),timeout=10.0).json()

@router.post('/phone/voice/say')
def phone_voice_say(data:VoiceSay):
    return request('/voice/say','POST',data.model_dump(),timeout=10.0).json()

@router.post('/phone/voice/question')
def phone_voice_question(data:VoiceQuestion):
    return request('/voice/question','POST',data.model_dump(),timeout=10.0).json()

class DirectChatMessage(BaseModel):
    message: str = Field(min_length=1,max_length=3000)

@router.post('/phone/chat/direct')
def phone_chat_direct(data: DirectChatMessage):
    return request('/chat/direct','POST',data.model_dump(),timeout=15.0).json()

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
