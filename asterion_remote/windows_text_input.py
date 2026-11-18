"""Fast text insertion into an owner-authorized Windows desktop session.

Windows SendInput with KEYEVENTF_UNICODE sends the user's UTF-16 input directly
to the focused desktop application. No clipboard, global hotkeys, shell execution,
pasteboard overwrite, external service, or per-character PyAutoGUI delay.

The remote UI/API deliberately caps one request at 128 Ki characters. Larger
data should be handled as a transferred file, not millions of synthetic keys.
"""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

MAX_TEXT_CHARS = 131_072
MAX_BATCH_UNITS = 96
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT),
                ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _keyboard_event(unit: int, released: bool) -> _INPUT:
    event = _INPUT()
    event.type = INPUT_KEYBOARD
    event.u.ki = _KEYBDINPUT(
        0, unit, KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if released else 0),
        0, 0)
    return event


def _utf16_units(text: str) -> list[int]:
    raw = text.encode("utf-16-le", errors="strict")
    return [raw[n] | (raw[n+1] << 8) for n in range(0, len(raw), 2)]


def insert_text(text: str) -> dict[str, int | bool]:
    """Insert requested text exactly once; throw on a partial/unverified SendInput.

    Windows foreground state is outside this function's knowledge. A successful
    SendInput means events were submitted, not that the target document changed.
    """
    if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
        raise ValueError("Remote text exceeds the 131072-character request limit")
    if not text:
        return {"submitted_utf16_units": 0, "requested_characters": 0,
                "target_state_verified": False}
    if os.name != "nt":
        raise RuntimeError("Native Unicode keyboard injection requires Windows")
    units = _utf16_units(text)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    send = user32.SendInput
    send.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    send.restype = wintypes.UINT
    dispatched = 0
    for start in range(0, len(units), MAX_BATCH_UNITS):
        batch = units[start:start + MAX_BATCH_UNITS]
        events = (_INPUT * (2 * len(batch)))()
        for index, unit in enumerate(batch):
            events[2 * index] = _keyboard_event(unit, False)
            events[2 * index + 1] = _keyboard_event(unit, True)
        count = int(send(len(events), events, ctypes.sizeof(_INPUT)))
        if count != len(events):
            raise RuntimeError(
                f"Windows keyboard injection outcome unknown after {dispatched} "
                "UTF-16 code units; do not automatically replay the text")
        dispatched += len(batch)
        # Give the target application time to consume its Windows input queue.
        if start + MAX_BATCH_UNITS < len(units):
            time.sleep(0.004)
    return {"submitted_utf16_units": dispatched, "requested_characters": len(text),
            "target_state_verified": False}
