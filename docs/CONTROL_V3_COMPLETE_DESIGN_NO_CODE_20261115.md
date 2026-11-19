> **SUPERSEDED WHERE CONFLICTING · 2026-11-19:** [V6 owner corrections and mandatory P−1 reliability](CONTROL_V6_OWNER_CORRECTIONS_20261119.md) override historic priorities, FR/EN voice (English-only), restricted Browser ambitions, bridge expectations and any older no-code hold. Original V3 approved 20 modules and unapproved N01–N30 proposals remain preserved. Use PROGRESS for actual implementation status.

> **V4 RESEARCH ADDENDUM · 2026-11-15:** [VPN provider facts, official Tor VPN Beta, all-rounder AI model/source modification and 24 real executable systems](CONTROL_V4_VPN_EVIDENCE_AI_TRAINING_SYSTEMS_RESEARCH_20261115.md). V3 is preserved as the broad owner-approved design; V4 narrows feasibility for actual free VPN exit sourcing and expands implementation-level architecture. Existing strict NO-CODE HOLD remains in force.

# ASTERION CONTROL V3 — COMPLETE SYSTEM DESIGN, NO-CODE HOLD
Date: 2026-11-15
Owner instruction: "Discard SuperVPN ... develop everything ... Do not code yet, just develop everything and suggest more systems."
Status: ARCHITECTURE / FUNCTIONAL CONTRACT / RECOMMENDATIONS ONLY. NO SOURCE IMPLEMENTATION, NO BUILDS, NO TESTS, NO DEVICE ACTIVITY, NO DEPLOYMENT, NO APK OR MODEL DOWNLOAD AUTHORIZED BY THIS INSTRUCTION.
Primary repository: Azrazieliz/Asterion-Comander
Development branch: work/control-0927-overnight-cycles-20261111
Prior references: 7STAR_FROZEN_MASTER.md; docs/7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md; docs/CONTROL_V2_OWNER_APPROVED_ARCHITECTURE_20261115.md; docs/CYCLE_EXECUTION_CONTRACT.md; docs/CONTROL_CROSS_APP_API_V1.md; PROGRESS.md.
This V3 contract supersedes earlier contradictory draft text about authorization to start implementation, a SuperVPN fallback, optional VPN default, ChatGPT-only operation, reverse-engineering scope, and the mistaken equivalence of normal actions and overnight cycles. Preserve the historical files for audit. The owner's explicit "Do not code yet" is the current instruction.

## 0. GOVERNING DECISIONS AND INVIOLABLE PROJECT BOUNDARIES

