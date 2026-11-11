> **CURRENT RELEASE — Asterion Control v0.9.26 (2026-11-11).** Published installer: `dist/Asterion-Control-v0.9.26-release.apk`; APK SHA-256: `be146e6f57d3b0660c5609c628d344fc9c5f1f7b38a6fa42e87b6f8d61a556f1`; source/build commit: `dcf60699fc1305b66e829334194288acce807e0b`; publication commit: `e79fdaa`. Use **the existing in-app Check for updates** action, which reads `dist/latest-release.json` and verifies SHA-256. Do not install the superseded v0.9.24 repair APK or bypass the updater. The separately published Android update still needs owner-confirmed installation and on-phone acceptance.

> **Transport:** Direct Windows worker → existing authenticated native WebSocket → Samsung is primary; private GitHub bridge is the fallback if the direct ChatGPT tool is not callable. Existing `PhoneDirectMcp`/MCP-named RPC code remains part of the current WSS implementation; do not claim it was all removed or make a separate ChatGPT MCP plugin a prerequisite. Repair verifies the *actual native WebSocket*, not an unrelated gateway process.

> **Cycle semantics:** [Real ChatGPT development cycle contract](docs/CYCLE_EXECUTION_CONTRACT.md). One cycle is a genuine tool-using ChatGPT reply with a verified marker, not an internal artificial model or a queued command. No arbitrary 10/20-turn caps; `max_cycles=0` is continuous. Each substantial ChatGPT development turn can last about 30 minutes. Individual actions, including ChatGPT decision time, command transport and verification, target under 10 seconds end-to-end and about one second for simple Android navigation.

# Asterion Control — Android-primary shared execution tool

**Canonical requirements:** [7* frozen master](7STAR_FROZEN_MASTER.md). **Current evidence:** [PROGRESS.md](PROGRESS.md). **Cross-app interface:** [Control API v1](docs/CONTROL_CROSS_APP_API_V1.md).

Asterion Control is the user's universal, deterministic device-control **tool**, operated externally by ChatGPT. Its Android user interface handles permissions and connection management. It does not embed a paid model API, another AI agent, or duplicate any Asterion application/game engine. Samsung Android is primary; Windows remains an optional subordinate build/desktop worker.

## Versions and safety

- **v0.8.6** is the latest **owner-confirmed installed** Samsung version. [Original owner-signed APK](dist/Asterion-Control-v0.8.6-debug.apk) and [SHA-256](dist/SHA256SUMS-v0.8.6.txt).
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

### Current recovery acceptance ledger (v0.9.26)

Windows recovery code and independent watchdog installed into the existing worker with backup; the authenticated `/api/v1/recovery/status` endpoint returned HTTP 200 after a safe restart. The phone previously reported paired native transport and direct WSS connected. **An end-to-end Auto-repair/Force-reinitialize invocation, fresh video permission, Android v0.9.26 installation and multi-turn cycle acceptance remain unverified; never report these as complete until actual device receipts confirm them.**
