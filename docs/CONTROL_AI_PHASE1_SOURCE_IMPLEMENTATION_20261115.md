# ASTERION CONTROL — Native AI / Verified Cycle Kernel: Phase 1 Source Implementation
Date: 2026-11-15
Source branch: work/control-ai-core-20261115
Status: SOURCE COMMITTED + ISOLATED WINDOWS PYTHON UNIT TESTS PASS. NOT A DEPLOYED APP OR COMPLETE SYSTEM.
Approval: owner "Authorized" on 2026-11-15 after architecture discussion. Source coding and source-only regression tests permitted. Prior owner hold on APK building, owner signing, installation and worker deployment remains until separately explicit authorization.
Owner constraints: 100% preserve original Asterion Control Android package/signature/pairing/Windows worker, all apps/data, and no independent changes inside Asterion Downloader; no paid model API or mandatory subscription; SuperVPN excluded; full-phone VPN must preserve throughput >=75% and route Japan only on actual need; Tor/.onion remain in design.

## 1. What was actually implemented in source

### Android existing ChatGPT cycle repair, not yet built
- android/app/src/main/java/com/asterion/control/ContinuationLedger.java: recover a prior uncertain UI submission only after a fresh matching *visible* non-generating ChatGPT reply marker; no arbitrary receipt input accepted, no double send.
- android/app/src/main/java/com/asterion/control/ContinuationCycle.java: in needs_review, re-observe a matching stable reply for 12 seconds, then call ledger reconciliation and resume the same cycle without replaying a potentially delivered message. Restart resets evidence timer. No APK recompile or real phone acceptance yet.
- These changes were initially committed to work/control-0927-overnight-cycles-20261111 and are inherited by the isolated branch. They are NOT evidence that the observed stopped cycle has been repaired in an installed app.

### Core Windows independent development-cycle engine
- asterion_remote/overnight_supervisor.py: SQLite WAL and FULL synchronous durability. Separate from a normal Action and a finite Task. Explicit owner-created cycle, persisted unique turn lease before any AI submission, fail-closed uncertain sends, actual provider receipts, *separate* verified project-work receipts, durable pause/resume/stop including in-flight turn, owner-defined turn limit distinguished from actual verified project completion, checkpoint and evidence hash carried to next turn; bounded multi-turn programmatic executor adapter.
- Requires a real owner-authorized AI provider callback PLUS an independently checked work executor callback; no background daemon or fake automatically-running cycles.
- asterion_remote/local_model_provider.py: real JSON API access to locally hosted OpenAI-style chat completions on strict loopback endpoint, no paid/cloud fallback, proxy inheritance removed, HTTP redirect forbidden to prevent private prompt forwarding. A matching local inference runtime and weights have NOT yet been installed, selected or benchmarked.
- asterion_remote/control_ai_routes.py: authenticated Windows API for cycle listing/creation/pause/resume/stop and separately owner-approved local inference. A cycle created from API correctly returns automatic_turns_running=false, provider_executor_bound=false.
- asterion_remote/app.py: additive router mounts; existing native phone/Windows control routes and original pairing untouched.

### Existing source repaired, not replaced
- asterion_remote/interaction_sessions.py: an accidentally concatenated duplicate older module caused a real SyntaxError and shadowed journal improvements. Removed duplicate tail on isolated branch. Fixed Pydantic request-ID regex with correct Rust \z anchor. Existing session journaling retained.
- asterion_remote/model_lab.py: corrected SQL insertion from nine placeholders to ten for actual ten-column benchmarks table.
- tests/test_control_v2.py: wait for actual asynchronous terminal session receipt in test before Windows SQLite temp directory teardown; this prevents a live test worker holding events.sqlite3 open. The source worker itself is not redeployed.

