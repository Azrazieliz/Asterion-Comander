"""Music-safe Android audio contract, replacing the obsolete exclusive-focus expectation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "android/app/src/main/java/com/asterion/control/MainActivity.java").read_text()
VOICE = (ROOT / "android/app/src/main/java/com/asterion/control/VoiceDialogueService.java").read_text()
RESTORE = (ROOT / "android/app/src/main/java/com/asterion/control/RestoreReceiver.java").read_text()

def test_voice_never_seizes_exclusive_media_audio_focus():
    assert "requestAudioFocus(" not in VOICE
    assert "AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE" not in VOICE
    assert "dispatchMediaKeyEvent" not in VOICE
    assert "preserve music/media playback" in VOICE.lower()

def test_mic_remains_opt_in_after_legacy_upgrade():
    assert 'MUSIC_SAFE_MIGRATION_PREF="voice_music_safe_migrated_v923"' in VOICE
    assert ".putBoolean(ALWAYS_ON_PREF,false)" in VOICE
    assert ".putBoolean(MUSIC_SAFE_MIGRATION_PREF,true)" in VOICE
    assert ".getBoolean(ALWAYS_ON_PREF,false)" in VOICE
    assert "VoiceDialogueService.migrateMusicSafePreferences(this);" in MAIN
    assert "VoiceDialogueService.migrateMusicSafePreferences(context);" in RESTORE
    # Opening the Control UI must never opt in to ambient recording by itself.
    resume = MAIN.split("@Override protected void onResume()", 1)[1].split("@Override public void onRequestPermissionsResult", 1)[0]
    assert ".putBoolean(VoiceDialogueService.ALWAYS_ON_PREF,true)" not in resume
    assert "ensureOwnerRequestedAlwaysOn(this)" in resume

def test_unrequested_sticky_restart_does_not_capture_microphone():
    assert 'if(intent==null && !getSharedPreferences("voice_style",MODE_PRIVATE)' in VOICE
    assert "stopSelf();return START_NOT_STICKY;" in VOICE
    assert "startListening(request)" in VOICE  # manual opt-in still works
