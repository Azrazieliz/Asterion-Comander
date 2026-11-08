"""True native Android MediaProjection stream is independent of screenshot tools."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android/app/src/main/java/com/asterion/control"
AGENT = (ANDROID / "AgentService.java").read_text()
MCP = (ANDROID / "AndroidMcp.java").read_text()
BRIDGE = (ANDROID / "PhoneGitBridge.java").read_text()
CAPTURE = (ANDROID / "CaptureService.java").read_text()

def test_stream_is_live_mediaprojection_and_auth_gated():
    assert "projection.createVirtualDisplay(" in CAPTURE
    assert "ImageReader.newInstance(" in CAPTURE
    assert 'path.equals("/stream")' in AGENT
    assert "multipart/x-mixed-replace; boundary=asterionframe" in AGENT
    assert 'if(!auth.equals("Bearer "+token(this)))' in AGENT
    assert AGENT.index('if(!auth.equals("Bearer "+token(this)))') < AGENT.index('path.equals("/stream")')
    assert 'path.equals("/stream/status")' in AGENT

def test_live_viewers_cannot_exhaust_phone_command_workers():
    assert "Executors.newFixedThreadPool(6)" in AGENT
    assert "liveStreamClients.incrementAndGet()>2" in AGENT
    assert "liveStreamClients.decrementAndGet();" in AGENT
    assert "Native MediaProjection stream is inactive or stale" in AGENT
    assert "CaptureService.active&&!s.isClosed()" in AGENT

def test_status_is_metadata_not_a_screenshot():
    assert "control_phone_stream_status" in MCP
    assert "owner.nativeStreamStatus()" in MCP
    assert '"stream_status"' in BRIDGE
    assert 'put("stream_format","multipart/x-mixed-replace")' in AGENT
    assert 'put("stream_clients",liveStreamClients.get())' in AGENT
