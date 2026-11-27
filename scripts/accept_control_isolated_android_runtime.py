"""Non-neural runtime acceptance on a disposable CI Android emulator ONLY.

No owner phone, worker, pairing, credentials, permissions, AI inference or release.
Fixture HTTP stays on an adb-reversed runner loopback; UI and HTTP observations
must both succeed. Failed screenshots/dumps are not published as success.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PACKAGE="com.asterion.control"
MARKER="Control runtime fixture"
PORT=18765
observed=[]
evidence={}

def adb(*args,timeout=30):
    return subprocess.check_output(["adb",*args],stderr=subprocess.STDOUT,
                                   timeout=timeout).decode("utf8",errors="replace")

def dump():
    adb("shell","uiautomator","dump","/sdcard/control-acceptance-ui.xml",timeout=20)
    raw=adb("shell","cat","/sdcard/control-acceptance-ui.xml",timeout=10)
    return ET.fromstring(raw[raw.index("<?xml"):])

def locate(label,attempts=8):
    for _ in range(attempts):
        try:
            root=dump()
            for node in root.iter("node"):
                if label not in (node.get("text"),node.get("content-desc")):
                    continue
                coords=list(map(int,re.findall(r"\d+",node.get("bounds",""))))
                if len(coords)==4 and coords[2]>coords[0] and coords[3]>coords[1]:
                    return ((coords[0]+coords[2])//2,(coords[1]+coords[3])//2)
        except (subprocess.SubprocessError,ValueError,ET.ParseError):
            pass
        time.sleep(0.7)
    raise AssertionError("Visible UI element unavailable: "+label)

def tap(label,attempts=8):
    x,y=locate(label,attempts)
    adb("shell","input","tap",str(x),str(y))
    time.sleep(0.6)

def find_by_scroll(label):
    dimensions=adb("shell","wm","size")
    width,height=map(int,re.findall(r"(\d+)x(\d+)",dimensions)[-1])
    for _ in range(8):
        try:
            locate(label,1)
            return
        except AssertionError:
            adb("shell","input","swipe",str(width//2),str(height*3//4),
                str(width//2),str(height//3),"450")
    locate(label)

class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path!="/control-acceptance":
            self.send_error(404)
            return
        observed.append(self.path)
        body=("<!doctype html><html><head><title>Control fixture</title>"
              "</head><body><h1>"+MARKER+"</h1><p>Rendered in native WebView.</p>"
              "</body></html>").encode()
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*args):pass

def main():
    if adb("shell","getprop","ro.kernel.qemu").strip()!="1":
        raise RuntimeError("Refusing to run outside disposable Android emulator")
    server=ThreadingHTTPServer(("127.0.0.1",PORT),Fixture)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        adb("reverse","tcp:"+str(PORT),"tcp:"+str(PORT))
        for setting in ("window_animation_scale","transition_animation_scale","animator_duration_scale"):
            adb("shell","settings","put","global",setting,"0")
        adb("shell","am","start","-W","-n",PACKAGE+"/.MainActivity")
        locate("ASTERION")
        screens={"Screen":"Remote control","Health":"Health & performance",
                 "Connect":"Connections","Tools":"Tools","Home":"Devices"}
        evidence["main_navigation"]=[]
        for name,heading in screens.items():
            tap("Open "+name)
            locate(heading)
            evidence["main_navigation"].append(name)
        find_by_scroll("Asterion Browser")
        tap("Asterion Browser")
        locate("Address and search")
        locate("Browser menu")
        evidence["browser_opened"]=True
        tap("Address and search")
        adb("shell","input","text","http://127.0.0.1:"+str(PORT)+"/control-acceptance")
        adb("shell","input","keyevent","66")
        locate(MARKER,12)
        if not observed:
            raise AssertionError("Fixture rendered without actual HTTP receipt")
        evidence["fixture_http_requests"]=len(observed)
        evidence["webview_render_verified"]=True
        tap("Site")
        locate("Site information")
        tap("Close")
        tap("1 tab")
        tap("New tab")
        locate("2 tabs")
        locate("Asterion Browser")
        tap("2 tabs")
        tap("Close tab 2")
        locate("1 tab")
        tap("Close")
        locate(MARKER,8)
        evidence["tab_create_close_restore"]=True
        # The isolated normal-browser menu exposes controls without claiming
        # biometric vault, provider activation, Tor exit or owner data tests.
        tap("Browser menu")
        locate("Shields and trackers")
        locate("Encrypted vault")
        evidence["browser_security_menu_visible"]=True
        adb("shell","input","keyevent","4")
        evidence["device_class"]="isolated_emulator"
        evidence["physical_owner_phone_verified"]=False
        evidence["owner_signed"]=False
        evidence["ai_exercised"]=False
        evidence["ok"]=True
    finally:
        server.shutdown()
        server.server_close()
        try:adb("reverse","--remove","tcp:"+str(PORT))
        except subprocess.SubprocessError:pass
        print(json.dumps(evidence,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
