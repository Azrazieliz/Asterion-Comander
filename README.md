> **CURRENT PUBLISHED RELEASE — Asterion Control v0.9.30 (2026-11-11).** Owner-certificate APK: `dist/Asterion-Control-v0.9.30-release.apk`; SHA-256 `006c8c77a644cdb2c6f85ae0b9a8f910bb5a9dbd5300ede3fa472ec8edf4cbc6`; compiled source `887e547299596df7cb613a2423f51b53d7cdda99`, published on `main` commit `1441eb7`. **18/18 source and native regression tests passed; Android Java compilation and the signed APK build succeeded.** This version removes misleading claims about remote reachability, screen capture, private queue freshness, pairing completion, transfer receipts, cycle counters and the ChatGPT checkpoint launcher. **Installation, live UI audit and cycle acceptance remain unverified.** Use the app's existing **Check for updates** control, not an older APK.

> **Windows console and action acceptance (2026-11-11):** Native worker auto-repair watchdog now uses a fully windowless `wscript` launcher, and spawned shell/script jobs use `CREATE_NO_WINDOW`. Actual spawned shell had no console window; worker and paired Samsung recovered after idle restart. Two persistent video WebSockets stayed up while alternating 6/6 verified PC/Android actions in 0.08–0.82 s each, **measured inside the worker**. This does not include external ChatGPT decision latency; the ChatGPT→worker direct executor is still not exposed in this chat. Verified source/test: `work/control-0927-overnight-cycles-20261111`, `scripts/accept_persistent_worker_pc_phone.py`; full receipts: `PROGRESS.md`.

> **HISTORICAL RELEASE — Asterion Control v0.9.28 (2026-11-11).** Original-certificate Android APK: `dist/Asterion-Control-v0.9.28-release.apk`; SHA-256 `c74daa7a31323edea1cf780163d23db39ed764ac9586df060563fdb28534f90a`; compiled source commit `651377137bd8d1053e17b7f3fd3aa49bee3324d2`; publish commit `234ed5e`. Use the existing in-app **Check for updates** flow. Source branch: `work/control-0927-overnight-cycles-20261111`; main branch is the publication/documentation index, not automatically the full installed source. Installation and a genuine 20-message unattended rollover remain **unverified**.

> **HISTORICAL RELEASE — Asterion Control v0.9.26 (2026-11-11).** Published installer: `dist/Asterion-Control-v0.9.26-release.apk`; APK SHA-256: `be146e6f57d3b0660c5609c628d344fc9c5f1f7b38a6fa42e87b6f8d61a556f1`; source/build commit: `dcf60699fc1305b66e829334194288acce807e0b`; publication commit: `e79fdaa`. Use **the existing in-app Check for updates** action, which reads `dist/latest-release.json` and verifies SHA-256. Do not install the superseded v0.9.24 repair APK or bypass the updater. The separately published Android update still needs owner-confirmed installation and on-phone acceptance.

> **Transport:** Direct Windows worker → existing authenticated native WebSocket → Samsung is primary; private GitHub bridge is the fallback if the direct ChatGPT tool is not callable. Existing `PhoneDirectMcp`/MCP-named RPC code remains part of the current WSS implementation; do not claim it was all removed or make a separate ChatGPT MCP plugin a prerequisite. Repair verifies the *actual native WebSocket*, not an unrelated gateway process.

> **Cycle semantics (2026-11-11):** [Continuous overnight cycle operator contract](docs/CYCLE_EXECUTION_CONTRACT.md). **A cycle is a continuous, potentially overnight development loop**; each turn should contain ~30 minutes of meaningful work, with turns under 25 minutes without substantive results considered inadequate. Every individual observation/decision/API/UI/verification action must finish in under 10 seconds end-to-end (simple gestures ~1 second). **No 10/20 total-turn cap:** `max_cycles=0` is unbounded by default. **Automatic conversation rollover after 20 total messages** preserves context via a canonical GitHub handoff; the overall cycle remains unlimited. Safety checks still prevent ambiguous double-sends and unverified chat changes. Published v0.9.26 still has older cycle code until the v0.9.27 repair is built and installed.

# Asterion Control — Android-primary shared execution tool

**Canonical requirements:** [7* frozen master](7STAR_FROZEN_MASTER.md). **Current evidence:** [PROGRESS.md](PROGRESS.md). **Cross-app interface:** [Control API v1](docs/CONTROL_CROSS_APP_API_V1.md).

Asterion Control is the user's universal, deterministic device-control **tool**, operated externally by ChatGPT. Its Android user interface handles permissions and connection management. It does not embed a paid model API, another AI agent, or duplicate any Asterion application/game engine. Samsung Android is primary; Windows remains an optional subordinate build/desktop worker.

## Versions and safety

