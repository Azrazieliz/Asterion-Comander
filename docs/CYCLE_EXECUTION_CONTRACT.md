# Asterion Control — real ChatGPT development cycles

**Authoritative 2026-11-11.** A cycle is a real external ChatGPT work/reply/checkpoint iteration, *not* a GitHub Actions workflow, an on-phone AI, a PC-only script, a queued command, or a simulated answer. Existing authenticated direct Windows worker + native WebSocket is the primary Control transport; the private GitHub bridge is contingency only.

## Sequence

1. The owner requests a bounded continuation on a named project, its canonical source/requirements and allowed number of turns. The phone owner explicitly enables continuation; otherwise no cycle runs.
2. The external ChatGPT operator actually investigates/implements/tests the next unit of work using available tools. Source commits are distinguished from APK build, phone installation and on-device acceptance.
3. A durable checkpoint gets a unique ID and the exact canonical source reference. Control only sends the next message into the real Android ChatGPT composer when the foreground app is ChatGPT, the draft is demonstrably empty, and input/Send can be verified. A tap acknowledgment **does not** count as a reply.
4. The next normal ChatGPT reply must end with exactly one unique marker built by appending the checkpoint ID to prefix `ASTERION-CYCLE-ACK:` when more verified work remains, or to `ASTERION-CYCLE-DONE:` only after all requested work and acceptance are complete. The outbound prompt intentionally never contains an already assembled full marker. This prevents observing the user's own prompt as a false reply.
5. Android Accessibility waits until the marker is visible in the assistant reply and generation has stopped, then holds for a stable quiet interval before acknowledging it. Only then may the next checkpoint start. Missing or uncertain evidence is **not** silently retried.
6. Pause/stop prevents further sends, but cannot retract an already-sent message. Existing drafts are never overwritten; changes to foreground, keyboard, message status, permissions, network or chat destination may require review.

## Bounds

- **Existing chat:** at most **10 additional turns**; **new verified chat:** at most **20 turns**.
- `max_cycles=0` selects the safe bound; positive values greater than the bound are refused, not treated as unlimited.
- Starting a new chat or rolling over is not automatic proof of a successful handoff. The app must verify the right ChatGPT composer and a canonical context/reference before dispatch.
- An observed response marker is **not evidence** of a successful code build or finished APK. Source, tests, artifacts, installed version and on-phone behavior require separate receipts.
- Cycle count, latest checkpoint, last error, active/paused/review state are visible via the **How development cycles work** dialog in Asterion Control v0.9.26 (once installed).
- If the external ChatGPT tool session lacks a direct worker connector, actions fall back to the existing GitHub queue. The backend does not become real-time simply because the Windows execution takes milliseconds. Measure end-to-end observation-to-act-and-verify time.

## Acceptance status

The v0.9.26 cycle marker and bounded-counter code was compiled with the owner signer; the local Windows native/recovery tests passed **7/7**. This is not an attended or unattended real end-to-end cycle acceptance: installation, permissions, actual reply marker observation and multi-turn rollover still require phone testing. Never claim those stages completed from build or command receipts alone.
