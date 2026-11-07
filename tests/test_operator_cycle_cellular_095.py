"""Runtime-independent guards for the approved ChatGPT operator architecture."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"android/app/src/main/java/com/asterion/control"
def java(name):return (SRC/name).read_text(encoding="utf-8")

def test_operator_writes_single_checkpoint_and_receipt():
    ledger=java("ContinuationLedger.java")
    native=java("AndroidMcp.java")
    assert all(x in native for x in ("control_phone_continuation_queue",
        "control_phone_continuation_dispatch","control_phone_continuation_ack"))
    assert 'last_checkpoint' in ledger and 'response_receipt' in ledger
    assert 'requires_manual_review' in ledger
    assert 'A send may already have happened; inspect before cancelling' in ledger

def test_phone_does_not_run_chatgpt_turns_locally():
    assert 'cycles.tick()' not in java("AgentService.java")
    assert 'Run two-turn phone cycle test' not in java("MainActivity.java")
    assert 'ChatGPT checkpoint continuation' in java("MainActivity.java")

def test_cellular_connection_is_bound_to_android_active_network():
    direct=java("PhoneDirectMcp.java")
    assert 'getActiveNetwork()' in direct
    assert 'network.getAllByName(HOST)' in direct
    assert 'network.getSocketFactory().createSocket()' in direct
    assert 'setEndpointIdentificationAlgorithm("HTTPS")' in direct
    assert 'sec-websocket-accept' in direct.lower()
    assert 'last_error_detail' in direct

def test_error_13_uses_system_recognizer_fallback_exactly_once():
    voice=java("VoiceDialogueService.java")
    assert 'SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE' in voice
    assert 'SpeechRecognizer.createOnDeviceSpeechRecognizer(this)' in voice
    assert 'SpeechRecognizer.createSpeechRecognizer(this)' in voice
    assert 'if(offline && (code==SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE' in voice
    assert 'beginRecognition(locale,id,false)' in voice