- **v0.8.6** is the historical installed baseline. The owner subsequently confirmed installing **v0.9.26**; installation of later releases has not been independently verified. [Original owner-signed APK](dist/Asterion-Control-v0.8.6-debug.apk) and [SHA-256](dist/SHA256SUMS-v0.8.6.txt).
- **v0.8.8** is source-complete and CI-compilable on development branch `work/android-primary-continuation-observation-20261105`, tracked in [PR #1](https://github.com/Azrazieliz/Asterion-Comander/pull/1). It is **not installed**, and CI's debug APK cannot upgrade installed v0.8.6 because the cert SHA-256 differs.
- Owner's v0.8.6 signing certificate SHA-256: `9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad`. Never uninstall or clear app data just to install a CI-signed APK.
- Safe owner-key build procedure: [build_owner_signed_control_088.ps1](scripts/build_owner_signed_control_088.ps1). Its output is published only after matching the installed certificate. An authorized private build request has been queued, but **the Windows bridge has not responded**. The release update index therefore remains pinned to the working v0.8.6 until signed delivery.

## Native Android operation

Enable phone control within Asterion Control; Android accessibility and MediaProjection permissions must be granted by the owner. Re-grant screen sharing after Android invalidates an old session. Samsung remote operations include native screen/stream, gestures/input, UI tree, battery/thermal/health, approved app discovery/launch and owned-app observation; controls are not dependent on ADB. Protected windows and Android background launch rules remain respected.

The Android foreground agent exposes an authenticated local/private-network `POST /mcp` with native tools. **Do not port-forward its HTTP port 8973.** A stable trusted HTTPS ChatGPT connection is not yet activated; the existing Windows-hosted Cloudflare Quick Tunnel was a temporary trial.

## ChatGPT operation and free Android-only fallback

**Preferred:** authenticate a supported direct MCP plugin to a stable HTTPS or supported secure tunnel. Merely installing the plugin or compiling an MCP server is not proof of connection; availability and account permissions must be checked in ChatGPT.

**Optional fallback in uninstalled v0.8.8:** Devices → *Private GitHub relay* → *Connect Android private bridge*. Enter a GitHub fine-grained credential scoped to **Contents read/write only** on the user's private `Azrazieliz/Asterion-Control-Bridge` repository. The credential is encrypted through Android Keystore on the Samsung; it is not entered into ChatGPT, GitHub source files or the Windows computer.

When enabled, the phone polls the existing private commands folder over GitHub HTTPS and writes results into the same private result folder. ChatGPT uses its already-connected GitHub plugin to create `commands/android-<id>.json`, e.g. `{"id":"android-probe-001","op":"phone_status","params":{}}`, and reads `results/android-<id>.json`. Only the native Android whitelist is accepted, with bounded retry/idempotency protection and durable failure receipts. This **does not** allow shell execution on Android, bypass OS permissions, create a second model, or deliver low-latency streaming. It is a temporary no-Windows fallback, not the final direct MCP transport.

## Spec-linked continuation and observation

On owner opt-in, ChatGPT can queue a bounded project/spec-referenced checkpoint and use Android Accessibility to submit the next message in the already installed ChatGPT app. It never overwrites a different existing draft. Clicking Send remains `submitted_unverified`; the actual next ChatGPT response must be observed and acknowledged. Conversation limits and context limits remain applicable; autonomous multi-conversation continuation is **not yet device proven**.

Voice uses Android foreground microphone permission, text-to-speech and on-device recognition when available. Optional observation retains bounded, owner-selected app evidence; it does not replace Asterion Pilot's own direct live game-state perception, strategies or mastery.

## Existing Windows worker and advanced tools

The Windows companion remains available for explicit desktop, native build, file and process operations, persistent interaction sessions, signed APK packaging and private Wi-Fi file transfers. Advanced commands and scripts remain ChatGPT-facing, not ordinary user-facing Android navigation. Old Windows-only pairing instructions and the 0.3 prototype history remain in [README_CONTROL_ADDENDUM.md](README_CONTROL_ADDENDUM.md) for reference.

## Verified vs pending

Native Windows/Samsung screen and input, persistent sessions, Wi-Fi APK delivery and v0.8.6 installation have historical device evidence. v0.8.8's Android GitHub fallback, direct MCP, continuation and voice compile, but **their new on-device behavior has not been accepted**. Completing this requires the matching owner-signed APK, Android installation/permission approvals, a real ChatGPT next-turn receipt, and a stable authenticated direct connection. See [the current ledger](PROGRESS.md).

### Historical recovery acceptance ledger (v0.9.26)

Windows recovery code and independent watchdog installed into the existing worker with backup; the authenticated `/api/v1/recovery/status` endpoint returned HTTP 200 after a safe restart. The phone previously reported paired native transport and direct WSS connected. **An end-to-end Auto-repair/Force-reinitialize invocation, fresh video permission, Android v0.9.26 installation and multi-turn cycle acceptance remain unverified; never report these as complete until actual device receipts confirm them.**
