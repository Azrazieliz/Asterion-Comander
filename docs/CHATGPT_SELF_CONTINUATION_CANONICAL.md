# ChatGPT self-continuation mechanism — canonical instruction (2026-11-07)

## Purpose
Continue the current development task across multiple ChatGPT turns without requiring the owner to manually send "continue" after each turn.

## Exact mechanism
1. The assistant works normally in the current ChatGPT conversation, using appropriate development tools and saving real progress in the canonical project repository.
2. Before the current assistant turn ends or reaches its execution limit, the assistant composes the **next development request**, identifying the current project, latest actual progress, remaining work, and instructions to repeat this same behavior.
3. **While the current turn is still running**, the assistant uses Asterion Control strictly as a remote phone input device to operate the **existing ChatGPT app and same conversation**: focus the writing bar, enter the next request, and press the visible Send control.
4. The submitted request starts the next ChatGPT turn. That turn continues the actual work, and repeats steps 1–3 before it ends.
5. Stop initiating new turns once the owner-requested work is genuinely finished or the owner explicitly stops the loop. Never manufacture progress or claim a submission without evidence.

## Boundaries
- Asterion Control is ONLY a way for the assistant to operate the phone and submit a message in ChatGPT. It is **not** a cycle manager, project scheduler, checkpoint queue, or development orchestration system.
- Do **not** implement or require cycle APIs, queued checkpoints, acknowledgment markers, artificial cycle indexes, or external scheduling for this mechanism.
- Do **not** create a new conversation. Do **not** wait for the owner to press Send as the intended loop.
- The next prompt must be a normal user-style development request, not a diagnostic checkpoint.
- Preserve all project context, GitHub canonical state, constraints, and previously completed work. Avoid duplicate sends when the outcome is uncertain.
- The mechanism depends on actual successful UI submission; a written continuation instruction in the assistant reply alone does not create another turn.
- Distinguish the **desired mechanism** from the **verified current functionality**: one prior phone-submitted message was observed, but reliable two-turn autonomous submission has not yet been verified.

## Owner's clarification
"While the current turn runs it's good and once it's close to finishing, it writes the request and sends it, that will end its turn yes but at the same time, that will start a new one which will when it finishes start another one and so on."

This document is the canonical reference to avoid asking the owner to explain the mechanism again.
