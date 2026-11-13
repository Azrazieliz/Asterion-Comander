# 2026-11-13 — Windows Control command relay dirty-receipt recovery guardrail

- **Confirmed failure:** a locally modified tracked `results/*.json` receipt blocked `git rebase origin/main` with `cannot rebase: You have unstaged changes`. The Windows API on port 8911 remained healthy while the relay supervisor repeatedly relaunched the failing worker.
- **Permanent source fix:** `asterion_remote/github_bridge_git.py` now checks raw porcelain output before every fetch/rebase, validates result identity/status, saves each exact receipt in a content-addressed local recovery directory, commits only valid receipt journals for publication, and fails closed on unrelated tracked changes or invalid receipts. It deliberately preserves incomplete untracked `.pending` journal markers without interpreting or deleting them. Existing pairing, WSS and Windows API remain unchanged.
- **Actual Windows deployment:** deployed into the existing `D:/AsterionControlRelease` Python worker with backed-up originals under the existing LocalAppData AsterionControl state. Windows source install was automatically rolled back on failing early regression runs; the final revision passed **4/4 isolated Git-repository regression tests** before being left installed.
- **Live recovery evidence:** following a controlled bridge process restart, the new guardrail created and published a `Recover durable local Asterion Control result receipts` commit for the exact Adaptive Study result previously responsible for the startup failure. A subsequent read-only `pc_status` returned `ok=true`, confirming restored command transport and Windows API responsiveness.
- **Scope:** Windows command relay only; no Android APK/signature, app data, credentials, native WSS pairing, or persistent owner files were changed. Asynchronous transfer acceptance is not proof of completed APK delivery.

---

# 2026-11-11 — Owner-approved two-turn Control app-switch test, TURN 1

- **Source branch:** `work/control-0927-overnight-cycles-20261111`. Canonical detailed real-test report: [docs/CYCLE_ABRIDGED_APPSWITCH_ACCEPTANCE_20261111.md](docs/CYCLE_ABRIDGED_APPSWITCH_ACCEPTANCE_20261111.md), report commit `4dcf2a9`; source recovery helper `scripts/restore_chatgpt_from_control.py`, commit `61df73d`.
- **Actual installed device verified:** `com.asterion.control` reports **versionCode 928**, Samsung Android 17 paired/reachable; Windows worker available. Initial ChatGPT Accessibility foreground verified, then actual Control foreground verified. Direct worker connector was not callable in this conversation; real actions used the documented private GitHub bridge.
- **First script test:** `accept_cycle_app_switch.py` worker job `c2261ab7d67e4411b9296cf6e45b1b5c` exited 1 because Control was already foreground at script start: `CHATGPT_NOT_FOREGROUND_com.asterion.control`. This is a strict precondition defect, not successful app-switch acceptance.
- **Capture test:** Control header `SHARING ON` contradicted native `capture:false` and `direct_mcp.connected:false`. Real `Start screen sharing` tap ACK 141 ms opened Android SystemUI MediaProjection `Share one app` consent. Mode-control taps ACKed 134/183 ms but did not change the observed mode; no permission was granted and no live video frames proved. Dialog dismissed with Back, ACK 172 ms.
- **Real recovery verified:** using Control `/apps/launch`, new Python helper returned ChatGPT foreground (worker job `1d367a1b8e35402c9966fab7c69a980c`, exit 0; native launch request 194.1 ms); independent Accessibility `final-ui` confirmed `com.openai.chatgpt`, editor `draft_empty:true`, receipt 94 ms. **No ChatGPT send/replay was performed.**
- **Status:** TURN 1 partial, TURN 2 pending. Source committed and Windows-executed; signed v0.9.28 already published and installed version 928 observed; cross-app continuous capture, direct connector, end-to-end SLA, duplicate-free second-turn continuation, full rollover and overnight operation remain **unverified**. The owner's short two-turn test does not relax ordinary unbounded-cycle production requirements.

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
