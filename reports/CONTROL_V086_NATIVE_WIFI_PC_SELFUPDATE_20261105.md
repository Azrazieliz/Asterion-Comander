# Asterion Control — persistent sessions, PC control, Wi-Fi file transfer and updater
Date: 2026-11-05

## Architecture
- Android Samsung is the primary controller. Windows is the subordinate PC worker.
- GitHub remains repository/source control and a *temporary ChatGPT command-launch fallback*, NOT the native Wi-Fi file/video/input data path.
- Direct HTTPS MCP gateway has previously passed 12/12 requests and 173.3-ms median status round-trip under load, but **the plugin's direct tools have NOT loaded into the current ChatGPT runtime**. ChatGPT-to-device per-command transport is not yet fully converted.
- Asterion Control Windows worker exposes a bounded persistent session engine: `POST /api/v1/sessions`, `GET /api/v1/sessions/{id}`, and cancel. Each session runs its fully authorized steps locally without returning to ChatGPT between gestures; latest source adds observed Windows title assertions.
- Windows transfer API `POST /api/v1/phone/transfers`, status, and cancel. The Android native agent receives authenticated file chunks, verifies SHA-256, commits into Android MediaStore Downloads only upon validation.

## Android build and installation
- v0.8.5 compiled (225,277 bytes) and installed through owner-authorized ADB bootstrap.
- v0.8.6 compiled (238,681 bytes, SHA-256 `950c0ff4a60886b4a617a66890c9a2965ec313916a356aeec344b24d0995ab94`) and installed (ADB install returned `Success`).
- v0.8.6 adds native device-screen controls: **Check for Asterion Control updates** and **Install an APK from Downloads**. Update index is `dist/latest.json`; manifest URL/size/checksum validated, HTTPS download SHA-256 checked, then Android's native package installer asks user approval. `REQUEST_INSTALL_PACKAGES` declared and app directs owner to Android unknown-source authorization if required.
- User-initiated APK installer handoff **has not yet passed a complete new-version self-update acceptance test**. Android approval cannot silently be bypassed. ADB is not required by the implemented Wi-Fi transfer or APK install flows after v0.8.6 is installed.
- After v0.8.6 install native Control reported phone `paired:true`, `reachable:true`, `accessible:true`, `capture:false`. The latter is Android MediaProjection requiring new user grant, not a loss of native transport.

## PC persistent interaction actual result
- Initial 10-step session completed in **3,282.7 ms**, screenshot 71,227 bytes; this acknowledgment alone **did not visually verify** intended Notepad app launch.
- A separate Control-only Windows Win-key test produced a screenshot of the actual Start menu (verified visually).
- Actual Notepad was then opened from Windows Start through Control. Notepad displayed an error dialog about a missing path; that dialog was dismissed.
- Corrected local persistent PC session: **8/8 steps completed in 2,644.2 ms**, including Enter to dismiss, Ctrl+N to create a new tab, typed text, wait, capture, health. Native PC screenshot visually verified the new Notepad tab displays the text `ASTERION CONTROL - WINDOWS APP DEMONSTRATION`, `Controlled from ChatGPT with one local multi-step session.`, and `no GitHub round trip between keys. Hekko Workd !` (typing deviations visible in screenshot). This is real input, not a simulated ack, but typing accuracy needs follow-up.
- Screen capture and key actions were executed through Asterion Control. No ADB or Desktop Commander used for acceptance.

## PC -> Android native Wi-Fi transfer verified
- Original harmless text probe: **149 bytes**, **212 ms**, SHA-256 matched Android receipt, location `Downloads/Asterion Control/Asterion-Control-WiFi-Proof.txt`.
- Signed app APK delivery probe: **238,681 bytes**, **439.7 ms**, all bytes received and SHA-256 matched Android receipt, location `Downloads/Asterion Control/Asterion-Control-WiFi-Delivered-v0.8.6.apk`.
- Both transfers were PC -> Samsung directly over authenticated private Wi-Fi; no GitHub/ADB carried the file bytes. The APK was delivered, not silently installed; package installation requires the owner's Android approval.
- Not yet validated: multi-GB file throughput, interruptions/resume, timeouts, collisions, complete GUI self-update upgrade, 30-minute Android idle recovery.
- 90-second native video soak performed earlier: 1,168 frames in 90 s, delivered 13 FPS at 18 requested, median frame interval 73.1 ms, Home acknowledgement 18.8 ms and no stream errors. Video FPS needs improvement; ChatGPT turn intervals remain limited by missing direct plugin MCP tool linkage.

## Operational follow-up
- **No more routine ADB** after installing v0.8.6; the native Android app handles APK receipt and user-approved installer requests.
- Open Asterion Control -> Devices -> App updates & installation -> Check for Asterion Control updates, or Install an APK from Downloads. The latter can pick any user-selected APK; Android must confirm installation.
- Open My Files -> Downloads -> Asterion Control to see verified transfer artifacts.
- For live video after a package update, the owner must re-grant Android screen sharing; native input and file transfer do not depend on screen sharing.
- Replace temporary Cloudflare Quick Tunnel with stable protected gateway and finish account-level direct MCP tool connection; keep source control separate from device commands.
