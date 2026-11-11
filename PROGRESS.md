# 2026-11-11 — Native persistent PC/Android switching and Windows console repair

- **Installed and executed on the actual Windows worker:** the minute watchdog scheduled task `Asterion Control Self-Healing Worker` now runs `wscript.exe //B //Nologo D:\\AsterionControlRelease\\scripts\\control_watchdog_hidden.vbs` rather than opening `powershell.exe` directly. Scheduler reported last result **0**. Existing credentials, watchdog health checks, Android pairing and service were preserved.
- **Live worker command-launch fix:** patched all four subprocess call sites to use Windows `CREATE_NO_WINDOW` on the existing production worker with a pre-change backup. Source equivalent committed as `asterion_remote/app.py` on `work/control-0927-overnight-cycles-20261111`. Safe idle restart completed; worker and phone immediately recovered.
- **Actual window test:** newly spawned Windows worker command returned `{"visible_console":false,"has_console":false}`. This confirms that new Control commands do not allocate a visible PowerShell console. It cannot rule out unrelated third-party console launches.
- **Persistent multi-device real-action acceptance:** owner-authenticated existing Windows worker maintained **two concurrent live WebSockets** for Windows desktop and Samsung. Actions alternated PC mouse move → Android Home → PC restore → Android notifications shade → PC mouse move → Android Back. Both live streams produced frames; **6/6 native actions were acknowledged AND visually/Accessibility/Win32-state verified**, and the pointer was restored. First clean test median command-to-verification **140.4 ms** (slowest 624.8 ms). Post-restart test **6/6**, median **202.0 ms**, slowest **818.7 ms**. Under 1 second per action *inside the worker* in that test. Test source `scripts/accept_persistent_worker_pc_phone.py` on the above branch.
- **Not proven:** ChatGPT's own decision time or ChatGPT→worker link on this chat. A working persistent Windows→PC/Android native connection is not itself proof of the user-required **sub-10-second complete ChatGPT decision/transport/execute/verify cycle**, or **~1-second simple complete interaction**. This session used the GitHub relay as the available ChatGPT→worker fallback. No unattended development cycle was started. Abridged-turn cycle testing is the next owner-requested stage.

---

# 2026-11-11 — v0.9.28 release of 20-message conversation rollover

- Corrected continuous-cycle controller published in owner-signed v0.9.28 from source `6513771`; APK SHA-256 `c74daa7a31323edea1cf780163d23db39ed764ac9586df060563fdb28534f90a`.
- Conversation limit now counts **20 total ChatGPT messages**, not 20 complete work turns: approximately 10 prompt/response pairs. At the boundary, the owner-authorized cycle continues into a fresh *verified* ChatGPT conversation using a canonical project handoff; no global cycle stop.
- Individual action budget <10 seconds including ChatGPT decision and verification; trivial navigation target ~1 second. Each substantial development turn target ~30 minutes, with <25 minutes without meaningful work inadequate. Code cannot force external ChatGPT inference duration, and native input acknowledgments do not prove model decision timing.
- **Verified:** owner-signed APK compiled, original certificate matched, Windows recovery/native suite passed 7/7; APK and update manifests published on commit `234ed5e`.
- **Unverified:** phone installation, actual new-chat landing verification, 20-message turnover, continuous overnight operation, complete ChatGPT-inclusive latency. Do not claim these passed.

---

# 2026-11-11 — Automatic 20-message ChatGPT conversation rollover

- Owner correction: the autonomous development **cycle** remains unbounded across many ChatGPT conversations. Automatically roll over after **20 total ChatGPT messages per conversation**, preserving a canonical repository handoff; do not stop the cycle at that limit. Each work turn aims for ~30 minutes of substantial work; individual actions (including ChatGPT decision time) must remain <10 seconds, trivial native gestures ~1 second.
- Source implementation: persisted `turns_in_chat`, `rollover_count`, `chat_rollover_messages=20`; prior turn is instructed to update exact canonical project handoff; next verified new-chat prompt carries last confirmed checkpoint and progress reference. A new conversation is not inferred from a clicked button or an empty old composer. Protected drafts and unique checkpoint IDs prevent double sends.
- Limitation: actual ChatGPT new-chat greeting availability differs by UI version, and final acceptance of unattended overnight 20-turn rollover has **not** been demonstrated. Verified source and APK build are not on-phone proof.

---

# ASTERION CONTROL — ACTIVE PROGRESS AND EXECUTION STATE (updated 2026-11-09)

