"""User-visible ChatGPT keyboard/blue-send-arrow workflow regression."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/"android/app/src/main/java/com/asterion/control/ControlAccessibilityService.java").read_text()
def test_samsung_keyboard_and_visible_blue_arrow_action():
    assert 'tapVisibleBlueArrow' in S
    assert 'AccessibilityWindowInfo.TYPE_INPUT_METHOD' in S
    assert 'GestureDescription.StrokeDescription(path,0,65L)' in S
    assert 'sendBlueArrowOrAccessibleButton' in S
    assert 'keyboard.commitText(message,1,null)' in S
    assert 'next.performEditorAction(EditorInfo.IME_ACTION_SEND)' not in S
    assert 'Keyboard draft prepared but no Send action offered' not in S

def test_preserves_user_draft_and_does_not_fake_completed_cycle():
    assert 'if(!before.isEmpty()&&!message.equals(before))' in S
    assert 'Existing user draft preserved; refusing to overwrite' in S
    assert 'ChatGPT text still in composer; Send did not complete' in S
    assert 'Blue Send action cleared draft; await visible ChatGPT reply' in S
    assert 'ChatGPT is no longer foreground' in S
    assert '"com.openai.chatgpt".contentEquals(root.getPackageName())' in S

def test_safe_fallback_requires_actual_visible_keyboard_window():
    assert 'if(!found)return false' in S
    assert 'chatKeyboard()==null)return false' in S
    assert 'keyboard.top-35*density' in S
    assert 'metrics.widthPixels-39*density' in S
    assert 'release-0912' in (ROOT/'.github/workflows/android-continuation-branch.yml').read_text()
