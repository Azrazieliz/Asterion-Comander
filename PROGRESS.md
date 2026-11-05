# Asterion Control — v0.8.0 beta progress
Date: 2026-11-05. Canonical scope: [7STAR_FROZEN_MASTER.md](7STAR_FROZEN_MASTER.md)

## Implemented and committed
- Standalone Windows API/agent, Windows one-time installer, per-user autostart and Private-LAN firewall approvals.
- UDP LAN service discovery on port 8912; Android head discovers the Windows peer over Wi-Fi, not USB or ADB.
- Eight-digit expiring one-time PIN exchange; separately authorized credentials stored hashed on Windows, with rate-limited pairing attempts.
- Android Control UI: live remote desktop, phone/PC health, manual PIN fallback with no permanent token exposure.
- Native Android foreground agent, AccessibilityService input, MediaProjection capture with user approval, on-device health including Android thermal pressure.
- Authenticated WebSocket frame stream now accepts individually paired Android credentials, not just the Windows master key.
- Native long-press remote interaction; removed legacy ADB discovery/fallback from visible user-interface workflow.
- 21 Python tests passed in the development environment and browser JavaScript syntax checked.
- GitHub Actions workflow configured to build and upload Android 0.8.0 APK and publish a beta release on successful execution.

## Not verified / not complete
- The v0.8.0 APK has NOT been confirmed installed or working on the owner's Samsung; last physically installed version reported was v0.7.0.
- No direct end-to-end PC and phone acceptance has passed with Desktop Commander and ADB disabled. Device control and stream latency are not measured.
- The user's ChatGPT account does not have Asterion Control registered as a callable plugin. MCP registration and an authorized network tunnel still need setup; merely exposing /mcp does not connect it to ChatGPT.
- This HTTP transport is for trusted private LAN or encrypted private VPN only; do NOT forward port 8911 publicly. Automatic encrypted internet relay is not implemented.
- GitHub Actions success/release availability was not independently verified here. CI debug signing may differ from the previous APK's signature.

## Acceptance required
With USB disconnected and Desktop Commander shut down: through Asterion Control's own API, show PC frames and interact with the PC, receive phone frames through MediaProjection, dispatch actual phone Accessibility actions, verify health telemetry and reconnection, and log observed evidence. Neither compilation nor ADB testing counts as completion.