### VPN/network eligibility and honest state engine
- asterion_remote/vpn_route_policy.py: FREE and owner-authorized provider requirements, explicit rejected SuperVPN/VPN Gate identifiers, real public IP/country checks, speed floor both download and upload >=75% direct, DNS/IP leaks, paired Control reachable, Japan geographic preference only on-demand, 30–60min distinct external phone IP rotation evidence, Tor mode separate.
- **No VPN transport, free foreign exit server, actual route or Android VpnService integration was activated by this module**. This is a tested policy/selection engine only.

### Real model evaluation harness
- asterion_remote/model_evaluation.py: SHA-sealed JSONL owner-allowed dataset, holdout and stress cases, bounded model-inference batches, actual provider result hashes, exact/contains/numeric/JSON-subset and externally evidenced tool/test judge scoring, per-model-revision SQLite ledger, progress status and continuation for large 50k+ case datasets. No model training, downloaded weights, generated genuine 50k corpus, or actual device benchmark has occurred.
- Existing asterion_remote/model_lab.py, skill_studio.py and security_scanner.py are preserved and tested; they are NOT brand new deployed services.

### MCP / actual tool protocol
- asterion_remote/local_mcp_client.py: real local stdio JSON-RPC subprocess protocol, older negotiated MCP 2025 versions and July 2026 stateless version with correct per-request client capability metadata and server/discover, executable SHA pin before launch, no shell, secret-free log behavior, only owner-approved tool allowlist, blocking of unexplained server requests, errors and unverified results distinguished, incomplete modern input_required not misreported as tool success.
- asterion_remote/mcp_tool_routes.py: bearer authenticated and *separately* owner-approved tool catalog and invocation endpoints for an owner-configured local official GitHub MCP executable and PAT, secret-free status, no API key logging, no resurrected ChatGPT-Control gateway, lazy process and graceful shutdown, deny if server not installed/configured.
- **Official GitHub MCP executable not yet deployed nor token configured in Windows Control. No claim that the native model already operates GitHub MCP.** Python subsystem can communicate with an actual MCP server once installed/configured.

## 2. Verification evidence

Isolated test procedure: existing authenticated private GitHub bridge to persistent Windows worker, non-destructive git fetch of feature branch into Git staging repository, source extracted to a NEW TEMP directory via git show (no git checkout/pull to dirty staging), syntactic Python compilation and 8 selected test module suites via scripts/verify_control_ai_isolated.py. Nothing changed in Windows production, signed Android app, original signer, pairing, or other apps.

Acceptance:
- 2026-11-15 early isolated 17/17 new cycle/local inference tests PASS via bridge results/ctl-source-20261115-1858-cycle-a2.json.
- 2026-11-15 isolated 60/60 tests PASS, source 73 files, 0 syntax errors via results/ctl-source-20261115-2138-shortreg-b1.json.
- 2026-11-15 updated 61/61 tests PASS, source 73 files, 0 syntax errors via results/ctl-source-20261115-2155-shortreg-b2.json.
- 2026-11-15 added real subprocess MCP legacy/2026 tests: 67/67 PASS, source 75 files, 0 syntax errors via results/ctl-source-20261115-2241-mcp-reg-c1.json.
- 2026-11-15 latest owner-authenticated MCP routes: **71/71 tests PASS, 77 Python files compile, 0 syntax errors** via results/ctl-source-20261115-2325-mcpapi-reg-c2.json. This is an isolated/source test, not live Android device verification.
- Failures were encountered, not concealed: original development source duplicated interaction_sessions.py, SQLite model_lab placeholder mismatch, async test teardown Windows lock; repaired on isolated feature branch and re-verified.

## 3. Preexisting Control assets preserved

- Original phone-native authenticated WSS and Windows worker, GitHub fallback bridge, Android package identity and original signing certificate, original Android installed state and credentials.
- Previous 7-star diagnostics and SSE, crash journal, v1 cross-app signed bridge, file transfer attempts, voice wake/STT/TTS code, WireGuard GoBackend source, owner access/permission profiles, model lab/skills/security scanner source.
- Do NOT confuse source present with deployed/installed/functionally accepted.

