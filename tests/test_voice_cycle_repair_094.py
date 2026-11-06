"""Regression guards for ChatGPT-owned execution and Android speech fallback.
Actual speaker, microphone and cellular acceptance requires device evidence.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"android/app/src/main/java/com/asterion/control"
def read(name):return (SRC/name).read_text(encoding="utf-8")

def test_speaker_test_uses_offline_then_system_recognizer():
    voice=read("VoiceDialogueService.java")
    assert 'SpeechRecognizer.createOnDeviceSpeechRecognizer(this)' in voice
    assert 'SpeechRecognizer.createSpeechRecognizer(this)' in voice
    assert 'SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE' in voice
    assert 'beginRecognition(locale,id,false)' in voice
    assert 'recognizer_backend' in voice
    assert 'speakerPlaybackCompleted=true' in voice
    assert 'speakNow(prompt,"en-US",id)' in voice

def test_android_cycle_runner_is_disabled():
    main=read("MainActivity.java")
    agent=read("AgentService.java")
    mcp=read("AndroidMcp.java")
    assert 'Run two-turn phone cycle test' not in main
    assert 'ChatGPT-operated checkpoints' in main
    assert 'cycles.tick()' not in agent
    assert 'controller","chatgpt"' in mcp
    assert 'control_phone_continuation_queue' in mcp

def test_voice_permission_denial_is_visible():
    main=read("MainActivity.java")
    assert 'Voice test blocked: Android microphone permission denied' in main
    assert 'runVoiceTestAfterPermission=false' in main
    assert 'Offline recognition available: ' in main
    assert 'Speaker completed: ' in main

def test_native_mcp_reports_real_package_version():
    mcp=read("AndroidMcp.java")
    assert 'getPackageInfo(owner.getPackageName(),0).versionName' in mcp
    assert '.put("version","0.9.2")' not in mcp