This file is the **current operational summary**, not a replacement for the full chronological audit. The full original historical progress record was preserved byte-for-byte as [PROGRESS_HISTORICAL_AUDIT_PRE_WORKER_FIRST_20261109.md](PROGRESS_HISTORICAL_AUDIT_PRE_WORKER_FIRST_20261109.md). Consult that archive for historical implementation details only; earlier connection experiments are not current task instructions.

## Mandatory execution priority

**1. Primary: existing authenticated Asterion Control worker.** When a direct, authorized worker session is truly accessible to a conversation, issue the requested bounded Android/Windows operation directly through that original worker, inspect the actual receipt, then observe the resulting state. Do not invent worker tool names or assume they are exposed merely because this system exists.

**2. Fallback: private GitHub bridge.** If the direct worker is not callable but the connected GitHub interface is available, operate the same worker through `Azrazieliz/Asterion-Control-Bridge` branch `main`. Submit unique `commands/active/<id>.json` via GitHub file creation, retrieve `results/<id>.json` via GitHub file read, and require completed results before marking success. Do not stop to invent or install new connectors, repeat pairing, reset devices, or switch to another control architecture.

**3. If both routes are absent**, report their actual availability separately. An unavailable direct session does not imply the Control application itself is offline when the GitHub fallback can still execute commands.

For owner-requested **"cycle"**, perform actual task work, then operate the normal Android ChatGPT composer with `phone_ui` and `phone_input` through the accessible route; verify a real next ChatGPT message and obey explicit `stop`. The exact verified cycle and rollover procedure is in [the bridge README](https://github.com/Azrazieliz/Asterion-Control-Bridge/blob/main/README.md). A queued command, tap confirmation or legacy cycle endpoint does not establish that a next turn was received.

## Live verification and current limitations

- On 2026-11-09 the GitHub fallback executed `pc_status`, `phone_status` and `phone_bridge_status` with matching results `complete`, `ok:true`. The original Windows worker was operational, Samsung SM-S948B paired and reachable, and its authenticated native phone link connected.
- This specific observation used **Wi-Fi**. It does not prove cellular reachability at the time of a later request. Cellular without home Wi-Fi remains a requirement and should be tested in situ, with real connection status receipts.
- Native operations include Windows commands/input and Android semantic UI/input, subject to actual authorization, foreground and Android permission controls. The GitHub fallback carries execution receipts but not a live streaming video viewer. Do not replace native continuous sharing with screenshot loops.
- Previously verified Android ChatGPT composer cycles 2–4 on 2026-11-07 demonstrated normal-message continuation. Full automated rollover and indefinite continuation were not yet fully accepted.
- Latest Android app/build/install status must be checked against actual current branch, signed artifacts and a live phone receipt. Historic progress records include a v0.9.7 release build and earlier installed-version evidence; neither alone establishes the current installed version or full on-device acceptance.

## Canonical assets, owners and constraints

- Control source: `Azrazieliz/Asterion-Comander`, development branch `work/android-primary-continuation-observation-20261105`. Read [START_HERE_CONTROL_CONTINUATION_2026-11-06.md](START_HERE_CONTROL_CONTINUATION_2026-11-06.md) for the current continuation handoff and [7STAR_FROZEN_MASTER.md](7STAR_FROZEN_MASTER.md) for the preserved core requirements.
- Private worker fallback: `Azrazieliz/Asterion-Control-Bridge`, branch `main`. Use the existing original authenticated Windows worker `LAPTOP-1LI4VRCJ` and Samsung `SM-S948B`, Android 17.
- Native Android application: `com.asterion.control`. Preserve application data, original signing identity, device pairing, keys, credentials, settings, working Windows processes and all other installed applications.
- Samsung is primary, Windows subordinate. No forced home-Wi-Fi dependence, payment, Work-mode replacement or ordinary-operation USB/ADB requirement.
- ChatGPT decides each operation and judges returned receipts. Control remains a deterministic executor, not an autonomous decision-making model.
- Keep verifiable acceptance categories separate: source implemented, tests passed, APK built, APK delivered, APK installed, device command completed, functional behavior verified.
- Never uninstall/re-pair, reset credentials, invent completed actions, or undo prior approved project work because of a missing conversation-specific action.

## Historical audit

The prior 60,890-character chronological progress record was copied **unchanged** to [PROGRESS_HISTORICAL_AUDIT_PRE_WORKER_FIRST_20261109.md](PROGRESS_HISTORICAL_AUDIT_PRE_WORKER_FIRST_20261109.md). It retains original technical filenames, implementation steps, tests, revisions and timestamps for traceability. It is not a current execution-routing specification. Do not run historical setup tasks merely because they appear in that archived record.

**Current handoff instruction:** execute using the direct original worker if genuinely available; otherwise immediately use the verified private GitHub fallback, then continue the owner's actual task.
