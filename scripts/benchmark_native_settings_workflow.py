"""Read-only, continuous Android Settings workflow through Asterion Control's direct WebSocket.

Runs on the already-paired Windows Control runtime. No GitHub, ADB, screenshots,
microphone, or app data changes in the timed operation path.

Steps: native notification shade -> Settings -> About phone -> Software information
-> return to the original ChatGPT app. Print only timings and neutral screen labels.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from websockets.asyncio.client import connect

STATE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
PAIRING = json.loads((STATE / "phone-pairing.json").read_text(encoding="utf-8"))
BASE = PAIRING["base_url"].rstrip("/")
PHONE_TOKEN = PAIRING["token"]
WINDOWS_TOKEN = (STATE / "control-token.txt").read_text(encoding="utf-8").strip()
STREAM = "ws://192.168.1.133:8911/api/v1/stream/phone"
EXPECTED_PACKAGE = "com.openai.chatgpt"
SETTINGS_PACKAGE = "com.android.settings"


def walk(node):
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def find_bounds(ui, *terms):
    matches = []
    for node in walk(ui.get("root", {})):
        labels = [str(node.get(k, "") or "").strip().lower()
                  for k in ("text", "description")]
        bounds = node.get("bounds")
        if not isinstance(bounds, list) or len(bounds) != 4:
            continue
        if any(any(term.lower() == label or
                   (len(term) > 5 and term.lower() in label)
                   for label in labels) for term in terms):
            if bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                matches.append((node.get("clickable", False), bounds))
    if not matches:
        return None
    # Exact target text is normally a child of a clickable row; tapping its
    # center is safe on read-only navigation entries.
    return matches[0][1]


async def main():
    steps = []
    frames = 0
    started = time.perf_counter()
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                  timeout=4) as http:
        async def ui():
            now = time.perf_counter()
            response = await http.get(BASE + "/ui",
                                      headers={"Authorization": "Bearer " + PHONE_TOKEN})
            response.raise_for_status()
            return response.json(), round((time.perf_counter() - now) * 1000, 1)

        initial, initial_ui_ms = await ui()
        original = initial.get("foreground_package")
        keyboard = initial.get("keyboard") or {}
        if original != EXPECTED_PACKAGE:
            print(json.dumps({"status": "not_started",
                              "reason": "ChatGPT no longer foreground",
                              "foreground": original}))
            return
        if keyboard.get("active") and keyboard.get("editor_package") == EXPECTED_PACKAGE                 and keyboard.get("draft_empty") is not True:
            print(json.dumps({"status": "not_started",
                              "reason": "An existing ChatGPT draft may be present"}))
            return

        async with connect(STREAM,
                           origin="http://192.168.1.133:8911",
                           max_size=4_200_000,
                           open_timeout=6,
                           close_timeout=2) as ws:
            await ws.send(json.dumps({"token": WINDOWS_TOKEN, "monitor": 1, "fps": 10}))
            async def action(label, payload):
                nonlocal frames
                ident = "multi-" + str(len(steps)) + "-" + str(time.monotonic_ns())
                t = time.perf_counter()
                await ws.send(json.dumps({"type": "input", "id": ident, "payload": payload}))
                while time.perf_counter() - t < 6:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    if isinstance(msg, bytes):
                        frames += 1
                        continue
                    report = json.loads(msg)
                    if report.get("type") == "error":
                        raise RuntimeError("Direct stream returned an error")
                    if report.get("type") == "input_ack" and report.get("id") == ident:
                        record = {"step": label, "ok": bool(report.get("ok")),
                                  "roundtrip_ms": round((time.perf_counter()-t)*1000,1),
                                  "device_ms": report.get("device_ms")}
                        steps.append(record)
                        if not report.get("ok"):
                            raise RuntimeError("Native action rejected: " + label)
                        return

                raise TimeoutError("Direct command acknowledgment missing: "+label)

            async def wait_pkg(package, retries=12):
                for _ in range(retries):
                    state, ms = await ui()
                    if state.get("foreground_package") == package:
                        return state, ms
                    await asyncio.sleep(0.13)
                raise RuntimeError("App did not become foreground: " + package)

            async def tap_label(label, state, *names):
                bounds = find_bounds(state, *names)
                if bounds is None:
                    return False
                x = (bounds[0] + bounds[2]) // 2
                y = (bounds[1] + bounds[3]) // 2
                await action(label, {"action":"tap","x":x,"y":y})
                return True

            settings_open = False
            reached_about = False
            reached_software = False
            restore_result = False
            blocker = ""
            try:
                await action("open_notification_shade", {"action":"notifications"})
                state, _ = await ui()
                if not await tap_label("open_Settings_from_shade", state, "Settings"):
                    await action("expand_quick_settings", {"action":"swipe", "x":535,
                                 "y":430,"x2":535,"y2":1350,"duration_ms":240})
                    state, _ = await ui()
                    if not await tap_label("open_Settings_from_expanded_shade", state, "Settings"):
                        await action("dismiss_shade", {"action":"back"})
                        await action("open_home", {"action":"home"})
                        await action("open_app_drawer", {"action":"swipe", "x":535,
                                     "y":1880,"x2":535,"y2":650,"duration_ms":240})
                        state, _ = await ui()
                        if not await tap_label("open_Settings_from_drawer", state, "Settings"):
                            raise RuntimeError("Settings icon not accessible in shade or drawer")

                state, _ = await wait_pkg(SETTINGS_PACKAGE)
                settings_open = True

                for attempt in range(5):
                    state, _ = await ui()
                    if await tap_label("select_About_phone", state, "About phone"):
                        reached_about = True
                        break
                    await action("scroll_Settings_" + str(attempt+1),
                                 {"action":"swipe","x":520,"y":1930,
                                  "x2":520,"y2":510,"duration_ms":210})
                if not reached_about:
                    raise RuntimeError("About phone category not accessible")

                for attempt in range(8):
                    state, _ = await ui()
                    if find_bounds(state, "Software information"):
                        if await tap_label("open_Software_information",state,"Software information"):
                            reached_software = True
                            break
                    await asyncio.sleep(0.15)
                if not reached_software:
                    raise RuntimeError("Software information entry not accessible")
                state, _ = await ui()
                labels = [str(node.get("text","")).lower()
                          for node in walk(state.get("root",{}))]
                verified = any("android version" in text or "one ui version" in text
                               for text in labels)
                steps.append({"step":"verify_software_information",
                              "ok":verified, "read_only":True})
            except Exception as error:
                blocker = str(error)[:160]
            finally:
                # Do not leave the owner in Settings or an expanded notification shade.
                for attempt in range(7):
                    state, _ = await ui()
                    if state.get("foreground_package") == original:
                        restore_result=True
                        break
                    try:
                        await action("return_to_ChatGPT_" + str(attempt+1),
                                     {"action":"back"})
                    except Exception:
                        break
                    await asyncio.sleep(0.08)
                if not restore_result:
                    state, _ = await ui()
                    if state.get("foreground_package") == original:
                        restore_result=True

            total_ms = round((time.perf_counter()-started)*1000,1)
            print(json.dumps({
                "transport":"persisted_authenticated_native_WebSocket_no_GitHub_between_actions",
                "status":"completed" if reached_software and restore_result and not blocker else "partial",
                "settings_opened":settings_open,
                "about_phone_opened":reached_about,
                "software_information_opened":reached_software,
                "original_app_restored":restore_result,
                "steps":steps,
                "total_workflow_ms":total_ms,
                "frames_observed_without_screenshots":frames,
                "first_ui_ms":initial_ui_ms,
                "blocker":blocker
            },ensure_ascii=False,separators=(",",":")),flush=True)


if __name__ == "__main__":
    asyncio.run(main())
