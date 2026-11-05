# Asterion Control — Plugin Creator integration contract
Date: 2026-11-05
Status: integration specification; **not** proof of an installed/connected plugin.

## Product invariant
**Android is the head and sole human-facing control authority.** The native Samsung Asterion Control app owns device pairing, authorization, session lifecycle, health dashboard, control permissions, and the user's ability to revoke access. The Windows PC is **only a remotely controlled worker**. ChatGPT operates Control as a tool with user-granted access. No embedded AI or "learning" is allowed in Asterion Control.

## Plugin Creator request
Create the ChatGPT plugin **Asterion Control**, backed by authorized device-control APIs and MCP tools. Reuse and integrate the existing repository at https://github.com/Azrazieliz/Asterion-Comander; do **not** rebuild the Android app or Windows agent and do not depend on Desktop Commander, ADB, or GitHub polling for normal operations. The private GitHub bridge repo (Azrazieliz/Asterion-Control-Bridge) is an **interim fallback**, not a real-time transport.

### Tool interfaces (read + write)
- `list_devices` — list paired Android head and authorized Windows worker, connection/permission/thermal state.
- `get_device_health(device)` — CPU, RAM, storage, battery, charging, thermal conditions, network; unsupported sensors shown explicitly as unavailable.
- `get_screen(device)` — current frame with display dimensions, timestamp, capture status.
- `get_ui_tree(device)` — available Android Accessibility hierarchy or Windows UI Automation tree.
- `input(device, action, coordinates/text/keys)` — authorized tap/swipe/long_press/home/back, mouse/keyboard actions.
- `run_job(device, saved_script_id, args)`, `run_batch`, `job_status`, `stop_job` — deterministic saved scripts, parallel bounded execution and cancellation. Hidden from ordinary user's Control UI.
- `list_applications(device)`, `launch_application(device, package_or_executable)`, `install_signed_artifact` — only with permissions and native OS approvals.
- `connection_status`, `reconnect`, `revoke_session` — Android-authorized connectivity.

### Real-time network architecture
- **Android ↔ Windows:** authenticated persistent encrypted private-network channel (WebRTC screen/video/data channels, or native WebSocket/WSS over a secure VPN). Android initiates/authorizes peer pairing and is the normal UI. Use continuous media streams and batch native input commands, not repeated image downloads or GitHub polling.
- **ChatGPT ↔ Android Control plugin:** authenticated HTTPS/MCP endpoint through a private relay that can reach the Android head without requiring the Android phone to expose a public TCP listener. Commands must be authorized by Android's existing Control permissions. The plugin cannot silently grant Android accessibility, screen capture, background execution or APK install permissions.
- ChatGPT plugin calls are request/response control operations; **continuous on-screen real-time video** is rendered in the native Android Control UI or an approved companion viewer, not presumed to stream inside a plugin-tool response.
- Transport and identity require authenticated device pairing, encrypted traffic, revocation and explicit user approval for sensitive actions; credentials must never appear in public GitHub repositories or the main UI.
- Keep CPU/RAM/thermal load low; batches and UI-tree actions avoid hundreds of screenshots per operation.

## Current implementation and gaps
Existing source includes Android native agent, MediaProjection capture and Accessibility input, Windows FastAPI agent, WebSocket desktop-stream API, LAN discovery and PIN pairing, and a Windows-hosted MCP endpoint. Compiled Android APK v0.8.1: https://github.com/Azrazieliz/Asterion-Comander/blob/main/dist/Asterion-Control-v0.8.1-debug.apk. Android was installed via one-time authorized ADB bootstrap. Android HTTP listener was reachable on LAN (responded 401 without its private token), but Windows reported `paired:false`. The code currently contains **two distinct pairings**: Android→Windows PIN authorization, and Windows→Android phone-agent registration. This was the root of user confusion. Refactor identity so Android authorizes/control sessions and the worker registers its availability to the Android head; do not imply that merely authenticating the Windows agent makes the phone remotely operable. The error toast currently conflates incorrect PIN with network failures; provide explicit diagnostics.
A separate native-Android-to-Windows registration can stay as a compatibility migration only; user should not be asked to coordinate tokens/IPs.

### Acceptance criteria
With USB unplugged and Desktop Commander stopped:
1. Android phone shows and controls the PC desktop and reports PC health.
2. ChatGPT connected to the new Asterion Control plugin can read Android screen/accessibility data and perform a safe user-approved phone input, **via the Android-head channel**.
3. ChatGPT can similarly read/control Windows PC through Android, execute authorized saved scripts, batch operations, and read results.
4. Both devices reconnect across app restarts and network changes without retyping IPs/tokens; secure transport and revocation verified.
5. Continuous live screen stream and input latency measured, not just code compilation/unit tests.
6. Full end-to-end evidence recorded, with honest implemented/verified/blocked status.

## Strict scope restrictions
The plugin is a ChatGPT-facing adapter for Asterion Control. It must not duplicate Asterion Art, Sound, Downloader, Core, Rounder, 3D, or NoWorld engines. The Android app already specifies branding and premium user UI; preserve and refine it, do not replace with a browser or terminal dashboard.
