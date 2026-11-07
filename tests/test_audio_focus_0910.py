"""Native Android voice must suppress competing music during speech and microphone recognition."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VOICE=(ROOT/"android/app/src/main/java/com/asterion/control/VoiceDialogueService.java")
def test_voice_gets_exclusive_audio_focus_and_releases_on_every_end():
    s=VOICE.read_text()
    assert "AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE" in s
    assert "AudioManager.AUDIOFOCUS_REQUEST_GRANTED" in s
    assert 'acquireAudioFocus(); // Android pauses competing music where the player supports focus.' in s
    assert 'if("answered".equals(value)||"failed".equals(value)||"acknowledged".equals(value))' in s
    assert "abandonAudioFocusRequest(speechAudioRequest)" in s
    assert "exclusive_audio_focus" in s
    assert 'releaseAudioFocus();' in s[s.index("@Override public void onDestroy()"):]
def test_legacy_music_is_not_explicitly_played_or_dismissed():
    s=VOICE.read_text()
    assert "dispatchMediaKeyEvent" not in s
    assert "AUDIOFOCUS_GAIN" in s
