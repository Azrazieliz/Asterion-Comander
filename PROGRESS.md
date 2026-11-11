# 2026-11-11 — Continuous overnight cycle correction (v0.9.27)

- **Owner directive:** one cycle = the continuously repeating process, potentially overnight or across days. Each ChatGPT turn should spend approximately 30 minutes on substantive real work (under 25 minutes without verified progress is inadequate). Each individual action—observation, reasoning, API, gesture and outcome check—must finish under 10 seconds end-to-end; trivial actions target approximately 1 second. Device execution time alone is not the end-to-end latency.
- **Source implemented:** `ContinuationCycle` now accepts `max_cycles=0` as unbounded by default rather than limiting total turns to 10/20. A new ChatGPT conversation is requested once when explicitly configured, not once per turn. Durable per-turn response timing warnings and owner-readable status were added. Unique reply ACK/DONE, uncertain-send guard and quiet evidence window were preserved.
- **Tested:** Original owner-signed v0.9.27 Android build completed; SHA-256 `3cdc5813446f7c220f5344fc0c97474fa48280db67921a7d8dd760e194aca1d3`, original certificate `9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad`. Seven existing native Windows/recovery regression tests passed; unbounded-cycle source checks passed.
- **Published:** v0.9.27 APK and canonical `dist/latest-release.json` / `dist/latest.json` via existing GitHub release feed on commit `75419ac`. No GitHub Actions build.
- **Not yet verified:** Owner installation of v0.9.27, sustained live ChatGPT turns of ~30 minutes, unattended overnight continuation/rollover, or under-10-second ChatGPT-inclusive end-to-end action latency. Native WSS media/tap timings from an earlier test do not measure ChatGPT thinking.

---

# 2026-11-11 — current access and safe-recovery implementation

- The existing private GitHub relay executed `phone_ui` on the authorized Windows worker and returned `ok:true`, `status:complete`, Android `com.openai.chatgpt` foreground, native Accessibility tree and 77 ms worker-side execution. The same worker continues to serve both direct and fallback routes; this is **not** direct ChatGPT tool exposure, live in-chat video acceptance, or measured end-to-end gesture time.
- Implemented in the Android app source: **Auto-repair connection**, a verified Windows-to-phone registration/reachability check; **Force reinitialize · keep pairing**, a user-confirmed phone listener restart that preserves credentials/settings. Screen-sharing permission remains under Android's control. Neither source change is an installed APK until build/install/phone testing is recorded.
- **Authoritative operating procedure:** [README.md](README.md). Direct authorized worker/WebSocket first for low-latency UI interaction, GitHub relay immediately when direct tool absent. Legacy prototype docs are explicitly marked historical; do not infer worker or phone downtime merely from missing tool exposure.
- Timing contract: separate operator think/decision latency, transport delay, device ACK and end-state verification. A 77 ms ACK alone does not make a ten-minute session "real time".

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
