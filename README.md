# Asterion Control — existing external Android/Windows infrastructure

**Active operating method (owner correction, 2026-11-11).** Read this before any Asterion Control work. This replaces all past MCP-gateway/callable-Control-connector experiments. Preserve current signed app, owner data/pairing and persistent Windows worker; the original setup is not to be rebuilt.

## How ChatGPT actually operates Asterion Control

**Asterion Control is an external Android app plus Windows worker — NOT a tool callable directly inside ChatGPT.** Do not look for or install a hypothetical Asterion Control plugin, MCP server, gateway, OAuth connector, tunnl.gg address or special ChatGPT API. Do not ask the owner to enable an invented ChatGPT-to-Control integration. **The MCP gateway is retired and must never be restarted.**

The existing working path in ChatGPT is:

```text
ChatGPT
  → existing connected GitHub integration (not an Asterion Control tool)
  → private Azrazieliz/Asterion-Control-Bridge/main
  → commands/active/<unique-id>.json
  → existing persistent Windows worker (authorized PC operations)
  → existing authenticated native Android listener / WebSocket
  → results/<same-id>.json
  → ChatGPT reads and verifies outcome
```

The worker-to-Android **native WSS** is essential, already installed and independent of the removed MCP gateway. The existing stable phone hostname forwards to a minimal native WSS-only relay on Windows port 8995. The relay exposes only authenticated `/phone/live` and `/healthz`; both historical HTTP `/mcp` endpoints now return 404. The old gateway/OAuth scripts were retired from active source and runtime, while the original phone pairing and SSH key were preserved. Never mistake an existing native service, historic class name or `direct_wss` telemetry for a ChatGPT-callable tool. Do not replace or restart it merely because this conversation has no direct worker action namespace.

**Authoritative operational contract:** [private Asterion Control bridge README](https://github.com/Azrazieliz/Asterion-Control-Bridge/blob/main/README.md). It contains the exact command JSON, permitted operations, receipts, app switching and cycle behavior. **That README supersedes older guidance.**

To control a device here, use the connected GitHub tool to **create** `commands/active/<id>.json` in `Azrazieliz/Asterion-Control-Bridge`, then **fetch** `results/<id>.json`. For example `{"id":"unique-id","op":"phone_ui","params":{}}`. Confirm `status:complete` and `ok:true`; a mere accepted job or tap ACK does not verify the intended state. Jobs such as `pc_command` can themselves run bounded multi-action scripts **on the persistent worker**, without GitHub per gesture. Never repeat an uncertain ChatGPT Send or destructive action.

## Android test/cycle method

- Leave ChatGPT for actual app testing through existing Android navigation. **Return using Samsung Recent tasks → the existing ChatGPT card**, NOT the generic ChatGPT launch intent, which may open a blank conversation.
- If sharing stops, use the existing Asterion Control **Connect → Start screen sharing** UI and the actual Android consent dialog. Confirm fresh video frames and direct WebSocket, then return to the original ChatGPT conversation/task. No new phone pairing or new gateway is required.
- Cycle = **continuously repeating development process** (often overnight), never one turn. Normal turn ≈ **30 minutes substantive work** (under 25 minutes without real changes is inadequate). The owner may authorize **short turns for acceptance testing only**. Every individual action must target **under 10 seconds including ChatGPT decision time**, simple actions ≈1 second. Worker-only timings do not certify the entire ChatGPT action latency.
- An unbounded cycle `max_cycles=0` **does not end after 10 or 20 turns**. After **20 total ChatGPT messages** (approximately ten prompt/reply pairs) perform a **verified conversation rollover with a canonical repository handoff** and keep the same long-running cycle. Do not open a new conversation after one message. Preserve the unique ACK/DONE reply marker and do not double-send on uncertain delivery. A normal keyboard dismissal after a Send gesture does not indicate an error.

## Truthful state / project continuity

| Stage | Meaning |
|---|---|
| Source implemented | Committed to canonical development branch |
| Tested / built | Tests/Android compilation/signing actually passed |
| Published | Update feed points to APK; **not proof of installation** |
| Installed | Real phone package version independently verified |
| Phone accepted | Full real UI/cycle scenario completed with matching receipts |

**Current publication:** owner-signed **v0.9.31** Android release is published on `main` with the existing in-app update feed (compiled source `f5f74e0ba94ceb5152fbbffe50d277ebc2ee3e97`, SHA-256 `800b85fb8114e8d6619620aeef2f82da47d2ef985e64eac523a138774be182bc`). Installation and a completed unattended cycle are **not verified**. For current version/defects read [PROGRESS.md](PROGRESS.md). Source of recent development is `work/control-0927-overnight-cycles-20261111` or a newer verified continuation, not old source on `main`.

Project requirements: [7-star frozen master](7STAR_FROZEN_MASTER.md), [continuous cycle contract](docs/CYCLE_EXECUTION_CONTRACT.md), [cross-app API](docs/CONTROL_CROSS_APP_API_V1.md). Historical MCP gateway/plugin instructions were exploratory and are **revoked**, not a checklist for future implementation.
