> **Release correction — 2026-11-11:** The canonical published update is **v0.9.25**, manifest SHA-256 `06f5f2d0f753ba697615dbefbabe96f7beaafb753b5065ec1449777d310e05b7`. The separate **v0.9.24 repair APK** built in an older development checkout has SHA-256 `dae1e1233ab998b0b5def3c26805f00865178e7ae84094c12b20c54a19736c6e` and **must not be installed or published over v0.9.25**. The Android app already contains a checksum-validating update detector (`UpdateManager`); retain it. The user's direct native WebSocket transport is connected. Do not require a new MCP plugin/gateway or restart a working ingress merely because old filenames contain `mcp`. The source still contains MCP-style RPC handlers inside the WSS system; removal has **not** been completed at the code/protocol level, so deleting those files blindly would break working access.

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

**Connect → Force reinitialize · keep pairing** asks for confirmation, restarts only the Android phone listener and re-registers it. It preserves Windows pairing, credentials, files, and app settings. Android screen capture may require renewed OS consent. A successful service-start call alone is never reported as proof that the native link works.

These controls are **implemented in Android source as of 2026-11-11**, but deployment status must be tracked separately: source change is not a compiled, installed, or phone-tested APK. The previously existing "Repair connection" lacked post-recovery verification.

## Service and security

Windows API: authenticated private-network HTTP on TCP `8911`; UDP discovery `8912`; Android foreground phone agent listener `8973`. There is an MCP-only gateway on loopback `8995` for approved HTTPS tunnel connections. Direct ChatGPT access requires an actual authorized callable connector in the current conversation; mere deployment of an MCP endpoint does not supply that interface.

For real-time PC/phone interaction use the existing authenticated WebSocket `/api/v1/stream/{source}` and state-checked interaction-session APIs rather than a GitHub command per gesture **where the client can actually consume these APIs**. The direct endpoint remains the production priority; GitHub commands are contingency only. Use private LAN/encrypted VPN and existing bearer authorization, never unauthenticated public listeners or credentials in the repository. Android foreground, Accessibility and MediaProjection permissions remain user-controlled.

## Release and evidence discipline

Latest source state and actual installed build may differ. See [PROGRESS.md](PROGRESS.md) for dated verified receipts. [RELEASE_STATUS.md](RELEASE_STATUS.md) and [README_CONTROL_ADDENDUM.md](README_CONTROL_ADDENDUM.md) are historical records, **not connection instructions**. Never equate source implementation, compilation, app installation, device operation and direct ChatGPT tool availability.
