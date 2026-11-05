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
