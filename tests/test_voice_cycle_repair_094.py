"""Regression guards for truthful on-phone voice and cycle self-tests.
These source checks do not replace the user's actual speaker/mic/ChatGPT device test.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "android/app/src/main/java/com/asterion/control"

def read(name):
    return (SRC / name).read_text(encoding="utf-8")

def test_speaker_selftest_does_not_require_offline_recognizer_to_make_sound():
    voice = read("VoiceDialogueService.java")
    # Independent TTS diagnostic still invokes speech even when the offline STT
    # service is absent. The regular authenticated Q&A remains strictly offline.
    assert 'if(Build.VERSION.SDK_INT>=31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this))' in voice
    assert 'speakNow(prompt,"en-US",id)' in voice
    assert 'speakerPlaybackStarted=true' in voice
    assert 'speakerPlaybackCompleted=true' in voice
    assert '.put("speaker_started",speakerPlaybackStarted)' in voice
    assert '.put("speaker_finished",speakerPlaybackCompleted)' in voice
    assert 'state("failed","Speaker playback completed; Android offline speech recognition is not installed or enabled")' in voice
    assert 'listener=SpeechRecognizer.createOnDeviceSpeechRecognizer(this)' in voice

def test_cycle_test_does_not_enqueue_without_required_accessibility():
    main = read("MainActivity.java")
    start = main.split("private void startPhoneCycleTest()")[1].split(
        "private void showCycleStatus()")[0]
    assert 'if(ControlAccessibilityService.active==null)' in start
    assert start.index('if(ControlAccessibilityService.active==null)') < start.index(
        'ContinuationCycle.get(this).start(input)')
    assert 'Settings.ACTION_ACCESSIBILITY_SETTINGS' in start
    assert 'getLaunchIntentForPackage("com.openai.chatgpt")' in start
    assert 'showCycleStatus()' in start

def test_voice_permission_denial_is_visible():
    main = read("MainActivity.java")
    assert 'Voice test blocked: Android microphone permission denied' in main
    assert 'runVoiceTestAfterPermission=false' in main
    assert 'Offline recognition available: ' in main
    assert 'Speaker completed: ' in main

def test_native_mcp_reports_real_package_version():
    mcp = read("AndroidMcp.java")
    assert 'getPackageInfo(owner.getPackageName(),0).versionName' in mcp
    assert '.put("version","0.9.2")' not in mcp
