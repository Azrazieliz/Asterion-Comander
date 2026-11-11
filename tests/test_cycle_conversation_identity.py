"""Regression contracts for ChatGPT same-thread cycle navigation.

These are static/source invariants; they supplement (not replace) Android
on-device testing of the actual Samsung Recents UI and assistant reply ACK.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ACCESS=(ROOT/"android/app/src/main/java/com/asterion/control/ControlAccessibilityService.java").read_text(encoding="utf-8")
CATALOG=(ROOT/"android/app/src/main/java/com/asterion/control/AppCatalog.java").read_text(encoding="utf-8")
CYCLE=(ROOT/"android/app/src/main/java/com/asterion/control/ContinuationCycle.java").read_text(encoding="utf-8")
LEDGER=(ROOT/"android/app/src/main/java/com/asterion/control/ContinuationLedger.java").read_text(encoding="utf-8")

def method(s:str, start:str, stop:str)->str:
    assert s.count(start)==1
    a=s.index(start)
    b=s.index(stop,a+len(start))
    return s[a:b]

def test_same_chat_only_rollover_at_twenty_messages():
    assert 'CHAT_ROLLOVER_MESSAGES=20' in CYCLE
    assert 'String conversation=input.optString("conversation","same")' in CYCLE
    assert 'state.optInt("turns_in_chat",0)*2>=CHAT_ROLLOVER_MESSAGES' in CYCLE
    assert 'if(initialNew||rollover)' in CYCLE

def test_cycle_recovery_does_not_create_new_chat():
    restore=method(ACCESS,"  JSONObject requestChatForeground(){",
                   "  JSONObject sendChatMessage(")
    assert "GLOBAL_ACTION_RECENTS" in restore
    assert "findChatRecentCard" in restore
    assert "Existing ChatGPT task card not visible" in restore
    assert "getLaunchIntentForPackage" not in restore
    assert "FLAG_ACTIVITY_NEW_TASK" not in restore
    assert "requestNewChat" not in restore

def test_generic_app_launcher_preserves_chatgpt_task():
    resume=method(CATALOG,"  static JSONObject requestLaunch(",
                  "\n  }\n}" )
    assert 'if("com.openai.chatgpt".equals(packageName))' in resume
    assert 'access.requestChatForeground()' in resume
    assert "existing_task_only" in resume
    assert resume.index('if("com.openai.chatgpt".equals(packageName))') < resume.index("getLaunchIntentForPackage")

def test_keyboard_disappearing_after_verified_send_gesture_is_normal():
    verification=method(ACCESS,"  private void verifyChatSend(",
                        "  private void sendBlueArrowOrAccessibleButton(")
    assert 'else if(remaining==null)' in verification
    assert 'chatOutcome(true,true,' in verification
    assert 'keyboard dismissed normally' in verification

def test_unverified_send_waits_for_unique_assistant_marker():
    assert 'if (outcome.optBoolean("sent"))' in LEDGER
    assert '"submitted_unverified"' in LEDGER
    assert 'if(outcome.optBoolean("uncertain"))' in LEDGER
    assert 'ASTERION-CYCLE-ACK:' .replace("\u200b","") in ACCESS
