"""Observed Windows foreground window, not inferred from input acknowledgements."""
from __future__ import annotations
import os

def foreground():
    if os.name != "nt":
        return {"available":False,"reason":"Windows only"}
    import ctypes
    from ctypes import wintypes
    user=ctypes.windll.user32
    hwnd=user.GetForegroundWindow()
    if not hwnd:
        return {"available":False,"reason":"No foreground window in this desktop session"}
    n=min(2048,max(0,user.GetWindowTextLengthW(hwnd)))
    buf=ctypes.create_unicode_buffer(n+1)
    user.GetWindowTextW(hwnd,buf,n+1)
    pid=wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    return {"available":True,"title":buf.value,"pid":int(pid.value),
            "window_handle":int(hwnd)}
