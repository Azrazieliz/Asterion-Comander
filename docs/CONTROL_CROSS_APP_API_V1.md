# Asterion Control: shared Android execution interface (v1)
Status: implementation contract, not a frozen requirement or proof of on-device acceptance.

## Identity and responsibility
Asterion Control is an authenticated, deterministic **tool** for ChatGPT to operate the owner's Android-first Asterion ecosystem. It is not a second AI system or game-playing engine. The Android UI is a limited settings and permission surface. Application intelligence stays in ChatGPT and in the existing per-project app engines. Windows is optional/subordinate.

## Native phone endpoints
Agent at `http://<private-paired-android-ip>:8973`; requires bearer token, private Wi-Fi, VPN or loopback. **Plain HTTP must never be published directly to the internet.** A stable authenticated HTTPS ingress into ChatGPT remains required.

- `POST /mcp`: stateless JSON-RPC (`initialize`, `ping`, `tools/list`, `tools/call`); native Android MCP tool catalog provided by `AndroidMcp.java`.
- `GET /health`, `GET /ui`, `GET /screen`, `GET /stream`, `POST /input`: existing native device interfaces.
- `GET /apps`: installed launchable packages plus labels. `POST /apps/launch` with `{"package":"..."}`: dispatch app launch only while Control's Activity is foreground. A dispatched Intent is **not** verified app foreground success.
- `GET /continuation/status`, `POST /continuation/queue`, `POST /continuation/dispatch`, `POST /continuation/ack`, `POST /continuation/cancel`: phone-owned persistent checkpoint state.
- `GET /observation/status`, `GET /observation/events`, `GET /observation/frame`: opt-in evidence from only the selected foreground application, after Android MediaProjection grant. No AI inference inside Control.
- `GET /voice/status`, `POST /voice/question`: owner-started Android foreground speaker and one-shot on-device speech recognition, no paid speech API.

## Continuation lifecycle
1. ChatGPT uses actual GitHub canonical files and progress to formulate a bounded checkpoint with project, checkpoint ID, 5*/6*/7* source reference and next steps.
2. The phone's user-enabled queue persists it atomically; duplicate checkpoint IDs are rejected.
3. When the owner-enabled ChatGPT app is visible and contains an empty accessible composer, Control attempts to type and send the continuation. It does **not** claim model acceptance on Send click.
4. A real subsequent ChatGPT response is acknowledged through `/continuation/ack`, with checkpoint ID and concrete receipt marker; then a following checkpoint may be queued.
5. Ambiguous send/timeouts require review; never auto-resend, overwrite a user's draft or pretend ChatGPT limits are removed. Pausing preserves the previous lifecycle state.

## Cross-app boundaries
- **Asterion Pilot / Game:** Canonical autonomous game-playing Android app. Direct live perception, learning, scheduling, objectives and verified completion belong to Pilot. Control may externally observe gameplay or invoke authorized operations but must NOT replace Pilot with screenshot-driven navigation.
- **Game Codex:** Authority for sourced game mechanics, characters, data and approved cross-app evidence contracts.
- **Asterion Art/Core/Downloader/Sound/Adaptive Study/NoWorld/KK/3D:** Preserve each project's existing engine, assets, signing and repository. Control provides the generic screen, input, app catalogue, files, worker and routine-execution surfaces only when authorized.
- **Windows worker:** Optional native build/resource workflow; remote desktop, scripts and file transfer remain separate MCP tools. Do not treat a Windows agent as Android's primary operating head.

## MCP gateway
The HTTPS bridge is authenticated and merges native phone and optional Windows tool catalogs. Phone-owned tools route to the Android MCP service; PC-only tools route to the Windows worker. The existing temporary Cloudflare trial remains a deployment dependency. **A stable HTTPS endpoint plus actual ChatGPT connector authentication is still required.**

## Reporting and acceptance
Distinguish `implemented`, `CI compiled`, `installed`, `on-device tested`, and `verified`. The user's Samsung has installed v0.8.6, while v0.8.7 is development code. A CI debug signer may differ from the installed signing key; do not claim an update is possible without verifying certificate continuity. Never modify frozen 7* or project-specific masters without exact authorization.
