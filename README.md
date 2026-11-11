> **CURRENT RELEASE — Asterion Control v0.9.26 (2026-11-11).** Published installer: `dist/Asterion-Control-v0.9.26-release.apk`; APK SHA-256: `be146e6f57d3b0660c5609c628d344fc9c5f1f7b38a6fa42e87b6f8d61a556f1`; source/build commit: `dcf60699fc1305b66e829334194288acce807e0b`; publication commit: `e79fdaa`. Use **the existing in-app Check for updates** action, which reads `dist/latest-release.json` and verifies SHA-256. Do not install the superseded v0.9.24 repair APK or bypass the updater. The separately published Android update still needs owner-confirmed installation and on-phone acceptance.

> **Transport:** Direct Windows worker → existing authenticated native WebSocket → Samsung is primary; private GitHub bridge is the fallback if the direct ChatGPT tool is not callable. Existing `PhoneDirectMcp`/MCP-named RPC code remains part of the current WSS implementation; do not claim it was all removed or make a separate ChatGPT MCP plugin a prerequisite. Repair verifies the *actual native WebSocket*, not an unrelated gateway process.

> **Cycle semantics:** [Real ChatGPT development cycle contract](docs/CYCLE_EXECUTION_CONTRACT.md). One cycle is a genuine tool-using ChatGPT reply with a verified marker, not an internal artificial model or a queued command. Limits: 10 additional turns in an existing chat; 20 in a verified new chat.

# Asterion Control — authoritative operator and recovery contract

**Current operating rule (2026-11-11): Android is the owner-facing head; the existing Windows worker executes commands. Preserve the working pairing, Windows process, Android permissions, signer, project sources, and installations.** This page overrides historical README addenda, release snapshots and superseded connection experiments. The frozen product scope is [7STAR_FROZEN_MASTER.md](7STAR_FROZEN_MASTER.md).

## Connect ChatGPT without wasting time

1. **Direct authenticated Windows worker session is primary.** When an authorized direct Control session is genuinely callable, use the existing native WebSocket/Accessibility/MediaProjection state for fast, adaptive interactions. Keep the session open, use live frames where available and tap grounded Accessibility elements or coordinates. For a short deterministic navigation sequence, prefer the existing state-checked session/batch API. Avoid repeated connection discovery, per-tap status requests and screenshot polling. **Report end-to-end operator latency**, including time between observation and command creation, not merely device execution time.
2. **Existing private GitHub worker relay is the immediate fallback.** If a direct callable worker control is not exposed in a particular conversation, do **not** conclude Asterion Control/Windows/phone is down, stop, or request installation/pairing. Send the command through [Azrazieliz/Asterion-Control-Bridge](https://github.com/Azrazieliz/Asterion-Control-Bridge) `main`: create `commands/active/<id>.json`, read matching `results/<id>.json`. That repository is only message transport; **the same Windows worker actually executes the action**. A completed `ok:true` receipt is required. The fallback is not equivalent to live viewed video.
3. If neither route is callable, distinguish *conversation tool exposure* from *Windows service health* and *native phone reachability*. Never claim the service is broken without its own error evidence. Do not install another controller, rotate existing credentials or use Remote Desktop/ADB as a prerequisite.

### Verified current evidence

2026-11-11: An authenticated `phone_ui` command executed via the existing GitHub fallback returned `ok:true`, `status:complete`, Android foreground `com.openai.chatgpt`, Accessibility tree and worker `elapsed_ms:77`. This proves native phone UI reachability via the established worker **at that moment**, not that a directly callable ChatGPT tool or in-chat live video was exposed. The 77 ms is worker execution time **only**, not end-to-end navigation latency.

The existing Windows/Android system supports native phone input, UI observation, Android screen sharing with OS consent and a Windows-side authenticated WebSocket stream. The Windows real-time stream code still needs actual end-to-end stream/viewer acceptance. An HTTP/MCP tool response is not continuous real-time video.

## Recovery from the Android app

**Connect → Auto-repair connection** checks the saved link, restarts the Android agent if necessary, re-registers with Windows, and confirms that the Windows worker can read phone status before reporting success. An already healthy connection is preserved.

**Connect → Force reinitialize all components** asks for confirmation, restarts the Android listener, runs the Windows recovery endpoint and schedules a safe Windows-worker restart when idle. It preserves Windows pairing, credentials, files, and app settings. Android screen capture may require renewed OS consent. A successful service-start call alone is never reported as proof that the native link works.

These controls are **implemented in Android source as of 2026-11-11**, but deployment status must be tracked separately: source change is not a compiled, installed, or phone-tested APK. The previously existing "Repair connection" lacked post-recovery verification.

## Service and security

Windows API: authenticated private-network HTTP on TCP `8911`; UDP discovery `8912`; Android foreground phone agent listener `8973`. There is an MCP-only gateway on loopback `8995` for approved HTTPS tunnel connections. Direct ChatGPT access requires an actual authorized callable connector in the current conversation; mere deployment of an MCP endpoint does not supply that interface.

For real-time PC/phone interaction use the existing authenticated WebSocket `/api/v1/stream/{source}` and state-checked interaction-session APIs rather than a GitHub command per gesture **where the client can actually consume these APIs**. The direct endpoint remains the production priority; GitHub commands are contingency only. Use private LAN/encrypted VPN and existing bearer authorization, never unauthenticated public listeners or credentials in the repository. Android foreground, Accessibility and MediaProjection permissions remain user-controlled.

## Release and evidence discipline

Latest source state and actual installed build may differ. See [PROGRESS.md](PROGRESS.md) for dated verified receipts. [RELEASE_STATUS.md](RELEASE_STATUS.md) and [README_CONTROL_ADDENDUM.md](README_CONTROL_ADDENDUM.md) are historical records, **not connection instructions**. Never equate source implementation, compilation, app installation, device operation and direct ChatGPT tool availability.

### Current recovery acceptance ledger (v0.9.26)

Windows recovery code and independent watchdog installed into the existing worker with backup; the authenticated `/api/v1/recovery/status` endpoint returned HTTP 200 after a safe restart. The phone previously reported paired native transport and direct WSS connected. **An end-to-end Auto-repair/Force-reinitialize invocation, fresh video permission, Android v0.9.26 installation and multi-turn cycle acceptance remain unverified; never report these as complete until actual device receipts confirm them.**
