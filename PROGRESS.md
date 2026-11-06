# 2026-11-06 — Control-only v0.8.8 update recovery (source repaired; owner-key deployment outstanding)

**No Desktop Commander or ADB was used in this recovery.** Control remains the external deterministic tool, Android is the principal device, Windows is its authorized build worker, and ChatGPT remains the external operator. Frozen 7-star requirements and app data were preserved.

- Repaired the **Windows PowerShell 5.1 encoding error** in `scripts/build_owner_signed_control_088.ps1`: removed the non-ASCII characters that caused the owner's Windows parser to fail before APK compilation. Added regression coverage (`tests/test_owner_signing_compat.py`).
- Replaced the one-shot private Git transport launcher with **Control-owned single-instance supervision**: the existing launcher restarts failed Control bridge processes and avoids duplicate legacy Python workers; the Control Windows launcher starts the supervisor when enabled. Does not invoke Desktop Commander or a new service provider.
- Added a **dedicated private PC active command queue** (`commands/active/`) to the Git-backed Control transport. During first-start legacy migration, only genuinely ambiguous old root commands are skipped, while explicitly reauthorized active commands can continue exactly once. Added deduplication and migration tests (`tests/test_control_bridge_queue.py`).
- Repaired the outstanding `owner-signed-control-v088-20261106` native Control update request and reauthorized the **same command ID** in the private active queue. Its command fast-forwards only the existing Control branch and runs the matching-owner-certificate build/transfer script. New code and the owner-key build remain separate from the installed app until successful execution and owner-approved Android installation.
- **Verified**: [CI 42190608211](https://github.com/Azrazieliz/Asterion-Comander/actions/runs/42190608211) passed at commit `1dfd0be7326665fb9da7125e2aa976f58b7e0bcc`: **41 Python tests passed**, all three critical Control PowerShell scripts passed syntax and ASCII checks, and native Gradle Android build succeeded.
- **Not yet completed**: Original Windows Control bridge has not produced a command result or uploaded a matching-signer v0.8.8 APK. CI debug signer is mismatched and must NOT be installed over owner-confirmed Samsung v0.8.6. There is **no device-install confirmation**. The existing private Git transport is a queued trigger, not an out-of-band way to start a stopped PC process.
- **Unblocker**: The Windows machine must be running its own Asterion Control Windows agent and Git bridge (existing login-autostart shortcuts, or launch the existing `scripts/start_windows.ps1` and `scripts/start_git_bridge.ps1` directly). Once the native Control worker executes the queued checkpoint, inspect its job ID/result, signed APK certificate and private Wi-Fi receipt. The Android package installer still requires owner consent. Do not use Desktop Commander to bootstrap.

---

# 2026-11-06 — Continuation improvements, isolated phone command queue, Android observation history (latest)

**Canonical:** Asterion Control remains Android-primary, shared deterministic device-control infrastructure. ChatGPT is the external AI operator. No new AI service, paid model API, embedded game engine or alteration to `7STAR_FROZEN_MASTER.md`.

## Implemented in Commander PR #1

- Native phone bridge now consumes **`commands/android/phone-<id>.json`** and writes `results/android/phone-<id>.json` in the existing PRIVATE `Azrazieliz/Asterion-Control-Bridge` repository. The previous `commands/android-<id>.json` / `results/android-<id>.json` namespace remains supported for issued legacy commands. Separate ETags, strict operation allowlist, Android Keystore credential protection, local idempotency and durable crash-uncertainty receipts remain in place. The private directories exist; a read-only `phone-control-smoke-20261106` request is queued but NOT executed.
- ChatGPT's operator can request **New chat** navigation through Android Accessibility / MCP / native REST / optional phone-only bridge. It never erases a populated composer, only clicks a specifically labeled visible control, and explicitly reports `verified_new_chat:false`. A real ChatGPT operator must inspect the resulting screen before sending its next checkpoint. This is NOT a tested autonomous conversation loop.
- Added an installed-app searchable native picker for user-selected observation rather than requiring manual Android package names.
- Long-run gameplay observation caps frame storage at 256 MiB, rotates JSONL timelines before unbounded growth, rechecks foreground package before recording, and exposes the recent retained frame timeline plus authenticated per-frame retrieval to the external AI operator. No AI analysis or user-game manipulation is built into Control.
- The Windows owner-signed deployment script now fails if local source differs from remote approved branch, verifies v0.8.6's exact signing certificate against the new build and refuses mismatches, and optionally delivers an accepted matching-signer APK over private authenticated Wi-Fi into Android Downloads with SHA-256 receipt. It NEVER installs silently, uninstalls, wipes data or sends APK bytes through GitHub. Its syntax is checked by CI, but it has NOT run on the original Windows worker.
- Private ChatGPT Asterion Control plugin updated successfully to **v1.6.1**, preserving the existing MCP server declaration and providing the new phone queue and observation methods as instructions.

## Evidence

- [GitHub Actions run 42139069606](https://github.com/Azrazieliz/Asterion-Comander/actions/runs/42139069606) **PASSED** at source commit `5b4465a9176c785bc69f910e3f4ed28c543e4e18`: **37 Python tests passed**, PowerShell original-signer script parser passed, **Gradle Android build passed**, CI APK uploaded (artifact `13467206029`). This CI output is NOT signed with the original owner's certificate.
- CI signer check still reports **`SIGNER_COMPATIBLE_WITH_V086_BASELINE=false`**. The user-confirmed installed version remains **v0.8.6**; the source version is **v0.8.8**. Do NOT recommend the CI APK as an in-place update.
- The previously queued owner-signed Windows build and private phone smoke commands still have no result receipts. No Android device install, live direct MCP authentication, ChatGPT next-turn continuation, voice recognition or long-idle acceptance is claimed from CI alone.

## Unresolved production dependencies

1. The original Windows signing worker must process the queued matching-certificate build once reachable; verify output SHA-256 and transfer receipt. The Android package installer requires owner approval.
2. Connect a stable authenticated HTTPS route to phone-owned MCP and make the actual ChatGPT plugin tool namespace available in the conversation. The original temporary Cloudflare Quick Tunnel is not a durable endpoint. The phone-owned private GitHub bridge is an explicitly enabled fallback and does not replace direct low-latency access.
3. Demonstrate ChatGPT sent checkpoint → new actual model response → inspected receipt → next checkpoint; verify new-conversation UI and no duplicate/incorrect-chat sends.
4. Verify Android real gameplay observation/voice and app permissions, long idle, interrupted transfers, and battery behavior. Keep Pilot/Game and all other project engines separate.

---

# 2026-11-06 — Control v0.8.8, phone-only private fallback and confirmed signer blocker

**Canonical scope unchanged:** Control is shared Android-primary deterministic execution infrastructure for all separate Asterion applications. ChatGPT is the external AI. No embedded AI, paid model API, merged engines, user-data reset or routine ADB.

## Implemented and committed (PR #1, branch `work/android-primary-continuation-observation-20261105`)

- Improved ChatGPT UI checkpoint sending: verifies the queued composer text, waits for UI recomposition before Send, refuses to replace a different draft, bounded retries on transient failures, uncertain submissions require manual review rather than duplicate actions.
- Added `PhoneGitBridge.java`: **owner-opt-in Android-resident private bridge** using the existing `Azrazieliz/Asterion-Control-Bridge` private GitHub command/result layout, without Windows execution. Token enters the phone only, encrypted at rest with Android Keystore AES-GCM. The Android foreground agent polls GitHub HTTPS with conditional ETags (15-second default), supports a STRICT native-tool whitelist, durable uncertain crash receipts, file-result outbox, idempotent command markers, no shell/API-model access, and local revocation. This is a slower fallback, NOT direct real-time MCP.
- Added native Devices controls to configure/revoke the private credential and inspect health; wired the worker through the owner-started Android foreground agent, with a separate executor so observation sampling is not blocked.
- Added authenticated native `GET /github-bridge/status`, corresponding Android MCP `control_phone_bridge_status`, Windows proxy/REST/MCP mappings, and tests.
- Version bumped to source **Android 0.8.8 (code 808)**; GitHub Actions CI verifies both native Android MCP and phone bridge are present.
- Reverted `dist/latest.json` to owner-confirmed 0.8.6 so the self-updater NEVER references an absent/mismatched 0.8.7/0.8.8 release. 0.8.8 preview is not advertised as installed or safe to upgrade.
- Owner-key signing script `scripts/build_owner_signed_control_088.ps1` verifies actual v0.8.6 certificate, compiles original-package v0.8.8 using the same Windows debug keystore, rejects signer mismatch, and would publish the resulting matching-key APK to the development branch only after validation. It does not uninstall/overwrite the current phone installation or change the production update manifest.
- Private ChatGPT plugin **v1.5.0** published (universal Control operating contract + optional phone-bridge command schema); preserves the previous direct MCP server declaration. Plugin version ≠ authenticated connection.

## Evidence and active dependencies

- **CI [42134917023](https://github.com/Azrazieliz/Asterion-Comander/actions/runs/42134917023) PASSED** from source at `5661208bfe7c03d7dafef5037853709177abaeb5`: **35 Python tests passed**, real Gradle **BUILD SUCCESSFUL**, CI APK artifact, SHA-256 `446a5e7246cf9a001ec3f3d1dc6d03e9ec722b867152e99baa0f1220663fcaed`. Subsequent additions are signing-script/documentation only. Java Android bridge source was included in the compiled CI snapshot.
- CI signer **incompatible** with owner-installed 0.8.6: baseline certificate SHA-256 `9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad`; CI certificate SHA-256 `09c819aed23671b9dccca9c3597ac065c0e7f1e94be045996c108b63dbe4c897`. This is a VERIFIED blocker to in-place install. Do not offer the CI APK as an update.
- Queued authorized owner-signed build command `commands/owner-signed-control-v088-20261106.json` in the existing private bridge, waiting for the original Windows worker. Also queued harmless read-only Android smoke request `commands/android-v088-phone-native-smoke-20261106.json` for AFTER the new APK is installed and locally enabled.
- The private Windows bridge returned **no response** to the latest worker-health or signing command. A queued command is not an executed job; do not claim signing, upload or phone installation complete.
- Only 0.8.6 is owner-confirmed installed. Stable phone-hosted authenticated HTTPS direct ChatGPT MCP connection, Android-only bridge device tests, actual ChatGPT next-turn acknowledgment, new-chat routing, spoken-question availability and long-idle resilience remain unverified.

## Next strictly required acceptance

1. Original Windows worker comes online and processes the non-destructive matching-signer build; verify artifact SHA-256 and signature before user-approved Android package update.
2. Install original-package signed 0.8.8 over 0.8.6 without uninstall or app-data reset, on Samsung; verify code 808 and prior pairing/access states.
3. Owner authorizes the optional phone-local Github fallback only if direct MCP remains unavailable (repo-scoped token, never in chat); inspect real `android-...` result receipts from the actual Samsung without relying on Windows.
4. Configure supported stable, authenticated ChatGPT MCP access; do not assume the previous temporary Cloudflare URL is live, nor that a plugin release grants tools automatically.
5. Demonstrate real ChatGPT checkpoint -> send -> next model response -> acknowledgment -> next checkpoint across chat boundaries, preserving 5*/6*/7* source references and respecting ChatGPT platform usage limits. Observe gameplay/voice only with Android consent and project-engine boundaries intact.

---

# 2026-11-06 — Android-native MCP endpoint + verified universal tool CI

- Implemented `AndroidMcp.java` on the Samsung agent: native stateless bearer-authenticated `POST /mcp`, `initialize`, `tools/list`, `tools/call` and direct phone-only tools. No Windows-based phone MCP proxy needed inside the Android device. Private Wi-Fi/VPN/loopback peers only. The private HTTP listener **must not be published on public internet**.
- Updated `mcp_gateway.py` (the temporary Windows-hosted public HTTPS ingress) to merge Samsung native and optional Windows tool catalogues, prefer Android-native phone tools, route PC-only calls to Windows, and allow phone-only logical operation when Windows MCP is not reachable. A stable phone-hosted HTTPS ingress and a connected ChatGPT authenticated plugin are **still missing**; phone-native service does NOT mean ChatGPT's cloud can connect directly yet.
- Owner's universal Control operating contract also documented in `docs/CONTROL_CROSS_APP_API_V1.md`.
- **Branch CI 42132064603 PASS at source commit `33e8a9d6`: 34 Python tests passed (7 warnings), real Gradle `BUILD SUCCESSFUL in 43s`, and a CI Android APK artifact uploaded.** Post-CI branch changes were documentation only (`docs/CONTROL_CROSS_APP_API_V1.md`), not code.
- CI APK is signed using CI's debug identity. There is no evidence this signer matches installed Android v0.8.6. Do not overwrite the owner's application or call the CI build install-ready without signer continuity; rebuild with the original Windows debug keystore if needed.
- Android Control v0.8.6 remains the only **owner-confirmed installed** version. Autonomous future-chat chaining, new-chat routing, voice availability, native self-update, 30+ minute idle recovery and stable HTTPS authentication remain **unverified**. The Windows fallback bridge did not produce a result to the most recent health command, so there is no verified active Control worker in this session.

---

# 2026-11-06 — Universal Android-primary Control, checkpoint continuity and cross-project transport (DEVELOPMENT BRANCH)

**Scope remains frozen by `7STAR_FROZEN_MASTER.md`.** Control is the shared deterministic external operator tool across Asterion and NoWorld, not another model, game player, artwork engine or internal agent. Android is the principal interface and execution device; Windows is subordinate, primarily for incompatible build tasks. ChatGPT is the external AI operator.

**Source implemented on `work/android-primary-continuation-observation-20261105`:**
- Existing v0.8.6 native Android agent, Win worker, streaming and authenticated PC→phone file transfer preserved.
- Android-local durable `ContinuationLedger`: owner-opt-in; spec-based message envelope; bounded 5*/6*/7* reference, project and checkpoint identity; paused state retained; no automatic replay of uncertain sends; cancellation; explicit response acknowledgment before a following checkpoint. External operator submits the next ChatGPT message using Accessibility when ChatGPT is foreground, the composer is blank and accessible Send control exists. Clicking Send remains **submitted_unverified**, not a verified model reply or promise of unlimited model usage.
- Generic installed-app discovery and foreground-only app-launch intent (Android visibility and background-launch rules respected). Tool operations are generic, not game-specific.
- Optional cross-app demonstration/evidence observation, scoped to user-selected launchable package, foreground accessibility verification and fresh MediaProjection frames; captures are local/bounded. This does NOT replace Asterion Pilot's direct in-memory gameplay perception, autonomous playing or game mastery.
- Optional foreground Android text-to-speech question → explicit, one-shot on-device speech recognition transcript, using approved microphone permission. No paid API or raw audio retention.
- Authenticated native REST/MCP and temporary private GitHub bridge adapters for new capabilities. They do not prove the tools are loaded or authenticated in this ChatGPT session.
- GitHub Actions branch validation includes Python API/MCP contracts and Gradle Android APK build; redundant runs cancelled. CI signing is not equivalent to the Windows owner's previously installed debug signing key.

**Evidence:**
- Previously built v0.8.7 APK 273,057 bytes, SHA256 `be8b9d558b775a140b169645a9390604db19932aceb5605d13e6936d16612d5a`, on this branch. This binary PREDATES some of the latest feature fixes. Do not distribute it as the final current source build.
- Branch CI succeeded at `d0d3eaf5` (full Python tests + Android compilation); subsequent commits require their own latest-source validation.
- Private ChatGPT plugin successfully updated to **v1.4.0** with the existing MCP manifest preserved and project-wide operating contract restored.
- Owner's screenshot confirms **installed v0.8.6**. No claim that v0.8.7 was installed, completed a self-update, or ran a full ChatGPT-to-ChatGPT continuation on the device.

**Unresolved, not to be silently called complete:**
1. Rebuild v0.8.7 from the latest commit using the SAME signing identity as installed v0.8.6; owner Windows Control bridge did not return a response to the latest read-only health command. CI debug APK may not upgrade installed app.
2. Device-install and test the self-update with Android unknown-app-source permission and package installer approval. Avoid routine ADB.
3. Connect and authenticate a stable, direct, phone-primary ChatGPT MCP transport. The prior Cloudflare Quick Tunnel and Windows relay are temporary, and direct tool registration is not working in this conversation.
4. End-to-end checkpoint submission → actual ChatGPT reply → acknowledgment → next checkpoint, including optional new-conversation routing; current UI accessibility selectors must be tested on actual Android 17.
5. Long-idle survival, screen/capture consent, app launching, voice recognizer/locale availability, video jitter, typing accuracy, interruption/retry and large-transfer recovery.
6. Respect frozen per-project sources and API boundaries; do not edit Pilot/Game/Codex masters or use Control's evidence screenshots as Pilot's gameplay navigation.

---

# 2026-11-05 — Direct MCP transport trial, Asterion Control plugin v1.3.0
- Implemented `asterion_remote/mcp_gateway.py`: dedicated authenticated MCP-only loopback ingress on port 8995. Forwards `POST /mcp` to existing Windows Control MCP and native Samsung proxy; DOES NOT expose Windows general REST routes through the tunnel. Independent 43+ character bearer credential kept only under `%LOCALAPPDATA%\AsterionControl\mcp-gateway-token.txt`, not in GitHub or plugin.
- Implemented `scripts/start_mcp_gateway.ps1` to start gateway and outbound Cloudflare Quick Tunnel. Installer reported `MCP_AUTHENTICATED_LOOPBACK_OK`, `MCP_TUNNEL_PID=11872`, HTTPS endpoint `https://days-hence-video-autos.trycloudflare.com/mcp`. Remote unauthenticated `POST /mcp` returned HTTP **401**; external `GET /healthz` through HTTPS returned `ok:true`. HTTPS bearer-authenticated external tool call is **not yet verified**; a control connector attempt to submit an authenticated remote test was blocked by platform safety checks and not retried by bypassing them.
- Plugin Creator update succeeded: existing private plugin `plugins_6aecce96358081918d70cb54cdca5b00` is now **v1.3.0** with explicit `.mcp.json` remote HTTPS MCP server and API key (bearer) auth metadata. NO credentials in package. **Direct MCP tool namespace is not exposed in the current ChatGPT conversation** as of update; user may need explicit connection and authentication through a supported UI. Do not claim done.
- The trial Cloudflare `trycloudflare.com` hostname changes after a tunnel restart, has no uptime guarantee, and is **not a production connection**. Durable fully independent access needs stable secure hostname/tunnel hosting and a supported ChatGPT MCP connection with user authentication. No GitHub polling is used inside the local MCP gateway; GitHub was used ONLY to deploy, collect health status, and the pre-existing fallback.
- Windows remains a relay for the trial HTTPS connection; Samsung remains the native principal device but a truly phone-hosted durable gateway is not yet implemented. Do not imply phone works when Windows is off.
- Prior Control-only native acceptance was passed: Samsung 0.8.3 paired/reachable, native screen, UI hierarchy, HOME and swipe. Direct ChatGPT MCP acceptance remains **open**.

---

# 2026-11-05 — v0.8.3 Samsung inactivity recovery (latest)
- **Compiled and installed** Android APK [v0.8.3](dist/Asterion-Control-v0.8.3-debug.apk); APK build published by independent Control Git bridge (commit `86bab7a`, 199,093 bytes, SHA-256 `ed77266a546b6df6200722536f8cd0235f890ad2e4c19159be1d8f79c1c4a484`). The owner-authorized ADB command was used ONLY for install and opening/starting the app, not device acceptance.
- **Implemented**: foreground notification directly opens Control; previous owner-enabled state persisted; `START_STICKY` recovery and transient socket accept retry; safe boot/app-update restart attempt; `stopWithTask=false`; re-arm on Activity resume; user-facing Samsung Battery > Unrestricted settings access; explicit user disable remains respected.
- **Actual Control-only verification** through private, authenticated Git transport: `phone_status` returned `paired:true, reachable:true`; `phone_health` returned Android 17 / Samsung SM-S948B, battery 94%, memory/thermal telemetry; `pc_input` moved pointer with `ok:true`; PC screen and health succeeded.
- **Remaining user consent**: Android Control `accessible:false`, `capture:false`. `phone_ui` and `phone_screen` returned HTTP 503 as expected, not acceptance failures of transport. Owner must enable Asterion Control Accessibility and approve Android MediaProjection once through the phone; Android may require new MediaProjection approval after reboot/stop. Battery unrestricted mode requires owner approval in Settings.
- **Long-idle resilience not yet empirically verified** after background/screen lock; Android vendor OS can still terminate foreground services. Do not claim unkillable service. Periodic acceptance check over actual elapsed inactivity is required, using Control only.
- **ChatGPT control**: Private plugin installed, skill accessible in normal Android ChatGPT, GitHub-based authenticated command bridge operational. Bridge is a high-latency fallback, NOT a real-time ChatGPT transport. Samsung remains primary user controller; Windows subordinate.
- No Work/Desktop Commander for acceptance. No ADB for actual Control functionality checks.

---

# Current continuation — Android v0.8.2 / Plugin v1.2.0 (2026-11-05)
- **Compiled APK published** at [dist/Asterion-Control-v0.8.2-debug.apk](dist/Asterion-Control-v0.8.2-debug.apk). Built on the owner's Windows PC through its PRIVATE Asterion Control GitHub bridge, without Desktop Commander or ADB. Verified build exit 0, 194,889 bytes, SHA-256 `b3e5fe037b43d98dc64682615be37ab77fdd07ad8ca9b84d8435c8ce9d25505f` (commit `cdd475c`).
- v0.8.2 updates pairing failure diagnostics, starts/auto-registers the phone agent after Windows pairing, selects phone's routable Wi-Fi address, retries registration, adds Repair connection and preserves saved credentials. **Android 0.8.2 is not confirmed installed**; owner must approve the APK update without an existing authorized installer channel.
- **Asterion Control private plugin v1.2.0** created and updated; its skill has been loaded from `skills://plugins/asterion-control/asterion-control` in an ordinary ChatGPT conversation. **Do not tell user to use Work or web.** ChatGPT currently calls connected GitHub as the separate private command relay, not a connected direct MCP tool.
- GitHub bridge independent acceptance: Windows health succeeds; latest `phone_status` still reports `paired:false`. Phone's native agent was reachable over Wi-Fi and rejected unauthenticated requests with HTTP 401; this is NOT successful phone authorization.
- **Still blocked**: user-initiated Android APK update, then one-time phone-to-Windows pairing and Android Accessibility/MediaProjection approval, followed by actual phone screen/gesture validation. Low-latency PC↔Android streaming exists in source, but ChatGPT's GitHub fallback remains polling rather than real-time. Do not claim full completion.
- Use no more routine ADB or Desktop Commander. Use the private GitHub bridge to execute PC commands. Android is the head; Windows is a subordinate worker.

---

# Asterion Control — deployment and acceptance ledger
Date: 2026-11-05. Frozen scope: [7STAR_FROZEN_MASTER.md](7STAR_FROZEN_MASTER.md).

## Actual delivered files
- Native Android **v0.8.1 compiled APK**: [dist/Asterion-Control-v0.8.1-debug.apk](dist/Asterion-Control-v0.8.1-debug.apk). Windows debug key signing, 188,525 bytes, SHA-256 in [dist/SHA256SUMS-v0.8.1.txt](dist/SHA256SUMS-v0.8.1.txt).
- Windows standalone agent bundle: [dist/Asterion-Control-Windows-v0.8.1.zip](dist/Asterion-Control-Windows-v0.8.1.zip), 225,892 bytes. Includes a repaired per-user autostart script and one-time installer.
- Both published by the owner's Windows PC Git client, commit 63c2abc and verified through GitHub history. Compilation and packaging are real, not mockups.

## Verified on the owner's Windows machine
- Android Gradle **BUILD SUCCESSFUL** for v0.8.1 from project source.
- Windows Python test suite **24 passed** with dedicated pytest temp directory; earlier default temp path caused unrelated Windows PermissionErrors.
- Windows agent running as independent uvicorn process at its private Wi-Fi address on TCP 8911.
- UDP discovery socket present on port 8912.
- TCP discovery endpoint returns an authenticated-app identity response from the private LAN address.
- Per-user Windows login autostart shortcut exists.
- Windows agent was bootstrapped using Desktop Commander, but the agent itself does not need that service to run.
- The Windows platform lacks permission to add its private UDP firewall rule automatically; Android v0.8.1 has bounded TCP discovery fallback to avoid needing the UDP rule.

## Implemented
- Android-first native UI with Home/Screen/Health/Devices, premium design assets, and hidden internal command/logcat controls.
- Native phone foreground agent, Accessibility gestures/input, MediaProjection capture with user approval, phone thermal/battery/health.
- PC live frame stream, desktop inputs, files/processes, saved deterministic script execution and internal command APIs.
- Android discovers PC via Wi-Fi UDP or bounded local-subnet TCP scanning; one-time 8-digit PIN; revocable device credentials.
- ChatGPT MCP tools now expose native Android control operations instead of ADB tool operations. Source/API availability is **not a connected ChatGPT plugin**.

## Still NOT verified / blocked
- **Android v0.8.1 has not been installed and operated on the owner's Samsung after USB was unplugged.** The user must initiate Android package installation and grant system-required screen/capture/accessibility permissions at least once. No trusted over-the-air Android installer channel is established yet.
- **No USB-free full end-to-end acceptance:** no demonstrated native phone screen frame and Android accessibility gesture from this ChatGPT conversation with Desktop Commander disconnected, nor PC input under that exact condition.
- **ChatGPT Plus custom full MCP write connector is not available** according to current OpenAI documentation; MCP registration also requires eligible workspace/account, private Secure MCP Tunnel or HTTPS endpoint, and explicit user connection. An API server alone cannot enroll ChatGPT.
- No automatic cross-network encrypted VPN enrollment; only private LAN/VPN access is implemented.
- No evidence yet of continuous remote video latency, reconnection after network changes, or independent ChatGPT operation.

## Acceptance
When Android v0.8.1 is installed, approve the one-time Windows pairing and Android accessibility/MediaProjection permissions. Confirm native PC input/screen, native Android input/screen and telemetry, reconnect, and independent ChatGPT tool availability without relying on Desktop Commander or ADB. Until then, label the app **compiled/deployed Windows agent, unverified Android end-to-end**.
