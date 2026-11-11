# ChatGPT self-continuation mechanism — canonical instruction (2026-11-07)

## Purpose
Continue the current development task across multiple ChatGPT turns without requiring the owner to manually send "continue" after each turn.

## Exact mechanism
1. The assistant works normally in the current ChatGPT conversation, using appropriate development tools and saving real progress in the canonical project repository.
2. Before the current assistant turn ends or reaches its execution limit, the assistant composes the **next development request**, identifying the current project, latest actual progress, remaining work, and instructions to repeat this same behavior.
3. **While the current turn is still running**, the assistant uses Asterion Control strictly as a remote phone input device to operate the **ChatGPT app and current conversation**, except when the mandatory conversation-length rollover requires a **new conversation with a complete handoff**: focus the writing bar, enter the next request, and press the visible Send control.
4. The submitted request starts the next ChatGPT turn. That turn continues the actual work, and repeats steps 1–3 before it ends.
5. Stop initiating new turns once the owner-requested work is genuinely finished or the owner explicitly stops the loop. Never manufacture progress or claim a submission without evidence.

## Boundaries
- Asterion Control is ONLY a way for the assistant to operate the phone and submit a message in ChatGPT. It is **not** a cycle manager, project scheduler, checkpoint queue, or development orchestration system.
- Do **not** implement or require cycle APIs, queued checkpoints, acknowledgment markers, artificial cycle indexes, or external scheduling for this mechanism.
- Stay in the same conversation for ordinary cycles, **but create a new conversation at the required 20/10-message rollover boundary** using native ChatGPT UI and a self-contained context handoff. Do not wait for the owner to press Send as the intended loop.
- The next prompt must be a normal user-style development request, not a diagnostic checkpoint.
- Preserve all project context, GitHub canonical state, constraints, and previously completed work. Avoid duplicate sends when the outcome is uncertain.
- The mechanism depends on actual successful UI submission; a written continuation instruction in the assistant reply alone does not create another turn.
- **Verified (2026-11-07):** the owner observed successive normal, same-chat cycle messages 2, 3, and 4, sent using the native phone UI. The owner stopped after cycle 4. **Not yet verified:** new-chat handoff, rollover message count, and context preservation after switching conversations.

## Mandatory length guardrail (owner instruction, 2026-11-07)

- **Fresh conversation started for cycle continuation:** no more than **20 actual user/assistant chat messages** before changing to another new ChatGPT conversation.
- **Cycle begins in an already-used conversation, outside its first messages:** change to a new conversation after **10 additional chat messages at most**, or earlier if already near/over the fresh-conversation limit. If the existing count cannot be established, roll over conservatively at the next continuation.
- Count actual chat messages (user + assistant), **not tools, background progress events, or UI taps**.
- At rollover, first commit current work, then prepare a self-contained handoff including project/repo, verified branch/commit, completed work, next task, exact constraints, link to canonical docs, and an instruction to repeat both the native-input continuation mechanism **and** this message limit.
- Use Asterion Control **solely as native screen/keyboard/touch input**: visually select ChatGPT **New chat**, confirm an empty new conversation, enter and visually verify the handoff prompt, then tap the real blue Send arrow. Confirm delivery before claiming success. **Do not use checkpoint queues or automated cycle managers.**
- The new chat resumes from the handoff and project source of truth, and begins its own count. An owner instruction to **stop** cancels sending the next prompt and any pending rollover.
- Full exact UI input procedure lives in the shared private bridge `Azrazieliz/Asterion-Control-Bridge/README.md` (GitHub main branch).
- **Remaining acceptance test:** actually switch chats on-device at the guardrail, observe context-preserving handoff and next assistant turn, and check threshold counting, stop behavior, and no-duplicate recovery. Code-only documentation is **not** evidence of a live guardrail.

## Owner's clarification
"While the current turn runs it's good and once it's close to finishing, it writes the request and sends it, that will end its turn yes but at the same time, that will start a new one which will when it finishes start another one and so on."

This document is the canonical reference to avoid asking the owner to explain the mechanism again.
