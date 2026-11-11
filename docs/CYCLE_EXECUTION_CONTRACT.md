# Asterion Control — real ChatGPT development cycles

**Authoritative 2026-11-11.** A cycle is a real external ChatGPT work/reply/checkpoint iteration, *not* a GitHub Actions workflow, an on-phone AI, a PC-only script, a queued command, or a simulated answer. Existing authenticated direct Windows worker + native WebSocket is the primary Control transport; the private GitHub bridge is contingency only.

## Sequence

1. The owner requests a continuous continuation on a named project and canonical requirements, optionally choosing a turn limit. Zero means unlimited turns. The cycle continues until finished, stopped, or paused for review. The phone owner explicitly enables continuation; otherwise no cycle runs.
2. The external ChatGPT operator actually investigates/implements/tests the next unit of work using available tools. Source commits are distinguished from APK build, phone installation and on-device acceptance.
3. A durable checkpoint gets a unique ID and the exact canonical source reference. Control only sends the next message into the real Android ChatGPT composer when the foreground app is ChatGPT, the draft is demonstrably empty, and input/Send can be verified. A tap acknowledgment **does not** count as a reply.
4. The next normal ChatGPT reply must end with exactly one unique marker built by appending the checkpoint ID to prefix `ASTERION-CYCLE-ACK:` when more verified work remains, or to `ASTERION-CYCLE-DONE:` only after all requested work and acceptance are complete. The outbound prompt intentionally never contains an already assembled full marker. This prevents observing the user's own prompt as a false reply.
5. Android Accessibility waits until the marker is visible in the assistant reply and generation has stopped, then holds for a stable quiet interval before acknowledging it. Only then may the next checkpoint start. Missing or uncertain evidence is **not** silently retried.
6. Pause/stop prevents further sends, but cannot retract an already-sent message. Existing drafts are never overwritten; changes to foreground, keyboard, message status, permissions, network or chat destination may require review.

## Bounds

- **No artificial cycle length or turn limit.** A cycle is potentially indefinite across as many verified turns and safe chat handoffs as needed. `max_cycles=0` means unlimited; a positive `max_cycles` is an optional owner-selected cap.
- **Substantive work:** a single ChatGPT development turn may take around **25–35 minutes**, roughly **30 minutes** when appropriate to the amount of required work. Do not force a development turn to end after seconds or a few minutes just to look fast.
- **Individual operations:** *every* action inside or outside a cycle must target **less than 10 seconds end-to-end** from the need/observation to decision, API command, execution and result verification. Simple navigation or API operations (e.g. ChatGPT to Android Home) target **about one second**. These action targets do not shorten the overall development turn.
- **Measure real action duration:** decision time, command creation, transport, execution and verification must all be included. A 69 ms device acknowledgment after a minute of reasoning is a failing action. The GitHub fallback cannot be described as real-time when its external relay exceeds the target; prefer the existing native persistent worker/WebSocket when directly callable.
- An end-to-end action over the target is a performance failure to record and optimize; never pretend that a server execution metric alone satisfies it.
- Starting a new chat or rolling over is not automatic proof of a successful handoff. The app must verify the right ChatGPT composer and a canonical context/reference before dispatch.
- An observed response marker is **not evidence** of a successful code build or finished APK. Source, tests, artifacts, installed version and on-phone behavior require separate receipts.
- Cycle count, latest checkpoint, last error, active/paused/review state are visible via the **How development cycles work** dialog in Asterion Control v0.9.26 (once installed).
- If the external ChatGPT tool session lacks a direct worker connector, actions fall back to the existing GitHub queue. The backend does not become real-time simply because the Windows execution takes milliseconds. Measure end-to-end observation-to-act-and-verify time.

## Acceptance status

The v0.9.26 cycle marker and bounded-counter code was compiled with the owner signer; the local Windows native/recovery tests passed **7/7**. This is not an attended or unattended real end-to-end cycle acceptance: installation, permissions, actual reply marker observation and multi-turn rollover still require phone testing. Never claim those stages completed from build or command receipts alone.