1. Preserve the existing authenticated Windows worker, Samsung Android Control, original Android package com.asterion.control and OWNER signing identity, paired native connections, WSS relay, established GitHub fallback bridge, credentials, device/project data, real verified functions and prior designs. No replacement gateway, new pairing stack, uninstallation, model removal or surprise migration.
2. Asterion Control is the master interface and trusted manager for connected Android/Windows and the Asterion ecosystem; it coordinates other apps' engines, DOES NOT duplicate image/video/sound/3D generation models or silently alter partner source. Downloader's own implementation is assigned to another developer/conversation; Control must not independently patch or rebuild Downloader.
3. All core operations must work at zero mandatory monetary cost: existing hardware, offline-capable open/free components, no subscriptions, no paid API, no rented GPU, no foreign owned servers assumed. Genuine external free service limitations and local electricity/bandwidth remain real.
4. Phone-native trainable general assistant is primary; PC-hosted model optional, cloud optional ONLY where genuinely no charge and no required dependence. ChatGPT optional provider, NOT the orchestration engine's mandatory backend.
5. The locally hosted AI should not add arbitrary provider-style moderation layers or reject broad content categories merely because they are controversial or adult. System file safety, external service authorization, OS permissions, data ownership, signed identity, credential isolation and approval for high-impact operations are separate from text generation preference.
6. Voice: trigger phrase "Asterion"; Bixby-like responsiveness; true multi-turn voice conversation; both owner-initiated commands and task-relevant assistant-initiated questions; configurable future Asterion Sound voice packs; no dependency on Sound being complete.
7. Security & Privacy are grouped in ONE user-facing section, but access-control profiles and malware-scan profiles are technically distinct. Automatic Standard scans for accessible new files, Deep for risky types; reversible quarantine, limited false-positive damage, audit.
8. VPN: FULL-PHONE default after real consent/provisioning, native Control connectivity protected; 30–60 min *verified public exit IP* rotation (45-min initial policy); geographic preferences where objectively supported; separate Tor/.onion access; maximum sustained throughput degradation of 25% (VPN throughput >= 75% of comparable direct baseline) as hard acceptance gate; p95 latency increase target <=25%. No silent privacy bypass on failure.
9. SuperVPN (Google Play com.jrzheng.supervpnfree) is OWNER-REJECTED. NEVER include it in candidate provider catalog, integration, dependency, fallback, recommendation or automated use. Mention only as historical rejected decision. No foreign servers/machines controlled by owner: do not invent them.
10. Reverse-engineering lab: primarily external binaries, programs, protocols, formats and components for which OWNER DOES NOT ALREADY HAVE THE SOURCE or documented implementation. Do not turn it into a duplicate project introspection engine; expose legitimate authorized external analysis and compatibility capability. Having a binary does not grant access to somebody's private repository.
11. Every previously approved capability (V2's 20 modules plus concrete security/network/AI/development/device/file/reliability/UI subsystems) remains in scope. Additional proposals under §18 are RECOMMENDATIONS until approved; do not silently reclassify suggestions as owner-approved.
12. Owner says no coding yet. This document may be committed with README/PROGRESS references, but NO operational/source changes, build, installation, network-provider login or automatic run. Implementation remains NOT STARTED for new V3-only capabilities.

## 1. SYSTEM ARCHITECTURE, PROCESS BOUNDARIES AND DATA FLOWS

A. USER LAYER: Native Android Control UI; secure voice assistant; optional PC dashboard and private authenticated API. It visualizes actual status, inputs, approvals, verified results, not cosmetic "connected" claims.
B. INTELLIGENCE LAYER: Local LLM runtime + optional PC backend + optional free external adapters; context packer; reasoning plan; tool selection; locally persisted project memory; evaluator; evidence/citation verifier; model router; quality calibration.
C. EXECUTION LAYER split into THREE separate systems:
   1. ACTION: one native UI/API/tool action with authorization, request ID, result, verification; latency measured end-to-end.
   2. TASK: bounded dependency-aware action graph, persistent execution and cancellation. Tasks may run in parallel when independent.
   3. OVERNIGHT DEVELOPMENT CYCLE: distinct project-advancement supervisor with real repeated substantive AI work turns, checkpoints, automatic follow-up prompts, response verification, test/commit evidence, continuation and ChatGPT-only message rollover.
   NEVER represent a task/gesture or a single AI reply as a full overnight cycle.
D. TRUSTED TOOL PLANE: typed registered tools and capabilities; GitHub MCP; native Control operations; shell/build/test broker (Windows owner authorized), internet retrieval/browser, external reverse engineering, device telemetry, file scanner, signed Asterion partner adapters; permissions and scope adjudication.
E. CYBERSECURITY/PRIVACY PLANE: file intake and malware analysis, quarantine, signatures, identity/credential store, privacy telemetry, routing, VPN/Tor, data export/redaction, rollback and supply chain.
F. OBSERVABILITY PLANE: crash-safe journal, incident matching, state snapshots, UI/network/process/engine traces only where permitted, evidence SHA256, provenance, telemetry policy, diagnostic stream, immutable test receipts.
G. STORAGE PLANE: encrypted credentials, indexed RAG/knowledge graph, task/cycle journal (SQLite WAL), scoped file cache and provenance, per-app adapter capability records, versioned model/skills registry, owner settings backup. Do not duplicate the partner engines' data.

Runtime distribution:
- ANDROID: required app, native AI inference as phone capacity permits, always-available command UI, wake word/voice, on-device scans of accessible files, Android VpnService, locally permitted app bridge and basic security/telemetry.
- WINDOWS: optional secondary worker for intensive local inference, development/build, Ghidra/other RE, deep static/behavioral scanning in isolation, large index processing and bulk model evaluation; preserve existing worker service.
- EXTERNAL: only optional no-fee services actually verified available; GitHub is already used with owner credentials and needs scoped permission; no reliance on purchased VPN exits or paid inference.

State ownership rules: Each task/cycle has exactly one durable leader/lease; steps have stable IDs and receipt hashes; network loss can yield OUTCOME_UNKNOWN. Mutating operations must not auto-repeat until prior state is reconciled. Phone and PC must not each assume they own the same job after reconnect. Scheduled/inference/scan/voice work is resource-budgeted.

## 2. USER FACING EXPERIENCE — PREMIUM, LOW-NOISE AND NO FAKE CONTROLS

Primary navigation (integrated existing UI, not a wholesale replacement):
- HOME: both devices, actual transport path, secure VPN current exit/status/speed budget, active tasks and overnight cycles SEPARATELY, threats, model health, next owner decision, recent VERIFIED outcomes.
- ASSISTANT: text/voice multimodal INPUT where needed; primary native AI; tool status; conversation and project selection; provenance and responsible model; ability to pause/cancel.
- TASKS: action/task DAG views, queued/running/blocked/completed/outcome-unknown, dependency progress, verification and artifacts.
- DEVELOPMENT CYCLES: true overnight cycle start/pause/resume/stop; current substantial turn, verified replies, project commits/tests, handoff/cycle counter, ChatGPT adapter-specific chat rollover and manual-review reason.
- SECURITY & PRIVACY: files scanned, Standard/Deep, quarantine/restore, signatures last updated, package auditing, credential access, VPN/Tor, leaks and network routes; ACCESS CONTROLS is separate subsection.
- NETWORK: all traffic routes, real remote exit IP/location when verified, rotation countdown/last success, throughput & RTT compared with direct baseline, selected country, Tor capability, disconnect/kill switch and OS consent.
- VOICE: microphone mode, wake phrase, selected voice package, languages, interrupt/quiet hours, question queue, speaker verification options and local wake-test.
- DEVELOPMENT: repo navigator, edit/test/build orchestration, GitHub MCP tool status, sandbox, third-party RE lab, evidence and compatibility.
- MODELS: per-app inventory, on-device phone AI, optional PC AI, model benchmarks, release notifications and migration proposals.
- SKILLS: library, editable and testable skills, pre/postconditions, version history, rollbacks and approval scopes.
- PROJECTS: knowledge graph, app/dependency inventory, source hashes, installed versions, outstanding acceptance targets.
- EVIDENCE: event/incident/trace timeline, validated artifacts, redacted export, repro scenarios; technical details on demand.
- SETTINGS: zero-cost guard, privacy policy, notifications, scheduling, battery limits, access profiles, backup, restore, app integration and OS permissions.

Design contracts: Responsive handset landscape/portrait, accessible controls, bounded rendering, precise state labels (not_connected, establishing, online, degraded, stale, permission_required, blocked, running, verified, failed, outcome_unknown, not_supported), explicit last verified timestamp, distinguish worker-local RTT and model-inclusive end-to-end latency. No dead/dummy controls, false success badges, fake progress or forced extra approval each harmless operation.

## 3. NATIVE ASTERION INTELLIGENCE — ALL-ROUNDER + INTERNET + CODING

Functions: general chat/reasoning in French/English, web research with source evidence, local/offline docs RAG, filesystem search, source and build understanding, tool planning, target app orchestration, diagnostic analysis, voice conversation, skill creation, model comparisons, setting real owner-scope tasks, developer tooling and reverse engineering coordination.
Model admission: evaluate 1 or 2 efficient phone-suitable open-weight instruct candidates (size/quantization chosen AFTER profiling Samsung actual RAM, thermal headroom and tok/s), separate optional larger PC model for heavy jobs. Do not require a dozen language models inside Control. No promise native model matches proprietary flagship intelligence.
Candidate discovery sources: verified model authors / Hugging Face model cards / release channels, licensed local runtimes (llama.cpp or equivalent), package integrity checks. No automatic acceptance of an Internet-advertised new model.
AI model router: tasks carry difficulty, context length, privacy, time, battery, tools and quality thresholds; choose PHONE, PC, optionally FREE_EXTERNAL, NEVER paid without changing owner decisions. Degrade to deterministic operations if LLM unavailable. PC not required for ordinary voice/wake.
Tool call contracts: typed JSON schemas, verified client invocation, allowlist per source/app/project, idempotency, scope expiry, cancellation, return evidence/hash, secure vault for credentials and telemetry sanitized. Tool outputs from network/source must be treated as untrusted data, not AI instructions.
Memory: project facts with source and date, owner-approved constraints, recent action outcomes, current task/cycle checkpoints, searchable embeddings, explicit forget/export, evidence freshness, per-project namespaces. Do not promote a model suggestion into a saved fact without verification.
Training tiers: (1) memory+RAG, (2) tool-use demonstrations + Skill Studio with deterministic code, (3) versioned LoRA/QLoRA fine-tuning of suitable licenses and hardware on PC, (4) offline evaluations before promotion. No unsafe automatic training on sensitive content or hallucinated "self-correcting" performance. Preserve base model / dataset consent / lineage.
Model quality benchmark domains: general Q&A/reasoning, coding edits verified by tests, security-risk judgment, GitHub MCP correctness, tool planning, web source citation, Asterion app operations, bilingual voice intent, context length, bad outputs/abstention, privacy regression, CPU/RAM, battery/thermal. Select only when real scores outperform baseline.
Content preference: no deliberately imposed cloud-style forbidden-topic filtering inside standalone local assistant; creative/text capabilities remain model/license dependent. This NEVER grants app OS permissions to exfiltrate keys, impersonate owners, or perform destructive work without approval.

## 4. THREE DISTINCT EXECUTION ENGINES

### 4.1 ACTION ENGINE (ordinary operations)
- Resolve exact device/app/target state, typed tool method, owner scope; prefer semantic UI/native partner API, video/image only if needed.
- Execute bounded operation, carry trace_id/action_id, observe the **actual target state** and classify verified / failed / outcome_unknown.
- Performance target trivial ~1s end-to-end (including model decision where measured); normal individual operations target <10s but cannot be guaranteed under every model/network condition. Instrument all elapsed stages.
- Remote command lease, replay prevention, separate cancellation receipt; side effects after uncertain transport must be reconciled rather than repeated.

### 4.2 TASK ENGINE (finite graph)
- Nodes: action, verify, condition, loop with bounded maximum, human-approval, wait-for-event, parallel-group, test, rollback and evidence-snapshot.
- Dependencies, deadline, concurrency, ownership, expected/observed outputs, resource quotas; retries ONLY for safe/idempotent operations.
- Durable resume after Android/Windows process death, network handover; no duplication of application install, send, delete, asset export or model change.
- UI: Tasks page, NOT displayed as cycle turns.

### 4.3 CONTINUOUS DEVELOPMENT CYCLE ENGINE (OVERNIGHT)
- One cycle = whole project advancement session, often overnight; one turn = substantive development and outcome verification; actions/tasks executed within turn are NOT cycles.
- Work-plan from canonical repository/spec and tests; autonomously submit next substantial meaningful project-advancement request to selected AI provider and collect genuine reply/evidence.
- After each turn, verify code/test/build artifact status, append accurate checkpoint, identify remaining work, generate next request, and repeat until real completion, owner stop, or unrecoverable permission blocker.
- ~30m substantial-work target per development turn and under-25m quality warning; no artificial waiting, no idle counted as work, no false DONE. Clock and evidence separate.
- For ChatGPT provider: 20 total messages/conversation rollover with verified new chat and canonical handoff; this must NOT restart overall cycle. For local/PC AI: do not simulate ChatGPT rollover, use context compaction and persistent verified handoff.
- Screenshot observed 2026-11-15 showed STOPPED, current turn 1, verified replies 0, chat 0/20, rollover 0, checkpoint requires_manual_review, prior ChatGPT send needs operator review. These are concrete outstanding reliability failures, not "cycle already functional".
- Autonomous meaningful progress is conditioned on real authorized developer tools, existing owner project scope and safety checks. Ask spoken question when blocked by a genuine owner decision, not for every minor action; when owner does not answer, preserve cycle and continue independent safe work if possible.
- Acceptance: 2+ substantive verified turns, real source changes/tests on authorized controlled test project, crash between steps, no duplicate send, one verified provider-specific chat rollover, unattended overnight recovery, accurate pause/resume/stop and full project handoff.

## 5. VOICE ASSISTANT — BIXBY-CLASS RESPONSIVENESS, INDEPENDENT REASONING

- Local low-power wake-word "Asterion"; optional push-to-talk, background listening only owner-enabled/Android-permitted; privacy icon+quick mute, privacy-safe recording policy.
- Streaming local STT or efficient offline fallback (sherpa-onnx/whisper.cpp candidates), partial transcription, language auto-detect FR/EN, custom dictionary of project/app terms.
- Local conversation state, immediate audible acknowledgement, TTS (sherpa-onnx/Piper or licensed suitable voice model), interruption/barge-in and music-safe audio focus, volume and speaking rate, quiet hours.
- OWNER-INITIATED: "Asterion, resume my overnight 3D cycle"; direct local task/cycle API, not ChatGPT textbox injection.
- AI-INITIATED: authorized task needs owner preference, speaks exact concise question, accepts response, records structured choice/confirmation, resumes same task; no fabricated answer/no unrequested constant interruptions.
- Asterion Sound as future producer of hot-swappable voice packages: packages have signed manifest, version, TTS model+vocab, voice embedding, languages, sample rate, license, checksum, install/rollback, preview and performance benchmark. Sound not ready -> free native fallback remains fully operational.
- End-to-end metrics: wake false-activation rate, mic startup, transcription quality in quiet/noisy conditions, first audible response, microphone CPU/battery, speaker/question turn handling.
- Don't promise Bixby exact proprietary voice/availability; target practical quality and latency on target Samsung, including Android microphone foreground service restrictions.

## 6. SECURITY & PRIVACY — SINGLE SECTION, DIFFERENT INTERNAL FUNCTIONS

### 6.1 File Security Engine
Pipeline: accessible file arrival/change via Android Downloads/MediaStore, owner-selected SAF folders, Control transfers, cooperating signed partner apps, allowed Windows watch folders → copy/hash metadata → file signature/type identification → STANDARD scanning → automatic DEEP for APK/EXE/DLL/archives/scripts/macros/models/binaries/suspicious malformed formats → classification → report/quarantine/restore.
- Use licensed offline signature/rule engines where feasible (ClamAV, YARA-X), independent hash allow/deny lists, package signature checks, archive recursion/time/expansion caps, static dependency analyzer and document/sandbox flags.
- Mobile budgets: quick hash/static checks on phone for accessible data, deep large processing on optional PC; if PC absent and budget exceeded, status UNVERIFIED or INCOMPLETE, never "clean".
- Verdicts: known-malicious, suspicious, no-known-threat-found, incomplete, unsupported, scan-error; include evidence source/rule version/scan timestamp/file hash. No 100%-safe promise.
- Never irrevocably delete owner files automatically; reversible quarantine/isolated archive when OS access permits; false positive workflow, restore with explicit owner choice.
- Scan intake is NOT an attempt to break Android sandbox or inspect protected private app data.

### 6.2 Access/security configuration
Existing Normal/Developer/Lockdown/Custom remain AUTHORIZATION profiles. Developer access time-limited, owner UI only. Sensitive tools require scope, expiry, signed trusted caller, audit and deliberate approval. This is separate from content preference and scan depth.
- Verified app signer and owner approval for each partner; private transport TLS/auth; OS-backed secret store; rate limiting and replay protection.
- Never hardcode credentials in repos, prompts or screenshots; opt-in storage/exports, encrypted confidential backups; security sandbox for unknown binaries and source packages.

### 6.3 Privacy Engine
- Per-app network route inspection and owner policies where Android can apply, IPv4/IPv6/DNS leak evaluation, privacy health, tracker/domain blocking only via lawful owner VPN routing and transparent allowlist controls, transparent exception handling for Control WSS.
- Local disclosure report: which apps/tools were granted documents, hashes vs full files, source of a model output, retention and ability to delete/exclude; no silent upload of private file samples.
- Supply chain: APK signature/provenance, SBOM/version/licenses, dependency alerts and model checksum and author verification.

## 7. NETWORK ENGINE — VPN DEFAULT, FREE EXITS, ROTATION, TOR, SPEED

Goal: after owner enables proper Android VpnService and a valid free exit source, whole-phone traffic goes through an encrypted route by default; native Control connectivity uses protected authenticated route designed not to lose phone/PC control. No mandatory foreign servers or purchased provider.

### 7.1 Honest exit-sourcing architecture
- OWNED foreign machines: NONE. Do not configure fictitious exits.
- Eligible third-party exits: only verified, free, genuine protocol access, reliable privacy/trust record, correct current terms, appropriate country and sufficiently fast route. Selection must not require bypassing billing, hidden keys, unauthorized scraping, repackaging or relying on secret undocumented endpoints.
- SuperVPN: owner DISCARDED, NO INTEGRATION, NO FALLBACK.
- Rejected candidate exits automatically removed from selection, with reason and last check. If NO available acceptable free exit exists, status "VPN_UNAVAILABLE_NO_ELIGIBLE_FREE_EXIT" and user-facing explanation; software cannot create public IPs in other countries out of nothing.
- Provide pluggable vetted WireGuard/OpenVPN/other free tunnel protocols only where configs and network rights exist; do not mistake phone-PC private WireGuard tunnel for a geographic privacy exit.

### 7.2 Real rotation
- Target each 30–60 min (initial default 45), require external IP before/after, country verified independently if available, distinct old/new exit IP, last success timestamp, failure reason, no fabricated success.
- Do not kill existing verified app download/sensitive sessions merely for clock rotation; pin critical flows or schedule a bounded safe transition where protocol supports. If full-phone IP changes break connections, report the tradeoff rather than promising zero interruption.
- Automatic selection based on real security, bandwidth, measured loss/latency, country and provider support; circuit break bad exits.
- Competing existing Android VPN -> require actual owner choice; only one prepared VpnService at a time.

### 7.3 Strict throughput budget
For comparable Wi-Fi and cellular trials: T_direct = median sustained baseline throughput; T_vpn = comparable sustained tunnel throughput. REQUIRE T_vpn >= 0.75*T_direct. Target p95 RTT_vpn <= 1.25*p95 RTT_direct with honest variability. Measure warmup and 3+ samples each direction, report variation and false negatives from radio instability.
- If secure route fails 75% threshold, optimizer tries *other permitted secure free exits*. If none meets limit, STATUS=FAIL_SPEED_BUDGET and show tradeoff; no silent VPN disable/bypass or bogus pass.
- Data cap/metered monitoring to avoid excessive benchmarking, battery and background radios.
- This threshold is for normal full-phone VPN. Tor mode requires an explicitly independent slow-network expectation; if Tor falls below budget, show SLOW_SPECIAL_MODE, do not claim it passes default VPN target.

### 7.4 Always-on and leak avoidance
- Android OS first-time consent, actual always-on configuration and onRevoke handling; "block connections without VPN" is owner option, availability dependent on Android; unauthorized bypass forbidden.
- Control native authenticated socket protection, private connectivity recovery, IPv4/IPv6/DNS route rules, reconnect backoff, network switch, route leak detection and outage policy. Android API limitations respected.
- Tor access preferably via verified official Tor Browser / isolated Tor proxy for owner requests, with .onion end-to-end routing, isolation and independent status. Tor Browser guidance may discourage simultaneous VPN use; do not claim anonymity gains by combining unsupported layers.
- Privacy and route metrics require real samples, not endpoint reachability alone.

## 8. GITHUB MCP + PROGRAMMING + AUTOMATED QA

- Official GitHub MCP Server in native assistant's local/Windows tool registry as distinct integration from retired Control HTTP MCP gateway; preserve existing private bridge used by ChatGPT.
- Repository list/read, issues, PR, commits, GitHub Actions, diffs, releases, branch creation and scoped changes; default read-only until a development project grants appropriate write capability. Access token OS-backed and least-privilege.
- Development workflow: discover correct repo+branch+dirty changes; read source contract; research component; create minimal change on owned branch; static check + compilation + test + security scan; compare baseline and exact requirement; preserve signer/app data; publish only if permitted; maintain rollback and evidence. No output "fixed" based on compilation.
- AI code integrity: typed schemas, approval of tools by project, review of patch shape, test gates, confirmation of target branch/commit, duplicate receipt protection, detect unauthorized unrelated file edits.
- Coding proficiency trained through benchmark tasks and real tests, not merely prompt "be trustworthy".
- Track tools and models separately, with explicit sources and limitations; never invent successful MCP operations.

## 9. EXTERNAL REVERSE ENGINEERING LAB — MISSING SOURCE FIRST

Inputs: software owner legitimately obtains or has permission to inspect but does NOT possess source/documented internals: APK, EXE, DLL, native SO, binary plugin, firmware blob, protocol captures, proprietary formats, packaged resources and runtime behavior.
- Intake metadata (hash/origin/target/license), file-safety scan and isolated analysis first.
- Static: JADX/Apktool (Android), Ghidra/radare2 and language metadata, calls/strings/imports/resources, binary function diff. Dynamic only when authorized in isolated environment using Frida or instrumentation.
- Reconstruct **interfaces and behavior** when practical: function-level maps, ABI/API surface, message/schema formats, asset file structures, compatibility shims, alternate implementation specs, focused reproduction tests.
- AI explains confirmed findings versus hypotheses, confidence and evidence/source offsets, avoids promising exact source recovery. Source of external third party not magically available; no copying private keys, unauthorized access, rights or credentials.
- Integrate findings with Skill Studio and Compatibility Lab, not an automatic rewrite of a third-party program. Potential first target is a legitimately available, owner-selected closed-source format/program, not the other Asterion apps whose source already exists.

## 10. SKILL STUDIO — ACTUAL REUSABLE LEARNED PROCEDURES

- A skill is a versioned capability contract: name/description, input schema, preconditions, allowed apps/devices, typed steps/action graph, expected artifacts, verification assertions, retries, rollback, scope and test fixtures.
- Recorder observes ONLY opted-in successful tool traces; remove private data; propose reusable skill; owner may edit parameter types and policy; run dry-run in sandbox then real small-scope acceptance; publish after passing tests.
- Skill dependencies versioned; model may recommend skill reuse for recurring workflow; skill execution deterministic where possible, reducing inference latency.
- Skill metrics: success/false success, p50/p95 time, user interventions, resource use, regressions. Auto-suspend on repeated verified failures and revert to last passing version.
- Skill Studio is for command/process knowledge, not an external model weight trainer.

## 11. MODEL LABORATORY — MODEL RELEASE INTELLIGENCE AND PER-APP OPTIMIZATION

- Inventory installed models across Control and signed Asterion apps with provenance, file hashes, quantization, language/licensing, required RAM, actual tok/s, image/audio/3D-specialist benchmarks where app provides evidence, sizes and dependencies.
- Track original authors' verified GitHub/Hugging Face releases, model cards, CVEs/recalls/format changes; configurable daily/weekly scan, not cost-heavy continuous downloads. Distinguish announcement vs verified available files.
- Preliminary metadata filter (license, availability, model family/size, API changes); then request permission before candidate large download/training. On actual hardware benchmark model against per-app validated task sets, quality, speed, power, crash rate.
- Produce recommendation card: CURRENT / CANDIDATE / quality delta / throughput delta / memory/storage change / compatibility/licensing / expected improvement / regression risks / proposed change with rollback / owner Approve, Reject or Remind Later.
- Approval only authorizes controlled migration in that relevant app's project process, never blindly edits another developer's app. Control owns model registry, not other apps' internals. Maintain staged model support for old project assets.
- Trainability laboratory: labeled tool-call datasets, reusable evaluation harness, safe LoRA fine-tunes on available PC GPU/CPU as feasible; never promise competitive full-model training without hardware.
- Main goal reduce duplicated/too many models per application; respect owner strategy 1–2 purpose-built models per app where feasible and Asterion Art first priority for specialist-model optimization if/when relevant owners approve.

## 12. UNIVERSAL ASTERION APP INTEGRATION

- Build on existing v1 signed provider contract and optional additive v2 stream/event extensions, with on-device owner approval in both apps, signer pins, request IDs, allowlisted operations, consent expiry and output evidence; no unreviewed file/private log access.
- Apps: Core/Nexus, Art, Sound, Writer, 3D Foundry, Adaptive Study, Game (Pilot + Codex), KK, NoWorld, Rounder and future. Downloader engineer owns its provider and implementation; Control must NOT modify Downloader.
- Capability Registry must show REAL support, missing provider, incompatible version, permission denied, engine unavailable, running vs verified; no generic fake "supports all apps" status.
- Preserve each app's specialist models and exports; Control is planner, transport, auditor and skill runner only.
- Inter-app procedure example: locate a character asset, request Art asset using app API, verify output hash, request 3D adaptation, ask Sound for voice package, test Game compatibility—each step separately scoped and validated before declaring success.

## 13. EVIDENCE, DIAGNOSTICS, FILES, RESOURCE OPTIMIZATION

- Crash/exit/ANR when accessible, HTTP stage, process/job/queue, native accessibility assertions, active model status, file transfer checksums, app signer/version/commit and verified outcomes with common trace IDs.
- Immutable redacted incident snapshots, source-mapped repro scripts, actual prior/good vs failed diff, reproducible acceptance test matrix, export with hash and privacy controls.
- File access: secure Windows file roots, Android scoped storage and SAF, encrypted vault, dedup by content hash, atomic transfer/resume (not just queued), sample checksum and post-transfer actual existence.
- Android resource governor prevents local AI+VPN+voice+scanner+background cycles from simultaneously saturating RAM/battery/thermal. Priority: maintain Control connectivity/OS responsiveness, then active voice, verified user tasks, background scans, model training.
- Service health: Android foreground restrictions, Windows worker process survival, transport reconnect backoff/circuit breaker, stale-state UI, nonduplicating task/cycle recovery.
- Telemetry opt-in granular; no blanket logcat of other apps without legal Android authorization.

## 14. ORIGINAL 20 OWNER-APPROVED CAPABILITIES — DETAILED OUTCOMES

01 Skill Studio: versioned tested skill files, preconditions, safe replay, rollback.
02 Model Laboratory: per-app inventory, free-source release watcher, benchmark, explicit replace suggestion.
03 Knowledge Graph: indexed provenance links from project/repo/model/issue/asset to tested outcomes.
04 Project Inspector: read actual repos/app status and generate verified gap/completion board.
05 Automated Test Architect: source diff -> test suggestions -> real acceptance receipts.
06 Source Provenance Tracker: project commit -> toolchain -> signed APK -> installed package hashes.
07 Compatibility Laboratory: ABIs/APIs/versions/external binary behavior compatibility.
08 Package Manager: list owner-approved first-party apps/modules, version constraints, safe staged upgrades.
09 Workflow Replay Engine: semantically verified task replay, robust to UI coordinate changes.
10 AI Tool Profiler: segment inference/queue/transit/execution/verification, optimize p95 latency.
11 Crash Reconstruction: durable telemetry, timeline, root-cause evidence and repro confidence.
12 Network Route Laboratory: Wi-Fi/cellular, direct/VPN/Tor, exit IP, throughput/p95 latency and leaks.
13 Secure Sandbox Manager: quarantined external file execution, VM reset and evidence capture.
14 Voice Skill Builder: natural spoken commands -> typed owner-approved skill -> tests.
15 Cross-App Dependency Graph: app versions, schema/engine/model/export compatibility matrix.
16 Resource Governor: CPU/GPU/RAM/thermal/battery quotas and background scheduling.
17 Task Evidence Vault: redact, hash, encrypt and retrieve known-good receipts.
18 Recovery Manager: crash/network/model failure state restoration without unsafe replays.
19 Offline Research Library: versioned local docs, searchable technical evidence and citations.
20 Capability Registry: signed app provider discovery, available actions, missing/unavailable cause.

The rest of the earlier approved subsystems are also mandatory: malware/quarantine/provenance; privacy and credential security; networking/VPN/Tor; multi-model specialists; code editor/GitHub automation; installed app/permission/storage health; file sync; UI customization; reliability/monitoring; project indexing and local assistant memory.

## 15. NEW RECOMMENDATIONS — NOT YET OWNER-APPROVED (APPROVE LATER)

N01 Capability Contract Simulator: preview and validate a planned multi-app action DAG and permissions before any side effect.
N02 Regression Guardian: automatic A/B canary of known good scenarios after app/model/tool change; block promotion if failures.
N03 AI Confidence Calibrator: map model self-confidence to observed reliability; request deterministic verification where uncertain.
N04 Tool Failure Reproducer: minimize a failed job to smallest repeatable safe series, rank hypotheses by evidence.
N05 Supply-Chain BOM Auditor: track open-source dependency versions, licenses, vulnerabilities and model weight provenance across Asterion.
N06 Secret Broker: give time-limited scoped credentials to code/tools, never insert secrets in prompts or repos.
N07 Secure Research Browser: domain-aware extraction, local page snapshot, citation/source freshness, prompt-injection isolation, no paid search requirement.
N08 Policy-Aware Data Exchange: show which app/AI/tool receives each type of file or personal data before export, log choices.
N09 Backup & Disaster Recovery: encrypted Control state, app approvals, model/skill registry, checkpoints, restore drills preserving original signer.
N10 Declarative Configuration Studio: versioned owner settings with dry-run, diff, schema migration and safe undo.
N11 Multi-Device Topology Map: real endpoints, private routes, live trust status, failover/circuit-breaker visualization.
N12 Automated Research Watchlists: monitor selected documentation, protocol, model, dependency and security updates and generate actionable diffs.
N13 Differential Model Judge: on owner-selected ambiguous/critical tasks compare local and PC model answers, verify with tests, avoid trusting agreement alone.
N14 Artifact Reproducibility Checker: rebuilt APK/model/asset reproducibility where deterministic, source signer and byte-hash accounting.
N15 Adaptive Power Scheduler: schedule heavyweight model training and scans by charging/thermal/network state.
N16 App Compatibility Canary: launch and minimally exercise approved app UI after a Control-only change, preserving state and data.
N17 Offline Emergency Console: limited owner-authorized local debugging when Windows worker/network is down, with verified local-only status.
N18 Intent History & Undo Planner: before irreversible operation show predicted file/app impact, retain rollback when feasible.
N19 Failure-Budget Dashboard: measure per-project repeated failed builds, false finishes, time wasted and unresolved blockers.
N20 Project Intake Wizard: classify new repo/app/system, inspect ownership/source availability, create scope with constraints and acceptance tests.
N21 Research Provenance Verifier: compare source publication date, version validity and repeated claims against retrieved primary sources.
N22 Intelligent Storage Lifecycle: identify duplicate caches/model versions, compare safe reclaim plan, NEVER delete automatically.
N23 Accessibility Semantic Layer: foreground app/action graph and element identity stability, avoid coordinate click drift.
N24 Plugin/Adapter Sandbox: external MCPs and adapter tool packages isolated by allowed permissions, CPU, network and files.
N25 Recovery Drill Simulator: deliberately sever WSS/kill test worker/switch Wi-Fi in sandbox, verify no silent resends or lost task IDs.
N26 App Resource Negotiator: avoid Art + 3D + native AI + scanner exhausting phone GPU/RAM, prioritize user foreground work.
N27 Consent/Approval Inbox: batched short spoken and visual questions from long-running work, with explicit expiry and project context.
N28 Licensing/Cost Guard: reject mandatory paid endpoints, flag license restrictions and unavoidable costs before installing a dependency.
N29 Semantic Diff Assistant: source/config/model/graph differences explained against canonical spec with exact proofs.
N30 Personal Data Vault Connector: optional device-local private files retrieval through owner-granted SAF/URI scopes only, not arbitrary app storage.

Recommended earliest six additional modules: N02 Regression Guardian, N06 Secret Broker, N09 Backup & Disaster Recovery, N24 Plugin/Adapter Sandbox, N27 Consent/Approval Inbox, N28 Licensing/Cost Guard. These reduce risk from autonomous AI, cross-app access, external analysis and zero-cost rules. Others can be staged without becoming dependencies for basic Control.

## 16. IMPLEMENTATION DEPENDENCIES & PROPOSED ORDER — DESIGN ONLY

P0 Preserve & reconcile: inventory current source/runtime/signature without destructive changes; rebase contradictory old docs; define module API boundaries; keep owner approved frozen master.
P1 Kernel: unified state/permission/observable receipts + separate Action, Task, Overnight Cycle engines; fix manual_review state and verify actual ChatGPT responses and durable rollover contract; no full autonomy claims without real tests.
P2 Native AI + MCP: phone-inference quality gate, local model router, local memory, tool registry, PC optional, GitHub MCP (new client only), web retrieval and development tools; evaluate coding accuracy.
P3 Voice, Skills, Model Lab: independent wake/voice/TTS, owner questions, Sound packages, skill capture/test, release watcher + per-app model migration proposals.
P4 Security: auto Standard/Deep file scanning, quarantines, app package/supply-chain audit and privacy dashboard. Keep access profiles separately explained.
P5 Networking: confirmed free exit sourcing, full-phone authorized VPN, route selection, hard 75% throughput gate, actual 45min IP rotation, leak protection, separately isolated Tor and verified phone connectivity. This block can be designed in parallel but cannot be declared complete without real trusted free provider.
P6 Reverse Engineering & Development: Ghidra/JADX sandbox, external closed-source use cases, code compare, compatibility and evidence mapping.
P7 Ecosystem: signed approved adapters and capability registry for each Asterion app, no Downloader code changes; all 20 modules and any later-approved Nxx recommendations; canary+resilience+UI polish.
P8 Real device acceptance and signed APK: ONLY after explicit owner authorization and original signing identity verified; do not consume old reserved builds or replace installed app prematurely.

Dependencies: P0 precedes all mutations; P1 required for autonomous P2; P2 tool registry before P3 skill learning and P6 AI analysis; P4 scanner before external binary execution; P5 VPN not a prerequisite for offline native AI or existing private Control connectivity. V3 no-code hold applies to every P0–P8 implementation action, not just final APK.

## 17. VERIFICATION MATRIX — REQUIRED EVIDENCE BEFORE LABEL "FINISHED"

C01 Action latency: 20+ normal native tasks with real phone/PC p50/p95, model-inclusive time separately.
C02 Task DAG: 3+ independent parallel operations, verified postconditions, dependency cancellation, no double side effect after timeout.
C03 Overnight cycle: 2+ substantial work turns, real project/test evidence, persisted state after process kill, ChatGPT rollover across 20 total messages when that provider selected; manual_review resolves without duplicate.
C04 Native phone AI: genuine offline chat + tool invocation + local memory retrieval + language handling on device, memory/thermal scores.
C05 PC AI fallback: optional, accurately reports no PC available, never required for ordinary voice/phone operation.
C06 Voice: "Asterion" wake, French/English recognition, interrupt, user command, model response, unsolicited but task-relevant AI question and owner voice answer.
C07 Sound package: signed voice sample manifest validation, fallback TTS if Sound absent, reversible voice swap.
C08 Security: automatic Standard file scan and Deep risky APK/archive; known malicious test sample and benign false-positive case; quarantine and restore.
C09 Privacy: signatures/owner approval/caller cert, local-only secret storage, no private file upload, audit and export.
C10 VPN: real OS consent, full-phone route, verified remote IP/country, distinct IP change 30–60min, repeat twice, direct paired Control remains accessible.
C11 VPN performance: matched Wi-Fi/cellular comparative real throughput >=75% baseline, RTT target, fail budget reported truthfully if unmet.
C12 Tor: actual .onion via proper Tor mode without claiming full-device Tor performance equivalence.
C13 Cost: no paid API/network/model dependencies, no subscription or new infrastructure assumed; free exit scarcity recorded.
C14 GitHub: native AI reads exact owner repo/branch, makes small authorized test patch on disposable branch, runs tests, records verified commit, no unrelated writes.
C15 Reverse engineering: independently source-absent authorized external binary, static/dynamic evidence-backed API/format map, practical compatibility proof.
C16 Skill Studio: record, redact, test, version, replay, fail, rollback a real skill.
C17 Model Laboratory: detect original vendor model release, metadata/license review, real sample quality/speed benchmark, concrete owner approval request, no silent production replacement.
C18 Ecosystem: each signed adapter permissions, real happy path, real failure and output check; report unavailable providers, no Downloader source modifications.
C19 Health: crash/ANR where OS permits, signed APK/source/installed fingerprint, incident-to-repro mapping, redacted hash export.
C20 Offline/recovery: reconnect failures, battery/thermal throttling, no false connection or lost state.
C21 Premium UI: every control has live handler, correct status/error/cancel, accessibility and small-screen portrait/landscape.
C22 Owner key: the exact installed signing certificate and app data must be maintained for any later update.
C23 No-code hold: until explicit next authorization, repository activity is architecture markdown only; no runtime/Android/Windows source changes or builds.

Status truth labels: PROPOSED / OWNER_APPROVED_SPEC / IMPLEMENTED_SOURCE / STATIC_TESTED / BUILT / DEPLOYED / INSTALLED / DEVICE_VERIFIED / BLOCKED. These are separate independent fields; docs cannot set them to DEVICE_VERIFIED.

## 18. FEASIBILITY & DECISION LEDGER

A. Free, fast, geographically rotating VPN exits are the largest external dependency. Neither owning the phone nor compiling WireGuard creates remote exit servers. Without a reliable free provider and rotation access there is no guarantee of user-selected foreign IP or <25% loss. Feature must be BLOCKED not fake.
B. Tor hidden services can work through official Tor Browser or isolated proxy; they are a separate privacy routing context with different performance and the Tor Project warns against unnecessary VPN layers.
C. Fully GPT-6-equivalent native all-rounder not guaranteed on Samsung; open model quality must be benchmarked against actual tasks. Running LoRA training may require optional PC hardware, not cloud expenses.
D. "Restrictionless" refers to model content moderation preference; network/API terms, access rights and file safety remain separate.
E. Truly 24/7 voice+VPN+LLM+file scans at low battery and low heat is an engineering budget, not a guaranteed result; must measure and schedule.
F. External reverse engineering requires binary access and authorization, may be limited by obfuscation/encryption/DRM/license. Recover interfaces when possible; never assert magical full original code recovery.
G. Android private app data, root, system VPN controls, microphone startup and camera/capture permission are restricted by OS; never claim silent bypass.
H. Existing production server and original signer are assets: no unreviewed replacement, reset or migration.
I. Current observed cycle failure (manual_review) remains a live blocker and should not be shown as functioning unattended.
J. New modules proposed in §15 are suggestions, not owner-approved until explicitly accepted.

## 19. DOCUMENTATION-ONLY CHANGE RECORD

Design-only owner request 2026-11-15:
- Exclude SuperVPN completely and permanently.
- Fully specify all existing approved components and genuinely new suggestions.
- Explicitly PAUSE ALL CODING, including source implementation, app release packaging, device testing and provider setup.
- GitHub architecture docs may be committed because previous instruction asks to push design decisions; links must identify the active latest document and older frozen specs preserved.
- No changes to Asterion Downloader or any other app. No source writes or runtime operations from this design task.

## 20. GROUNDING LINKS AND TECHNICAL REFERENCES

- Android VpnService & always-on / one prepared VPN: https://developer.android.com/develop/connectivity/vpn
- Android VpnService API: https://developer.android.com/reference/android/net/VpnService
- Proton free server selection limitations, not adopted as provider: https://protonvpn.com/support/change-server-free-plan
- Official Tor Browser Android: https://download.torproject.org/tor-browser-for-android/
- Onion services: https://support.torproject.org/tor-browser/features/onion-services/
- Official GitHub MCP server: https://github.com/github/github-mcp-server
- Example candidate open-weight model card: https://huggingface.co/Qwen/Qwen3.5-4B
- Existing Control v1 API and cycle contracts listed at top remain governing implementation boundaries.
