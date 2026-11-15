# Asterion Control v0.9.32 — actual Samsung and Windows acceptance audit

Date: 2026-11-15 (Europe/Paris). Device: Samsung SM-S948B, Android 17.
Development branch: `work/control-0927-overnight-cycles-20261111`.

## Verified working (live)
- Paired native Control listener returned reachable, authenticated `remote_transport.connected=true` and `validated=true`, Accessibility enabled and screen capture active. Native UI opened from Samsung app drawer using existing authorized input.
- Native Home/Health/Screen navigation worked. Web Screen refreshed and loaded the existing Windows UI with a Diagnostics tab. Windows endpoint `/api/v1/health` returned 200.
- Native Health > **Review recorded Asterion app incidents** opened and returned a read-only snapshot: 15 Windows-side diagnostic events from 1 instrumented app over last 24 hours, no classified symptoms and current runtime state explicitly NOT VERIFIED.
- Native Health > **Inspect recent Control incidents** returned two local Control service events, one authenticated WSS connection, and 12 Android historical process exits. Local journal and historical exit reporting both function.
- Health displayed battery, temperature, RAM, storage, network, thermal moderate and performance governor. Real Windows CPU/RAM panel populated.
- Security choices dialog displayed normal, owner-approved developer 60-minute mode, lockdown and custom without changing selection. Current security level remained normal.
- Native VPN details displayed WireGuard OFF, configuration not stored, Android VPN route not active, full-tunnel approval false. We did not import or enable a VPN.
- Windows HTTP runtime: diagnostic triage, snapshot, phone health, performance, security, permissions, voice status, phone cycle status, network status, app-bridge catalog all returned 200.
- Native voice status route returned 200 but voice is currently disabled. App integration catalog returned only one integration.
- The installed UI contains the v0.9.32-specific **Review recorded Asterion app incidents** entry. This identifies the updated UI, though the package manager version code was not independently read.

## Verified failures and gaps
1. `GET /api/v1/intelligence/cycles` returned HTTP 404 on the installed Windows service.
2. `GET /api/v1/phone/diagnostics/vpn` returned HTTP 404 on the installed Windows service despite the native VPN read-only dialog working.
3. Read-only inspection of `D:/AsterionControlRelease/asterion_remote` confirmed `control_ai_routes.py` absent, `app.include_router(control_ai_router)` absent and `/phone/diagnostics/vpn` absent from deployed native routes; the diagnostic router is mounted. These are concrete deployment/integration omissions, not evidence of broken phone permissions.
4. Cross-app diagnostics currently reflect **one instrumented application** only; no per-app engine-level request trace/worker/queue evidence was returned. It cannot establish the root causes of failures in Downloader, Art, Core or other uninstrumented apps.
5. Local crash dialog displays numeric Android exit reason codes without human-readable interpretation or corresponding app-specific remediation.
6. UX: Home is long and congested with connection, recovery, voice, app access, files, updating and privacy controls; Health hides the new diagnostics. The embedded Windows Screen duplicates native navigation (Computer/Phone/Diagnostics within Home/Screen/Health/Connect), creating two command surfaces.
7. Extended VPN service capability, true local model inference, independent development cycle execution, voice microphone functionality and partner app integration were **not** established by this test. Native VPN is OFF, voice disabled, backend AI cycle route absent.
8. Connect page could not be completed: owner foreground switched to AsterionCore while inspecting; testing stopped to avoid disrupting concurrent work. This is **not** evidence of a Connect failure.

## Non-destructive policy and acceptance boundary
- No installer, uninstaller, permissions, pairing, security level, VPN, microphone, user data or model assets were changed.
- Tests used the existing private GitHub command/result bridge, native Accessibility and the authenticated Windows read-only endpoint probes.
- Runtime diagnostic endpoint 200 establishes that the endpoint responded; it does not independently prove correctness of every underlying feature.
- No claim that complete V3/V5 Control functionality is implemented or accepted. The v0.9.32 release is a **working diagnostics increment**, not a complete general-purpose Asterion Control release.

## Immediate repair order
- Deploy/mount the existing validated `control_ai_routes.py` and updated `native_routes.py` through a coordinated, regression-tested Windows rollout, preserving signer, pairing, data and existing native WSS.
- Independently test the native phone and Windows endpoint side of each capability before claiming it visible/working.
- Integrate actual opt-in partner-app instrumentation and per-operation evidence instead of cross-app claims based on Control-only events.
- Redesign native information architecture to unify duplicate command/navigation layers, surface new capabilities directly, and replace opaque diagnostic text dialogs with actionable per-app screens. Preserve all existing functionality during consolidation.
