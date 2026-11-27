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
    assert 'tapVisibleBlueArrow' in s
    assert 'Visible ChatGPT keyboard and blue Send arrow not confirmed; draft preserved' in s
    assert 'Send tap completed but message remains visible; do not replay an uncertain submission' in s
    assert 'No lower-screen ChatGPT composer found' not in s
    assert 'result.put("foreground_package"' in s
    assert '.put("editor_package"' in s
def test_release_911_uses_native_keyboard_not_privileged_adb():
    s=(ROOT/"android/app/build.gradle").read_text()
    import re
    code=int(re.search(r"versionCode\s+(\d+)",s).group(1))
    version=tuple(map(int,re.search(r"versionName\s+'(\d+)\.(\d+)\.(\d+)'",s).groups()))
    assert code==version[0]*10000+version[1]*100+version[2] and code>=912
    assert "adb shell input" not in (MAIN/"ControlAccessibilityService.java").read_text()
