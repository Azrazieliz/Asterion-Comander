# Asterion Control — frozen-master compliance and production-readiness audit
Date: 2026-11-06
Scope: Asterion Control ONLY, compared to 7STAR_FROZEN_MASTER.md and the established Android-primary/ChatGPT-as-operator continuation requirements.
Canonical branch: work/android-primary-continuation-observation-20261105; PR #1. No changes to the frozen master, Asterion Sound, Pilot, Art, Core, Downloader, NoWorld, or other app engines.

## Standard for the word "complete"

"Implemented in source" is not "installed", "connected", "executed", or "accepted on-device". Asterion Control is only complete after an original-signer-compatible Android update is installed without data loss, ChatGPT actually invokes authenticated Control tools, Android and PC operations work through Control itself, and recoverable long-running jobs survive network/client failures with verified exit receipts. No Desktop Commander or ADB should be needed during ordinary use after first-time OS/device authorization. Android package-install, Accessibility, capture and microphone consent requirements cannot be silently bypassed.

## Matrix against frozen master

| ID | Original requirement | Evidence in preserved source | Status / unclosed condition |
| --- | --- | --- | --- |
| C01 | Phone is principal; independent Windows/Android agents | MainActivity, AgentService, asterion_remote/app.py | Source exists; owner-confirmed Samsung v0.8.6, new v0.8.8 not installed |
| C02 | Replace Desktop Commander, not wrap it | Control Windows REST and native Android MCP/REST; own private Git transport | Architecture independent; ChatGPT cannot currently invoke a live Control connection |
| C03 | Windows optional, no permanent USB/ADB | AndroidMcp, AgentService, optional PhoneGitBridge | Native phone agent exists in uninstalled code; native Git fallback needs separately owner-entered repo-scoped credential; Windows still needed for original-key APK signing |
| C04 | Wireless encrypted local and cross-network access | Android private IP/bearer HTTP, Windows private IP/bearer HTTP; temporary tunnel gateway | **FAIL**: direct LAN HTTP is not encrypted. Stable authenticated HTTPS ingress for direct ChatGPT MCP is not live |
| C05 | Low-latency live two-device visual observation | Android CaptureService/stream; Windows live_stream WebSocket | Implemented, but sustained Samsung/live-PC frame rates and reconnect behavior not device-accepted |
| C06 | Native Android UI state, gesture/app control | AccessibilityService, AppCatalog, AndroidMcp | Source implemented; OS Accessibility authorization and real device execution still required |
| C07 | PC files, apps, terminal, processes, input | asterion_remote/app.py and control_services.py | Substantial PC API source implemented; no current live Control worker or full acceptance run |
| C08 | Phone files, apps, processes, logcat, audio/video | Phone native apps, UI, screen, observation, voice, transfers | **PARTIAL**: no equivalent complete phone-native filesystem/process/logcat management suite or continuous bidirectional audio stream |
| C09 | Builds, APK update, original app/data preserved | Owner-key build script, UpdateManager, native Wi-Fi transfer | **FAIL**: CI APK uses incompatible signer; no owner-key v0.8.8 deliverable/receipt; v0.8.6 remains installed |
| C10 | Saved parameterized routines, parallel jobs and cancellation | control_services, interaction_sessions, Windows command API | Partial; volatile Windows in-memory command registry cannot recover all job states after server crash |
| C11 | Client disconnect resilience and hands-off recovery | Windows launcher/bridge supervisors, Android RestoreReceiver/foreground AgentService | Source recovery improved; not live tested. A stopped/unprovisioned worker cannot bootstrap itself through its own dead connection; OS restrictions still apply |
| C12 | ChatGPT direct authenticated MCP control | AndroidMcp, mcp_protocol, mcp_gateway, private plugin v1.6.1 | **FAIL**: publishing a plugin or server source is not an authenticated live ChatGPT connector; no direct Control tool exposed in this chat |
| C13 | Minimal runtime, controlled permissions | Python Windows worker, Java Android agent, private bearer auth | Source partially meets; no proven sustained RAM/network/thermal acceptance; private HTTP does not meet encryption requirement |
| C14 | Truthful CPU/GPU/RAM/storage/battery/thermal/IO/network health | MainActivity metrics, AgentService.health, control_services.host_health | Partial, OS-exposed sensors only; GPU/IO precision and long-run accuracy unverified |
| C15 | ChatGPT-only scripts/terminal/logcat, simple owner UI | Native MainActivity panels and hidden PC API | Mostly represented in Android UI source; actual owner-app separation and usability not fully device accepted |
| C16 | Cross-project integration without reimplementing engines | Separate repositories; app discovery/launch and scripts | Separation preserved; invocation coverage across every Asterion app not tested |
| C17 | Voice exchange without embedded AI | VoiceDialogueService, AndroidMcp | Opt-in TTS and single-turn speech recognition code, not full always-on conversational assistant; no real Samsung acceptance |
| C18 | Continue ChatGPT projects through existing/new conversations | ContinuationLedger and guarded Accessibility clicks | **FAIL as full autonomy**: a click is 'submitted_unverified'; no end-to-end response acknowledgment and subsequent automatic ChatGPT iteration proven |
| C19 | Real app-observation record for Asterion Pilot | AppObservation retained frames, timeline and frame MCP tools | Bounded observational evidence code exists; not Pilot's actual autonomous gameplay, no cross-app acceptance |
| C20 | Failure handling with provable receipts | Private Git queues, Android encrypted credential, Windows job ledger | Earlier code incorrectly treated job acceptance/failed Android actions as success; patched in continuation source but no device execution evidence |

