# Asterion Control native WSS recovery — 2026-11-12

## Verified incident
- Existing private GitHub bridge, Windows worker (LAPTOP-1LI4VRCJ), paired Android SM-S948B and native Android Accessibility remained operational.
- Phone native WSS reported `wss_upgrade / WSS handshake rejected`; relay access logs showed repeated HTTP 403 for `/phone/live`. No re-pairing or new gateway was required.
- A manually induced restart of the **specific existing SSH forwarder** alone did not clear the 403. A guarded restart of the local native WSS relay on 8995 did: it logged `WebSocket /phone/live [accepted]`.
- Afterward a real `phone_bridge_status` reply returned `connected=true, phase=connected`; relay health returned `phone_connected=true`; a read-only `phone_ui` produced a live Accessibility tree.
- The native supervisor lock initialization independently failed with `PermissionError: [Errno 13] Permission denied` upon reading a byte while another supervisor already held the Windows byte lock. Existing supervisor and SSH processes had been present; early zero-process diagnostic was false due to an incorrect regex.
- An early Windows PowerShell public-health probe showed HTML, but a proxy-free Python HTTPX probe returned the expected native relay JSON; do **not** conclude that the external forwarding hostname was down based on that PowerShell probe.

## Permanent source / installed repairs
1. Commit `b274b740be30e68f9182a3af784c688b34d78a3d` replaces the lock-file byte read with `os.fstat` for size checking before `msvcrt.locking`. Existing original installed file was backed up. Python `py_compile` passed.
2. Commit `7f0a12c8093043e75b2859df6b6975b6414a8d38` adds native WebSocket handshake failure self-healing to the existing once/minute `Asterion Control Self-Healing Worker`: only when the paired phone is reachable and reports a repeated `wss_upgrade / WSS handshake rejected` state, and the local relay reports no connected native phone, restart only the exactly verified native WSS relay after two consecutive failed checks. It leaves pairing, original SSH key, installed Android APK and unrelated processes unchanged.
3. Deployed the watchdog file to `D:\AsterionControlRelease\scripts\control_repair_watchdog.ps1` after verifying the downloaded canonical commit against the installed original and PowerShell parse. Saved a backup in existing `%LOCALAPPDATA%\AsterionControl` state.
4. Brief sanitized auth logging was used to locate server 403 errors, then the original native handler file was restored on disk without interrupting the now connected session.

## Acceptance / limitations
- Installed watchdog manual execution: exit 0, local native health `ok=true`, `phone_connected=true`, failure counter `0`, Python syntax valid. Read-only Android UI response succeeded.
- No forced recurrence test of a 403 was performed after service restoration, so the automatic restart-on-future-outage behavior is **implemented and script-validated**, not proven by an induced production failure.
- The original private bridge README remains the operational contract. No MCP gateway, connector installation, ADB workaround, pairing reset, or Android APK replacement was used.
