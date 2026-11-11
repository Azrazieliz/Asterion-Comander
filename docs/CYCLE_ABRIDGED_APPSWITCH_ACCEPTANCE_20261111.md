# Owner-approved abridged two-turn app-switch acceptance — 2026-11-11

Checkpoint: `control-abridged-appswitch-20261111-1`  
Contract: `docs/CYCLE_EXECUTION_CONTRACT.md` (7*).  
Status: **TURN 1 PARTIAL; TURN 2 PENDING.** This is the owner's two-turn exception; it does not change the ordinary unbounded ~30-minute development turn contract.

## Evidence and transport

- Source: `Azrazieliz/Asterion-Comander` branch `work/control-0927-overnight-cycles-20261111`.
- Direct authenticated Asterion Control tool **not exposed** in this ChatGPT session. Existing GitHub bridge fallback `Azrazieliz/Asterion-Control-Bridge` `main` was used to operate the **real original Windows worker and Samsung**, not a simulated session. This relay does not let ChatGPT consume the native continuous video stream.
- Worker `LAPTOP-1LI4VRCJ` operational, worker capability listing includes native Android agent/live WebSocket. Phone `SM-S948B`, Android 17, paired/reachable, Accessibility enabled.
- Published signed v0.9.28 exists per canonical release documentation. **Installed v0.9.28 (versionCode 928) is now independently seen in the actual Control Android UI.** This does not prove the entire cycle feature works.
- No ChatGPT composer send, message replay, re-pair, uninstallation, phone data clear, or OS permission bypass occurred during this turn.

## Turn 1 — actual command/result receipts

All result paths below are in private bridge `results/<id>.json`, where each id begins `control-abridged-appswitch-20261111-1-t1-`. The `elapsed_ms` values are **worker/bridge execution times**, not ChatGPT-inclusive observation-to-verification times.

| Step and receipt id suffix | Device- or worker-confirmed outcome |
|---|---|
| `ui01` | `complete, ok:true`; foreground `com.openai.chatgpt`; elapsed **85 ms** |
| `pc01` | `complete, ok:true`; `LAPTOP-1LI4VRCJ` worker; elapsed **9 ms** |
| `switch01` and `job01` | Real existing `accept_cycle_app_switch.py` job `c2261ab7d67e4411b9296cf6e45b1b5c` accepted (**26 ms**) then finished **exit 1**. Root cause: strict ChatGPT-foreground precondition failed because `com.asterion.control` was foreground at actual script start. No native switch steps were run by that script. |
| `ui02` | Actual Control UI foreground; header says `SHARING ON`, but text says `Native screen sharing stopped; Android approval required`. Installed app reports `version code 928` and has a visible `Start screen sharing` control. |
| `status01` | `complete, ok:true`, **53 ms**; Samsung paired/reachable, Accessibility true, `capture:false`; `direct_mcp.connected:false`, phase `stopped`. |
| `stream01` | `error: Unsupported operation`; this bridge operation is not available even though it was named in older bridge documentation. No live stream receipt. |
| `share-tap` | Visible `Start screen sharing` tapped, `complete, ok:true`, **141 ms**. Real Android SystemUI MediaProjection consent appeared. |
| `consent-ui` | SystemUI dialog `Share your screen with Asterion Control?`; default spinner `Share one app`, buttons `Cancel` / `Next`. |
| `share-mode`, `mode-arrow` | Spinner tapped via grounded bounds; native input receipts `ok:true` at **134 ms** and **183 ms**, but follow-up Accessibility UI still showed `Share one app` with no `Entire screen` selection. These ACKs do NOT prove consent or a mode change. |
| `consent-back` | Back `complete, ok:true`, **172 ms**; follow-up UI was Samsung launcher. No MediaProjection permission granted. |
| `restore-job`, `restore-status` | Ran newly committed `scripts/restore_chatgpt_from_control.py` on real Windows worker. Job `1d367a1b8e35402c9966fab7c69a980c` finished **exit 0**. Script verified Control foreground, used actual `/apps/launch` for `com.openai.chatgpt`, received `intent_dispatched:true`, and verified ChatGPT foreground. Launcher request measured **194.1 ms within worker**. |
| `final-ui` | Independent `complete, ok:true` Accessibility result: foreground `com.openai.chatgpt`, keyboard active, `draft_empty:true`; **94 ms**. No duplicate send. |

## Implemented / built / installed / phone-verified

- **Source committed this turn:** safe, bounded `scripts/restore_chatgpt_from_control.py`, commit `61df73da0b9d8bd842ac2bcd081e042b257445f9`. It verifies Control then returns to ChatGPT through the existing Control Android launcher. It neither sends ChatGPT messages nor approves screen sharing. **Windows execution passed with exit 0**.
- **APK built/published this turn:** none; existing v0.9.28 is already published.
- **APK installed:** device Control UI states version code 928.
- **Phone verified:** Control foreground observed; Android consent prompt actually opened; ChatGPT successfully restored using the real Control app-launch path and independently reobserved.
- **Not verified:** active MediaProjection, fresh continuous video frames, direct ChatGPT-facing native worker tool availability, full 10-second end-to-end interaction SLA, two-turn continuation, no-duplicate second-turn sends, 20-message rollover, overnight endurance.

## Defects and acceptance gate

1. `accept_cycle_app_switch.py` treats a valid Control foreground at entry as fatal instead of resuming safely; source repair candidate is a foreground-aware entry state machine.
2. Header `SHARING ON` contradicts current native `capture:false` and the app's own `Native screen sharing stopped` explanation.
3. MediaProjection permission dialog defaulted to app-only sharing; Spinner native ACK did not yield an observed mode change. Do not bypass Android consent or count a single JPEG/status flag as continuous frames. The owner may need to confirm or choose full-screen sharing in SystemUI if Accessibility cannot operate that protected dialog.
4. Private bridge `phone_stream_status` returned Unsupported operation; direct ChatGPT worker tool not exposed. Native WebSocket was stopped at the observed moment.
5. GitHub transport is a slow fallback. Its per-command worker ACKs cannot establish the requested ChatGPT-inclusive latency.

**Turn 2 criteria:** inspect the actual Samsung cycle state, the exact receipts above and any new real response; verify the correct next-turn count and absence of duplicate sends; obtain live frame receipt if Android consent becomes available without bypass; update this report with independent proof. DONE only when all prescribed two-turn acceptance steps pass; otherwise ACK with precise blockers. Do not submit an extra ChatGPT composer message manually merely to force acceptance.
