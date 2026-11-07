"""Android 13+ native InputMethod fallback for Compose-backed ChatGPT entry."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/"android/app/src/main/java/com/asterion/control"
def test_input_method_enabled_for_keyboard_fallback():
    xml=(ROOT/"android/app/src/main/res/xml/accessibility_service.xml").read_text()
    s=(MAIN/"ControlAccessibilityService.java").read_text()
    assert "flagInputMethodEditor" in xml
    assert "onCreateInputMethod()" in s
    assert "getCurrentInputConnection()" in s
    assert 'getCurrentInputStarted()' in s
    assert 'chatKeyboard()' in s and '"com.openai.chatgpt"' in s
def test_keyboard_does_not_overwrite_user_draft_or_blindly_hit_enter():
    s=(MAIN/"ControlAccessibilityService.java").read_text()
    assert 'if(!before.isEmpty()&&!message.equals(before))' in s
    assert 'IME_ACTION_SEND' in s
    assert 'Keyboard draft prepared but no Send action offered' in s
    assert 'Keyboard draft remains; send not confirmed' in s
    assert 'No lower-screen ChatGPT composer found' not in s
    assert 'result.put("foreground_package"' in s
    assert '.put("editor_package"' in s
def test_release_911_uses_native_keyboard_not_privileged_adb():
    s=(ROOT/"android/app/build.gradle").read_text()
    assert "versionCode 911" in s and "versionName '0.9.11'" in s
    assert "adb shell input" not in (MAIN/"ControlAccessibilityService.java").read_text()