## 4. What remains to deliver the OWNER'S ENTIRE APP (NOT DONE)

P0: Real phone Android compilation and safe original-owner signed APK once separately authorized. Confirm 2026 Android APIs / source compile, restore correct signer, no data loss, live phone tests and verify uncertain-send recovery. Do not build prematurely.
P1: Obtain/license-benchmark an actually phone-native general LLM with original weights and Android inference runtime, plus optional PC model (not mandatory); tool-use evaluation and real model fine-tuning/training/adapter optimization; local model inference adapter currently assumes a configured loopback engine and does not itself load a phone model.
P2: Connect actual trusted developer work executor to cycle engine, persistent background scheduling, real several-hour substantial verified turns and project progress; ChatGPT-specific 20-message rollover remains inherited Android implementation requiring real acceptance.
P3: Populate 50,000 independent held-out and 200,000 distinct stress scenarios, 2,000 true multi-device integrations, 1,000 human-reviewed cases; execute and measure real models. The synthetic 500-case evaluation unit test is NOT 500 actual model benchmark tests.
P4: Integrate official GitHub MCP server binary with user-approved token/scopes, verify real repository read/write tool operation in a disposable project; present client module is source tested against a fake local process.
P5: Owner-enabled local wake "Asterion" and natural spoken two-way questions, offline STT/TTS, optional Sound voice-pack format; inherited voice code is not yet standalone all-rounder voice assistant.
P6: Cybersecurity/privacy on Android, full Standard/Deep file scan coverage within scoped Android constraints, test file scan/quarantine restore, cryptographic model packages and no private data leaks; Windows security_scanner source preexists.
P7: Real free trustworthy VPN exit, owner-approved VpnService, full-phone routing, verified new IP every 30–60m, measured <=25% sustained throughput loss and no native Control break, Japan on demand. No free provider proven to satisfy all constraints. Tor Browser and Tor VPN modes/.onion remain separate.
P8: Third-party missing-source reverse engineering workbench (JADX/Ghidra/controlled dynamic instrumentation), full tools and actual external-binary acceptance, not just concepts.
P9: Skill Studio/Model Lab full UI and app interaction, Asterion Sound/Art/Core/Rounder signed adapters and all 20+ approved modules. Avoid duplication with specialist apps and no Downloader modifications.
P10: Quality: full repo tests, Android compile/test, real Samsung phone/Windows cross-platform tests, security review, sustained battery/RAM/thermal performance, owner-signed build/update feed, device acceptance. 71 Python tests do not replace full project acceptance.

## 5. Current source paths / Git history

- Repo https://github.com/Azrazieliz/Asterion-Comander
- Implemented isolated branch https://github.com/Azrazieliz/Asterion-Comander/tree/work/control-ai-core-20261115
- The original work/control-0927-overnight-cycles-20261111 was subject to concurrent source changes, so isolated branch was introduced to prevent overwriting the other workstream. DO NOT merge without review.
- Source-only runner scripts/verify_control_ai_isolated.py; exact test files tests/test_overnight_supervisor.py, test_control_ai_routes.py, test_control_v2.py, test_session_journal.py, test_mixed_sessions.py, test_vpn_route_policy.py, test_model_evaluation.py, test_local_mcp_client.py and test_mcp_tool_routes.py.
- Status labels: documented, source implemented, source tested, built, deployed, installed, phone-verified are strictly independent.

## 6. Owner release / no-cost policy

All current work is free and in existing GitHub and Windows test infrastructure; no new account/subscription/model purchase/VPN subscription, Google Play action, APK signing, installation or production service replacement was performed.

The user authorized IMPLEMENTATION, not a destructive migration. The earlier explicit no-build requirement remains until a separately explicit authorization to build. Documentation and source commits are now permitted; never claim the whole app complete based on this phase.
