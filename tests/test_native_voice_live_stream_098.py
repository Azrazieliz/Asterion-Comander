"""Real-time native Control stream and user-only voice lifecycle regression tests."""
from pathlib import Path
from asterion_remote.live_stream import _take_mjpeg_frame
from asterion_remote import native_routes

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'android/app/src/main/java/com/asterion/control'

def test_mjpeg_frames_reassemble_across_boundary():
    jpeg=b'\xff\xd8hello\xff\xd9'
    piece=b'--asterionframe\r\nContent-Type: image/jpeg\r\nContent-Length: 9\r\n\r\n'+jpeg+b'\r\n'
    buffer=bytearray()
    for part in (piece[:10],piece[10:45],piece[45:]):buffer.extend(part)
    assert _take_mjpeg_frame(buffer)==jpeg
    assert _take_mjpeg_frame(buffer) is None

def test_consent_and_fresh_frame_rate_contract():
    voice=(SRC/'VoiceDialogueService.java').read_text()
    agent=(SRC/'AgentService.java').read_text()
    perf=(SRC/'PerformanceManager.java').read_text()
    assert 'MainActivity.foregroundActivity()==null' in voice
    assert 'Manifest.permission.RECORD_AUDIO' in voice
    assert '"/voice/enable"' in agent and '"/voice/stop"' in agent
    assert 'Thread.sleep(125)' not in agent
    assert 'lastSentAt' in agent and 'CaptureService.latestAtMs' in agent
    assert 'tune(65,62,3000,mode,"normal")' in perf
    assert 'tune(65,62,3000,mode,"full_observation")' in perf
    assert callable(native_routes.phone_voice_enable)
    assert callable(native_routes.phone_voice_stop)
