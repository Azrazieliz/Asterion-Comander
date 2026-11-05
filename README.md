# ASTERION CONTROL · Android-first remote control

**Build:** v0.8.1 native Android beta + Windows companion. **Project scope:** [7* frozen master](7STAR_FROZEN_MASTER.md).

Android is the primary user interface. Windows executes desktop jobs and supplies the remote screen, file, process and health APIs. Control contains **no AI**. Script execution, terminal and logcat are hidden internal tools for ChatGPT, not normal end-user navigation.

## Installable downloads

- **Android:** [Asterion-Control-v0.8.1-debug.apk](dist/Asterion-Control-v0.8.1-debug.apk) — native Samsung Android APK; compiled on the development PC. See [SHA-256](dist/SHA256SUMS-v0.8.1.txt).
- **Windows:** [Asterion-Control-Windows-v0.8.1.zip](dist/Asterion-Control-Windows-v0.8.1.zip) — Windows API, service launcher, autostart installation and firewall setup.
- **Evidence:** [PROGRESS.md](PROGRESS.md). Compilation and backend tests **do not** constitute independent remote-control acceptance.

## Initial connection (no ADB)

1. On Windows, extract the Windows ZIP and run **INSTALL_ASTERION_CONTROL.bat**; approve the Windows private-network firewall dialog once. The Windows agent runs under your login and is configured to restart at next Windows login.
2. On Android, install the APK (existing older debug-signed builds signed by the same Windows key should update normally), launch Control, and tap **Find my Windows computer**. Both devices must initially be on the same Wi-Fi or a trusted private VPN. If UDP discovery is blocked, Control scans its local subnet for the Control TCP endpoint; no IP entry is normally necessary.
3. Enter the **8-digit one-time pairing code** shown by the Windows agent. The code expires after ten minutes. Control retains its device-specific key internally for reconnections. Never paste permanent access tokens into the UI.
4. To enable independent Android control, use **Enable phone access** and grant Accessibility, notification, and MediaProjection screen-sharing permissions when Android requests them. Screen sharing is an ongoing approved session; the OS may require renewed approval after service restart.
5. Open **Screen** to operate the Windows desktop. Health reports OS-exposed sensors. Advanced remote commands, logcat and saved scripts remain available only through authorized internal APIs.

**The Android build does not require USB or ADB for runtime communication.** You cannot silently install an APK or approve sensitive Android permissions remotely until that device has an already authorized, working control channel. The app does not override Android's secure-window rules.

## Host API and operational limits

The Windows agent exposes authenticated HTTP REST and MCP endpoints on TCP port 8911; LAN discovery uses UDP 8912 with TCP discovery fallback. These are for an authorized **private** network only. **Do not port-forward HTTP 8911 onto the public internet.** Use a VPN or a protected HTTPS tunnel for cross-network access. Persistent end-to-end internet relay and automatic VPN enrollment have not yet been implemented.

Native Android support: a foreground phone agent with token authorization, Accessibility-driven input/gesture dispatch, MediaProjection snapshots and continuous session capture, and device health.

Native PC support: image/video frame delivery, UI input, file operations, process/command operations, parameterized saved scripts, and resource monitoring.

The Android app is the user-facing head; the Windows agent is a remote executor. No other Asterion application engine has been copied into Control.

## ChatGPT connection

Control exposes an MCP server and native-phone tools, but **an MCP endpoint does not automatically register a ChatGPT plugin**. The account/workspace must support creation of custom MCP connections, and a publicly reachable HTTPS or Secure MCP Tunnel endpoint must be authorized through ChatGPT Plugins. A local 192.168.x.x URL is not directly reachable by ChatGPT cloud tools.

Current OpenAI documentation limits full custom MCP write access primarily to ChatGPT Business and Enterprise/Edu customers. On other plans, use the phone's own interface and a separately supported external workflow; **do not mistake the existing GitHub or Desktop Commander connector for a Control connection**.

## Acceptance contract

Only report **operational** when, with USB unplugged and Desktop Commander unavailable, the same authorized Control channel is demonstrated to:
- view and send mouse/keyboard actions to the Windows desktop;
- view and send accessibility gestures to the Samsung device;
- retrieve PC/phone health and job status;
- reconnect after Wi-Fi disruption; and
- allow ChatGPT to invoke the Control API through an actually connected tool, not through a simulated test.

**Currently:** Backend and Android compilation tests are verified; independent end-to-end device acceptance is still pending. See [PROGRESS.md](PROGRESS.md).