## Concrete defects fixed in this audit branch

1. Removed single-router Windows address assumptions from the native Windows bootstrap, private Git bridge and restart tool. The native Windows agent writes its selected private endpoint into local Control state.
2. Added an independent Windows agent restart loop; the private Control transport keeps its own supervised/restartable worker and refuses duplicate workers.
3. The PC private command queue now probes native Control health BEFORE recording/consuming a new queued owner command. Offline commands remain pending.
4. Asynchronous Windows shell jobs now receive 'accepted' first; a later actual exit-code observation is required for 'complete'. Process/worker loss becomes 'uncertain' without replaying dangerous side effects.
5. The Android private fallback no longer reports a native action returning {"ok":false} as successful completion.
6. The MCP gateway no longer assumes a specific Windows IP or requires the Windows agent to be configured for phone-only startup.
7. Protected original-key signing and app-data preservation; no substitute signer, forced uninstall, silent install or new app engine.

## Not fixed by compilation

- Live ChatGPT-to-Control authentication and stable HTTPS ingress are NOT active.
- The owner-signer-compatible v0.8.8 APK is not available, and the Windows native Control bridge has not returned its build/transfer receipt.
- Android requires user approval for installation from a non-store source, and separate consent for Accessibility and screen/microphone capture as applicable.
- Android v0.8.8 cross-app control, long idle, reboots, network migration, transfer, continuation and observation still need device receipts.
- Full phone files/process/logcat capabilities, fully durable PC job supervision after a host crash, complete encrypted remote transport, continuous audio, and Asterion app-by-app acceptance remain open.
- These gaps are NOT silently called completed or downgraded to optional.

## Acceptance protocol / evidence required

| Gate | Required evidence | Actual |
| --- | --- | --- |
| A | Source/CI tests and native Gradle APK build | CI tested; updated build to be checked against latest branch head |
| B | Original v0.8.6 signing identity exactly matches published v0.8.8 APK | Not demonstrated |
| C | Owner-approved Samsung in-place update preserves user pairing/data | Not demonstrated |
| D | ChatGPT invokes live native phone and Windows Control tools (not another remote plugin) | Not demonstrated |
| E | Native job accepted, exits, result receipt verified; stop/resume and crash uncertainty tested | New source tests, not live |
| F | Android consented UI, gestures, screen, app launch, transfer, resource metrics, voice | Not demonstrated on v0.8.8 |
| G | Phone-only behavior with PC off and network changes, login/reboot recovery | Not demonstrated |
| H | Authenticated encrypted remote path, revocation and privacy assurance | Not complete |
| I | Continuation sends one real ChatGPT turn, observes reply, acknowledges it and resumes correctly | Not demonstrated |

Do not close this audit or mark Asterion Control production complete until all required gates have observed receipts. No requests for arbitrary owner-side setup steps are generated from the audit.
