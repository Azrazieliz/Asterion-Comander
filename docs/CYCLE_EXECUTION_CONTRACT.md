# Asterion Control — continuous overnight development cycle (operator contract)

**Owner-authorized specification — 2026-11-11.** This supersedes the earlier "one cycle = one turn" and "10/20 total turns" descriptions. The **cycle is the entire continuously repeating development process**; a **turn** is one substantial ChatGPT work request within that cycle. A **single action** is an individual observation, decision, API call, UI gesture or confirmation performed inside or outside a cycle. Never confuse these three levels.

## Duration, throughput and quality

| Unit | Required behavior |
|---|---|
| One simple native action | **Approximately 1 second** end-to-end, including ChatGPT's decision overhead, transport, execution and confirmation |
| Any individual action | **Under 10 seconds total** measured end-to-end, including ChatGPT thinking/decision time — neither a millisecond API acknowledgment nor a quick burst of taps hides minutes of planning |
| One substantive ChatGPT development turn | **Approximately 30 minutes of real implementation, integration, troubleshooting, validation and artifacts**; a turn under **25 minutes** without substantial verified work is inadequate |
| One development cycle | **Continuously repeats substantial turns**, often **overnight**, for as long as necessary until the defined scope is genuinely complete or the owner explicitly stops it |

Time is a target, **not a substitute for progress**: do not keep a finished tiny task open to consume 30 minutes, hallucinate progress, invent fabricated milestones, or count a 30-minute idle/model wait as development work. All turns must advance the canonical project substantively. If a platform session cannot remain active for 30 minutes, resume work durably in the next verified turn rather than presenting brief no-op replies as cycles. Do not claim an absolute ability to bypass ChatGPT's model/runtime/usage limits.

## Unattended operation

1. An owner-authorized cycle starts from its canonical project repository, specification, checkpoint and current progress. Android Control remains a deterministic phone/Windows transport. **No separate AI model runs inside Control**.
2. ChatGPT performs substantial project work with real tool receipts: edits, builds, tests, diagnosis, device checks, issue fixes. One reply ends with a unique ACK (work remains) or DONE (all defined work and acceptance verified); no early DONE.
3. Control verifies the *actual assistant reply in the real ChatGPT app* before submitting the next normal message, preserving the exact checkpoint ID and canonical handoff.
4. **At 20 total ChatGPT messages in the current conversation, Control automatically requests a fresh conversation without stopping the overall cycle.** The final turn before rollover must write a durable handoff in the canonical project progress/source, including exact branch, commit, test receipts, unfinished work and next tasks. The first turn in the new verified chat reads that handoff. Rollover must occur earlier if a verified conversation-length warning would otherwise block progress. A click alone is not proof that the new conversation loaded; Control checks the actual landing UI and protects unsent drafts. If the app hides evidence, an uncertain send must never be blindly attempted.
5. The same cycle continues indefinitely by default: **`max_cycles=0` means no arbitrary total-turn limit**. Positive `max_cycles` is an **explicit owner-requested** limit, not a safety default. The earlier limits of **10/20 turns are not total-cycle termination limits**. New chat rollover occurs after **20 total messages per conversation** (not after every turn), with actual landing verification before dispatch.
6. Android/Windows crashes or network outages retain the durable checkpoint and reconnect using existing worker/agent without resetting the cycle. Never regenerate or resend a message with an uncertain delivery status, overwrite an owner's draft, bypass required Android permissions, or silently send to an unverified chat. Resume automatically where the next step is provably safe; expose true blockers prominently without reporting success or requiring needless manual restarts.
7. The owner can pause or stop. DONE ends a genuinely complete scope. A recoverable network/foreground/keyboard delay does **not** count as a completed cycle. A genuinely ambiguous Send or missing Android consent may require review; do not mislabel it as completion or claim overnight independence that has not passed acceptance.

## Measurement and acceptance

Measure separately **(a) observation-to-decision**, **(b) command transport**, **(c) device/API execution**, **(d) outcome verification**. The sum for **each individual action** is compared to the 10-second deadline. The target for trivial deterministic gestures is ~1 second. The existing GitHub connector and private command/result bridge are the **actual ChatGPT-to-worker invocation path in this setup**. The Windows worker's authenticated phone WebSocket is an **internal native transport**, not an Asterion Control tool callable inside ChatGPT. Do not install or use an MCP gateway or claim a direct ChatGPT worker session exists. GitHub relay latency is additional to worker execution.

A worker-side 69 ms input ACK does **not** measure ChatGPT's minutes of thinking and cannot satisfy the end-to-end action SLA by itself. Likewise a model's 30-minute working turn cannot excuse a 20-second individual UI navigation.

The phone's durable turn telemetry records time from actual message submission to observed assistant response, but elapsed wall-clock time alone **does not prove substantive work**. Cross-check real source commits, test outcomes, artifacts and phone acceptance. Keep observed states separate: written, tested, built, published, installed, phone-verified, continuous overnight run verified.

## Implemented versus proven

Canonical operating method: [Asterion-Control-Bridge README](https://github.com/Azrazieliz/Asterion-Control-Bridge/blob/main/README.md). Asterion Control is an **external Android/Windows system**, never a ChatGPT-callable tool. The legacy HTTP MCP gateway, OAuth setup and associated launcher scripts are retired; **native authenticated phone WSS is preserved** behind the existing stable forwarding identity. An old class or SSH-key *filename* containing `mcp` is not a reason to resurrect that gateway.

The currently published owner-signed Control APK is **v0.9.30**, and source work beyond that version may be staged. Only a real phone version check proves installation. The 20-message rollover, same-conversation task restoration, actual ChatGPT ACK handling, unattended operation and full end-to-end action latency still require live acceptance; do not claim these are proven from a build or source test alone.

