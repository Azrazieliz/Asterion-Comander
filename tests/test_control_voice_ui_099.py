"""Premium Control UI and native offline-natural voice contract; no legacy key generator."""
from pathlib import Path
import pytest
from asterion_remote import github_bridge, native_routes
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"android/app/src/main/java/com/asterion/control"

def test_obsolete_key_generator_and_duplicate_cards_removed():
    ui=(SRC/"MainActivity.java").read_text()
    assert '"Copy connection key"' not in ui
    assert '"Copy one-time approval code"' not in ui
    assert '"Authorize ChatGPT (one-time code)"' not in ui
    assert 'wise-eagle-c8b55706.tunnl.gg' not in ui
    assert 'LinearLayout cycles=card()' not in ui
    assert 'LinearLayout mobile=card()' not in ui
    assert 'button(phone,"Check direct Control link"' in ui
    assert 'button(summary,"Cycle status","check",false,this::showCycleStatus)' in ui
    assert 'button(summary,"Auto-repair connection","refresh",true,()->fullRepair(false))' in ui
    assert 'showRemoteSection("desktop")' in ui

def test_voice_picks_installed_high_quality_offline_voice_without_forcing_accent():
    voice=(SRC/"VoiceDialogueService.java").read_text()
    assert 'candidate.isNetworkConnectionRequired()' in voice
    assert 'Voice.QUALITY_HIGH' in voice
    assert 'candidate.getLocale().toLanguageTag().equalsIgnoreCase(language.toLanguageTag())' in voice
    assert 'setUsage(android.media.AudioAttributes.USAGE_ASSISTANT)' in voice
    assert 'naturalRate=0.96f' in voice and 'naturalPitch=1.00f' in voice
    assert 'speaker.setSpeechRate(naturalRate)' in voice
    assert 'speaker.setPitch(naturalPitch)' in voice

def test_voice_preferences_use_owner_authenticated_private_api():
    source=(SRC/"AgentService.java").read_text()
    bridge=(ROOT/"asterion_remote/phone_bridge.py").read_text()
    assert 'path.equals("/voice/settings")' in source
    assert "'/voice/settings'" in bridge
    assert github_bridge.PHONE_NATIVE["phone_voice_settings"]==("GET","/voice/settings")
    assert github_bridge.PHONE_NATIVE["phone_voice_configure"]==("POST","/voice/settings")
    assert native_routes.VoiceSettings(rate=0.96,pitch=1.0).rate==0.96
    with pytest.raises(Exception):
        native_routes.VoiceSettings(rate=2.0,pitch=1.0)

def test_owner_operated_cycle_remains_acknowledged_before_next_step():
    agent=(SRC/"AgentService.java").read_text()
    ledger=(SRC/"ContinuationLedger.java").read_text()
    cycle=(ROOT/"android/app/src/main/java/com/asterion/control/ContinuationCycle.java").read_text(encoding="utf-8")
    assert 'if(!state.optBoolean("active",false)||"paused".equals(state.optString("state")))' in cycle
    assert 'if(!ledger.status().optBoolean("enabled",false))return status();' in cycle
    assert 'if("acknowledged".equals(current))' in cycle
    assert 'submitted_unverified' in ledger and 'acknowledge(' in ledger
    assert 'requires_manual_review' in ledger
