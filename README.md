> **LATEST OWNER REQUIREMENTS · 2026-11-19 — V6 P−1/P0 CORRECTIONS:** [V6 reconciled Control contract](docs/CONTROL_V6_OWNER_CORRECTIONS_20261119.md) takes precedence over contradictory historical V2–V5 text. **P−1 mandatory:** stop recurring bridge and control failures with live, truthful universal diagnostics. **P0:** advanced and maximally tailored Asterion Cute/AI, complete everyday Browser plus AI crawlers, primary cellular-capable native WSS for both Control and native AI, self-contained free VPN onboarding as far as Android/provider consent permits, robust actions/tasks/development cycles, genuinely actionable signed partner bridges including **3D**, meaningful Core and Downloader diagnostics, security/model training, external software analysis and premium UI *everywhere*. **P1:** voice is **English only** and currently reported nonfunctional. Original signing, Android data, paired services, app ownership and the no-mandatory-cost rule remain. **V6 is documented product scope, NOT verified runtime completion.** Older NO-CODE HOLD statements here refer to the November 15 design-only stage; separate subsequent owner authorization and implementation work are recorded in PROGRESS.

> **CURRENT OWNER IMPLEMENTATION AUTHORIZATION · 2026-11-15:** The owner subsequently authorized continuation and completion of Control implementation after the V3/V5 documentation-only review. Those older NO-CODE statements are retained below as historical context, not a present stop condition. This continuation committed evidence-only cross-app diagnostics, bounded private bridge operations, an existing-style Windows dashboard, and a native Android Health entry; Windows Python tests and Java/JS compilation checks passed in an isolated checkout. **Source-tested is not installed or phone-accepted.** The existing paired Windows worker, native phone connection, signer, user data and APK remain preserved; deployment and full multi-app acceptance are still outstanding. See [PROGRESS.md](PROGRESS.md) for exact results and the current source branch.

> **LATEST USE-CASE AND TRAINING REVIEW (2026-11-15):** [Control V5 — geographic IP benefit, Rounder overlap and 50k-case AI holdout evaluation](docs/CONTROL_V5_GEO_USAGE_ROUNDER_MODEL_TRAINING_REVIEW_20261115.md). For the owner's actual work, reliable fast replacement IP is more important than arbitrary country selection; region-specific exits remain on-demand, based on actual site policy and verified availability. Control must use Rounder/Downloader/Core instead of duplicating specialist capabilities. AI benchmark target upgraded to 50,000 held-out + 200,000 robustness + 2,000 real multi-device workflows, ALL FUTURE NOT IMPLEMENTED. **No coding/build/install authorized.**

> **LATEST BROWSING + EVALUATION DECISION · 2026-11-15:** [V5 full browsing/media VPN geo-value, shared Browser/Codex, Rounder reuse, 12,000 sealed native AI tests](docs/CONTROL_V5_USAGE_GEO_BROWSER_REUSE_12000_EVAL_20261115.md). Country access is useful ON DEMAND for region-specific Japanese artwork/creator and media sites as well as general browsing, while default VPN prioritizes a replacement public IP, privacy and no more than 25% throughput loss. The owner rejected 500-test evaluation; at least 10,000 distinct held-out tests, recommended 12,000. Document changes ONLY; no coding, builds, device operations or training yet.

> **CURRENT VPN/AI RESEARCH · 2026-11-15:** [V4 verified VPN alternatives, Tor VPN Beta, native all-rounder training feasibility and actual engine systems](docs/CONTROL_V4_VPN_EVIDENCE_AI_TRAINING_SYSTEMS_RESEARCH_20261115.md). **NO CODING/BUILD/INSTALL** authorized yet. Free VPN with security, programmable country rotation and <25% speed loss is UNVERIFIED; Proton Free supports standard WireGuard config import, VPN Gate logs private connection metadata and is NOT a default privacy candidate, Tor VPN Beta has Tor Project leak-risk warnings. V3 remains full design baseline. Asterion's AI must gain real tool systems, not rely on model training alone.

> **LATEST OWNER DIRECTIVE · 2026-11-15 · NO CODE:** [Control V3 — Complete architecture and 30 new optional systems](docs/CONTROL_V3_COMPLETE_DESIGN_NO_CODE_20261115.md) is the authoritative specification. SuperVPN is fully discarded. The owner explicitly ordered NO CODING YET, no build, test, installation, runtime mutation or provider configuration. The last V2 interim "source implementation authorized" notice is superseded. Preserve existing Control pairing/signer/runtime and leave Downloader to its own developer. The original cycle remains overnight project advancement, never normal action handling.

> **CURRENT OWNER-APPROVED ARCHITECTURE (2026-11-15):** [Asterion Control V2 — zero-cost native AI, true overnight cycles, security/privacy, VPN performance gate, voice, GitHub MCP, reverse engineering and all approved modules](docs/CONTROL_V2_OWNER_APPROVED_ARCHITECTURE_20261115.md). This is **specification only**; do not build/transfer/install or replace the owner signer without an explicit subsequent authorization. The owner has assigned **Downloader to someone else**: no Downloader source edits/builds from Control work. V2's explicit corrections override older suggestions that Control's only AI must be ChatGPT, that a normal action is a cycle, or that the VPN is optional by default. Preserve all old contracts as historical sources, not current contradictory requirements.

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

## Owner-approved 7★ upgrade specification (2026-11-15)

The active implementation contract for universal live crash/engine diagnostics, real-time phone/PC execution, developer-authorized access, optional fast private VPN, adaptive connection recovery and security levels is [docs/7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md](docs/7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md). Preserve the existing working Control infrastructure; implement and verify the requirements incrementally, beginning with instrumented Downloader root-cause analysis. This is a **specification, not a claim of implementation**.
