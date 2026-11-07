"""Native Android phone-only private relay wiring and owner controls."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/"android/app/src/main/java/com/asterion/control/MainActivity.java"
AGENT=ROOT/"android/app/src/main/java/com/asterion/control/AgentService.java"
BRIDGE=ROOT/"android/app/src/main/java/com/asterion/control/PhoneGitBridge.java"

def test_owner_opt_in_native_ui_and_encrypted_github_only():
    main=MAIN.read_text(encoding="utf8")
    bridge=BRIDGE.read_text(encoding="utf8")
    assert 'button(privateBridge,"Enable private phone relay"' in main
    assert "PhoneGitBridge.configure(this,token,enabled)" in main
    assert "Fine-grained GitHub token" in main
    assert "phoneBridgeFeedback" in main
    assert "GitHub token" in main
    assert "AndroidKeyStore" in bridge
    assert "PhoneGitBridge.enabled" in main
    assert "Azrazieliz/Asterion-Control-Bridge" in bridge

def test_phone_scheduler_live_but_disabled_by_default():
    agent=AGENT.read_text(encoding="utf8")
    bridge=BRIDGE.read_text(encoding="utf8")
    assert "phoneBridgePoller.scheduleWithFixedDelay" in agent
    assert "PhoneGitBridge.poll(this)" in agent
    assert "phoneBridgePoller.shutdownNow()" in agent
    assert "Executors.newSingleThreadScheduledExecutor()" in agent
    assert 'if(!enabled(owner)||busy)return;' in bridge
    assert 'getBoolean("enabled",false)' in bridge

def test_no_unprompted_windows_or_tunnel_requirement():
    bridge=BRIDGE.read_text(encoding="utf8")
    assert "api.github.com/repos/" in bridge
    assert "MCP" not in bridge[bridge.index("static void poll("):bridge.index("private static void pruneFinishedCommand")]
    assert "control_phone_" in bridge
    assert "phone_"+'_' in "phone_"
