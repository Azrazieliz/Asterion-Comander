"""Verify low-latency remote PC text input contract without typing into owner apps."""
import ctypes
import os
import sys
import pytest

from asterion_remote import windows_text_input as native


def test_powershell_switches_are_not_keyboard_layout_transformed():
    command = 'SCHTASKS /RUN /TN "ASTERION CONTROL SELFHEALING WORKER"'
    assert native._utf16_units(command) == [ord(x) for x in command]
    assert native._utf16_units("/Run /TN") != native._utf16_units(":rUN :tn")


def test_multiline_unicode_supplementary_surrogates_are_preserved():
    command = "First line\nFrench: é à ç\n日本語 😀"
    raw = command.encode("utf-16-le")
    expected = [raw[i] | (raw[i + 1] << 8) for i in range(0, len(raw), 2)]
    assert native._utf16_units(command) == expected
    assert len(expected) > len(command)


def test_request_cap_128k_text():
    with pytest.raises(ValueError, match="131072"):
        native.insert_text("x" * (native.MAX_TEXT_CHARS + 1))


def test_empty_input_is_no_side_effect():
    outcome = native.insert_text("")
    assert outcome["submitted_utf16_units"] == 0
    assert outcome["target_state_verified"] is False


def test_keyboard_events_are_unicode_not_layout_virtual_keys():
    stroke = native._keyboard_event(ord("/"), False)
    release = native._keyboard_event(ord("/"), True)
    assert stroke.type == 1
    assert stroke.u.ki.wVk == 0
    assert stroke.u.ki.wScan == ord("/")
    assert stroke.u.ki.dwFlags == native.KEYEVENTF_UNICODE
    assert release.u.ki.dwFlags & native.KEYEVENTF_KEYUP


@pytest.mark.skipif(sys.platform != "win32", reason="Native INPUT alignment only on Windows")
def test_windows_sendinput_x64_abi_alignment():
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(native._INPUT) == 40


def test_source_has_no_clipboard_replacement():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] /
              "asterion_remote/windows_text_input.py").read_text("utf-8")
    assert "OpenClipboard(" not in source
    assert "SetClipboardData(" not in source
