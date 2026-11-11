"""Asterion Control phone-local tests are callable even without the Windows bridge."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def java(filename):
    return (ROOT / "android/app/src/main/java/com/asterion/control" / filename).read_text()

def test_owner_can_run_local_voice_test_without_remote_plugin():
    activity=java("MainActivity.java")
    voice=java("VoiceDialogueService.java")
    assert '"Test speaker and microphone now"' in activity
    assert 'this::testVoiceDialogue' in activity
    assert '.setAction("TEST")' in activity
    assert 'runVoiceTestAfterPermission' in activity
    assert 'pendingLocalTest' in voice
    assert 'localVoiceTest()' in voice
    assert 'SpeechRecognizer.createOnDeviceSpeechRecognizer' in voice
    assert '"answered".equals(phase)' in activity

def test_chatgpt_is_the_operator_and_android_does_not_start_local_cycles():
    activity=java("MainActivity.java")
    agent=java("AgentService.java")
    native=java("AndroidMcp.java")
    assert '"ChatGPT checkpoint continuation"' in activity
    assert '"Run two-turn phone cycle test"' not in activity
    assert 'this::startPhoneCycleTest' not in activity
    assert 'cycles.tick()' not in agent
    assert 'cycleWorker' not in agent
    assert 'control_phone_continuation_queue' in native
    assert 'control_phone_continuation_dispatch' in native
    assert 'control_phone_continuation_ack' in native

def test_mobile_data_is_allowed_but_requires_real_authorization():
    bridge=java("PhoneGitBridge.java")
    transport=java("TransportConnectivity.java")
    assert "TRANSPORT_CELLULAR" in transport
    assert "TRANSPORT_VPN" in transport
    assert 'if(!enabled(owner)||busy)return;' in bridge
    assert 'Missing private GitHub credential' in bridge

def test_release_is_a_real_optimized_owner_signed_apk():
    gradle=(ROOT/"android/app/build.gradle").read_text()
    workflow=(ROOT/".github/workflows/android-continuation-branch.yml").read_text()
    assert "versionCode 912" in gradle
    assert "versionName '0.9.12'" in gradle
    assert "debuggable false" in gradle
    assert "minifyEnabled true" in gradle
    assert "signingConfig signingConfigs.ownerRelease" in gradle
    assert ":app:assembleRelease" in workflow
    assert "Asterion-Control-v0.9.12-release.apk" in workflow
