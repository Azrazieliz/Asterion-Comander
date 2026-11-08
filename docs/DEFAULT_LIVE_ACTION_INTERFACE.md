# Asterion Control — default native action interface

**Selected default (2026-11-08):** interactive, state-aware phone actions over the existing authenticated, full-duplex Windows Control <-> Android WebSocket. This replaces prewritten click-through scripts and GitHub file polling as the **preferred** action mechanism, whenever the interactive client and direct paired transport are available.

## What the fast Clock benchmark proved — and did not prove

The successful Samsung Clock test opened the real app, navigated World clock, Stopwatch, Timer, and Alarm, and returned to ChatGPT. It completed 10 native actions in 3.254 seconds, with a 75.4 ms median action acknowledgment. **The test's decisions were prewritten in Python.** It was not a human/assistant choosing each step after observing new state.

The durable improvement is to use the same low-latency WebSocket for **one dynamic action at a time**. Never assume an app starts on its home screen, that tabs or accessibility labels are stable, or that a successful tap means the intended screen loaded.

## Default interaction protocol

Existing authenticated endpoint: `ws://<paired-private-Control-IP>:8911/api/v1/stream/phone`. Must use the established owner pairing token; no new credentials or public listener. All phone calls require the existing Android native accessibility authorization.

The interactive session starts with `{"token":"<owner-paired-token>","video":true,"fps":12}`, or `"video":false` for semantic-only operation when visual sharing is not available. **Video false does not mean screen sharing is active.** Authorized native MediaProjection live frames may be streamed when video is true; do not replace them with screenshots.

For each action:

1. **Inspect:** `{"type":"inspect","id":"unique-1"}`. Receive `{"type":"ui_state","id":"unique-1","ok":true,"state_id":"ephemeral-token","state":{"foreground_package":"...","root":...,"keyboard":...}}`.
2. **Choose dynamically:** Use current foreground app, accessibility text and bounds, keyboard state, and observed native live video if available. Prefer supported semantic `click_text` for labeled controls over stale absolute coordinates.
3. **Execute once:** `{"type":"input","id":"unique-2","state_id":"ephemeral-token","expect_package":"<observed-package>","payload":{"action":"click_text","text":"..."} }`.
4. **Read `input_ack`**, then **inspect again** and decide the next step based on the **actual new state**. Action acknowledgment means native dispatch succeeded, not that the intended UI transition completed.
5. If a page changed before input, state token expired, app is different, or action timed out, **stop, inspect, and replan**. Never replay an action with uncertain outcome.

A state token is valid for **one subsequent action**, on the same live WebSocket session, for up to **10 seconds**, only if the current native accessibility UI still matches the observed state. Duplicate operation IDs are rejected without executing twice. Older clients without `state_id` remain supported but are **not the preferred interactive workflow**.

**App launch:** `{"type":"launch_app","id":"unique-3","state_id":"...","expect_package":"com.asterion.control","package":"com.sec.android.app.clockpackage"}`. It only dispatches the existing Android `/apps/launch` API, which itself requires Control visible in the foreground and an installed launchable package. The reply does **not** prove the new app opened; inspect after launch.

**CLI implementation:** `scripts/live_phone_operator.py` keeps one connection open and accepts operator-chosen `inspect`, `tap`, `click`, `swipe`, `back`, `home`, `recents`, `notifications`, `type`, and `launch` commands. Every action consumes the last inspection token; it then re-inspects. It does not run a fixed script. Use the installed Control Python environment and set `ASTERION_CONTROL_LIVE_URL` when the paired private host changes. The CLI does not render video itself.

## Transport precedence

1. **Preferred:** direct, interactive, state-guarded WebSocket with real-time native UI state and optionally owner-authorized live MediaProjection video.
2. **Native MCP alternate:** direct Android MCP over existing phone-initiated WSS / paired private network. The Windows gateway already routes `control_phone_ui` / `control_phone_input` via `phone_live.invoke` when connected. For this route, explicitly inspect UI before each input; the WebSocket state-token guard is **not** automatically enforced by this separate MCP path.
3. **Fallback only:** private GitHub command/result mailbox for initial orchestration or when direct transport is unavailable. Do not treat GitHub polling as real-time control or substitute screenshot loops.
4. **Optional:** prewritten scripts for repeatable tests where the starting state and expected transitions are known. They must still verify state between steps, stop on mismatch, and restore the original app. Never make them the default for exploratory app navigation.

## Host integration boundary

The Control application and Windows agent now expose the **live state-aware protocol**. **ChatGPT can use it directly only when a compatible, authorized tool/connector is available in the conversation.** GitHub file access alone cannot attach to a persistent live WebSocket from the ChatGPT side, so do not claim the chat itself is continuously connected merely because the Windows client runs a script. A matching host-facing tool adapter, including request-level action arguments and UI state output, remains necessary for true per-turn interactive assistant operation. Until connected, GitHub may still initiate a single PC job, but that job is not equivalent to live assistant-selected actions.

## Safety and acceptance

- Preserve Android accessibility, private-network/auth, MediaProjection consent and stop controls, and chat draft. Never capture microphone/audio without owner opt-in.
- No blind multi-action chain, silent duplicate submission, broad PC shell or lockscreen bypass.
- Do not log tokens, full UI contents, screenshots or typed text in ordinary benchmark results.
- Reject stale state, unexpected foreground app, expired token, duplicate request IDs, and unverified app launches.
- Check native frame streaming, semantic-only operation without screen capture, video/input coexistence, and reconnect behavior on real device.
- Actual time to complete workflows includes UI loading and decision-making, not only low millisecond native acknowledgments.

**Status:** Source implementation + regression tests; live Android acceptance of the new inspect/state-token protocol and a ChatGPT-facing direct connector still need verification. The Clock timing only proves the *existing* direct streaming/input transport.
