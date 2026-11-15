> **IMPLEMENTATION AUTHORIZED 2026-11-15:** Owner says to develop the entire Control upgrade, not only its VPN. SuperVPN (com.jrzheng.supervpnfree) is EXCLUDED as an insecure/unusable candidate: no integration, no reliance, no recommendation. The prior architecture-only freeze on SOURCE IMPLEMENTATION is superseded, but the previous restriction on producing, transferring or installing an APK remains in effect until separately authorized. Preserve existing signatures, private Control connection and all other Asterion apps; Downloader is out of scope. A real free alternative must demonstrably meet security, available exits, IP rotation and <=25% measured throughput loss. Do not fabricate a free worldwide VPN network. Source/test progress and device acceptance are separate.

# ASTERION CONTROL V2 — Owner-approved independent AI, overnight cycles, cybersecurity, privacy and reverse engineering
Date: 2026-11-15
Status: SOURCE IMPLEMENTATION AUTHORIZED; NO APK PACKAGING/PUBLICATION/INSTALLATION/SIGNER CHANGE OR RUNTIME DEPLOYMENT WITHOUT SEPARATE AUTHORIZATION.
Canonical repository: Azrazieliz/Asterion-Comander
Working branch: work/control-0927-overnight-cycles-20261111
Preceding requirements: docs/7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md, docs/CYCLE_EXECUTION_CONTRACT.md, docs/CONTROL_CROSS_APP_API_V1.md, 7STAR_FROZEN_MASTER.md.
This file is additive. For the revised requirements below, the latest explicit owner instructions take precedence over older contradictory assumptions. Preserve older files and progress records for auditability.

## 0. Owner decisions, scope and non-negotiables

- Asterion Control is the universal phone/Windows operating, AI, development, cybersecurity, privacy and Asterion-ecosystem management platform. It DOES NOT become a replacement for the other apps' generation/rendering engines.
- Cost: free operation using open source, free licenses, existing Android/Windows devices and genuinely free services when technically possible. NO paid API, paid VPN subscription, compulsory cloud model, compulsory GPU rental, or automatic purchase. CPU, bandwidth, power, and paid third-party server availability remain actual physical/infrastructure constraints.
- Default AI: phone-native, optional PC-hosted AI. Cloud AI may be included only when genuinely free and optional; no reliance on it for normal operation. OpenAI/ChatGPT remains an OPTIONAL provider, not a foundational requirement.
- Content flexibility: locally hosted configurable open-weight model, no deliberately added cloud-vendor-style content filters or arbitrary content-category restrictions. Keep proper Android/Linux/Windows permissions, owner-issued authority, provenance, safe storage, credential isolation, destructive-operation validation and legally required constraints. Content freedom is NOT a request to disable machine safety or lie about external limits.
- Default network: full-phone VPN ON after initial genuine Android authorization and viable service provisioning; rotate actual public exit IP about once/twice per hour (30–60 min). Support automatic/country-preferred exits, dark-web/.onion browsing via separate isolated Tor mode, protected native Control connectivity. Other VPN installed? Never silently displace; owner chooses explicitly.
- VPN HARD performance requirement: no more than 25% sustained throughput loss relative to same-network direct baseline (VPN throughput >= 0.75 × direct), and target <= 25% increase in measured RTT/p95 latency. No fake speed measurements or unverified IP rotation. The threshold must be measured on phone Wi-Fi and cellular; auto-select/re-evaluate routes, state degradations honestly, never secretly bypass privacy or switch off kill-switch. If there is no route meeting policy, declare requirement BLOCKED / degraded, ask for owner choice between privacy and performance, never claim both were met.
- The owner has NO geographic remote hardware/server infrastructure. Do not plan as though foreign exit machines exist. Geography and IP rotation depend on honestly obtainable, free exits (or Tor with separate limitations); cannot promise guaranteed countries, unlimited automated rotation, high throughput or zero external cost without working providers.
- Existing free VPN app precedent: SuperVPN (com.jrzheng.supervpnfree) is owner-REJECTED and expressly OUT OF SCOPE due to privacy/security concerns and unavailable verified integration. It must never be a selectable Control provider, dependency, default or fallback. Preserve reference to this decision only as a negative historical record.
- Android VpnService permits only ONE prepared VPN application; the owner must consent to Control replacing an existing VPN. VPN must not break existing Control direct WSS, pairing or credential state. Provide explicit owner override/disable.
- File cybersecurity/privacy are ONE user-facing Security & Privacy module. Access levels Normal/Developer/Lockdown/Custom are permissions profiles, NOT scan severity profiles. File scan default: automatic STANDARD, auto-DEEP for risky file types; quarantine with reversibility, no false "guaranteed clean."
- Reverse engineering means analyzing software, binaries, APKs, firmware, protocols and data formats for which the owner DOES NOT already have source/implementation. Target external closed-source/undocumented/otherwise unavailable systems, not just one's own Asterion binaries. Tool-supported analysis does not guarantee original code recreation, permission to distribute third-party source/keys, or ownership. Support legally authorized interoperability, compatibility and security research without automatically inventing private assets or bypassing access controls.
- The user approved ALL concrete capability modules listed in section 9, including Skill Studio and Model Laboratory. For every system distinguish planned, implemented, compiled, deployed, installed, and device-verified. Design approval is NOT permission to build.
- NO development, patching, testing or source writes inside Asterion Downloader from this Control scope. The owner explicitly assigned Downloader to another project owner. Control may eventually consume a signed, opted-in general adapter from other apps; do not modify their source now.
- Preserve existing signed Android application com.asterion.control, native phone/PC pairing, WSS, Windows worker, working GitHub fallback bridge, Android data, repositories, provenance, other apps, installed models and secrets. Do not resurrect retired MCP gateway/duplicate pairing. GitHub MCP for the NEW local AI is a separate OPTIONAL tool client and must not be confused with the retired ChatGPT-to-Control gateway.
- No APK update, build, signing, installation, remote deployment, new paid service, auto VPN enable, or device mutation from this architectural documentation change.

## 1. Separate THREE execution units permanently: action, task, overnight development cycle

A. ACTION: one authorized observation, UI interaction or native API operation. Measure model decision, queue, transport, device execution, verification, result. About 1 second for simple native gestures and target under 10 seconds inclusive of AI/tool overhead where achievable, with observed p50/p95 and truthful limitations. An action is NEVER an "overnight cycle."

B. TASK: finite dependency graph of actions with verified desired outcomes, idempotent job IDs, durable steps, explicit retry policy, cancellation and evidence. A task might run for seconds or hours. It is NOT a development cycle just because it contains multiple operations.

C. CONTINUOUS OVERNIGHT DEVELOPMENT CYCLE: long-running sequence of SUBSTANTIAL PROJECT ADVANCEMENT TURNS, repeatedly and automatically issuing requests to the selected AI operator, applying actual source changes, performing builds/tests where explicitly authorized and resolving failures. Owner starts, pauses, resumes or stops. One turn aims for ~30 min substantial development; 25 min warning is a progress/quality heuristic, NOT a mandatory idle time. A cycle may span many turns/chats/nights and must stop at verified DONE or owner stop, not an arbitrary 10/20 turns. Maintain repository handoff plus durable cycle state across process and conversation changes. ChatGPT-specific rollover after 20 total messages in one chat is a transport/provider adapter, NOT the definition of a cycle; local AI need not roll over ChatGPT chats.

ACTUAL EXISTING SCREENSHOT OBSERVED 2026-11-15:
- Development cycle STOPPED, active=false, current turn=1, verified replies=0, current chat 0/20, automatic rollovers=0.
- Continuation enabled=true, checkpoint requires_manual_review, error "Prior ChatGPT submission needs an operator review".
- Never claim continuous overnight operation is verified. Troubleshoot actual pending/unconfirmed Send and reply acknowledgment; never blindly resubmit after uncertain submission.
- Native existing AndroidMcp reports android_autonomous_cycle=false; ChatGPT checkpoint queue/dispatch/ACK works at source level but overnight completion and rollover NOT proven.

REVISED CYCLE FLOW:
1. Explicit owner-authorized start + canonical project branch/spec/acceptance/current checkpoint and tool permission scope.
2. Acquire/validate durable lease, unique cycle ID, turn ID, request ID, provider ID and model ID; capture project and build/release state.
3. Choose the next meaningful task from outstanding verified project work; submit to available AI via native local model, optional PC AI, or optional external provider adapter.
4. Receive REAL reply/structured action plan (no guesses), run approved tools, persist source changes, run tests and gather acceptance receipts.
5. Evaluate tangible project progress; classify genuine DONE vs CONTINUE vs FAILED vs OUTCOME_UNKNOWN vs OWNER_REVIEW.
6. Keep compact canonical state/memory; provider-specific ChatGPT chat rollover ONLY when required, verify the new actual chat and transferred context.
7. Recover after crashes, sleep, network handovers, model context exhaustion and UI changes using same immutable request IDs, without duplicate sends/destructive actions. Pending uncertain outbound operations do not auto-repeat.
8. Next substantial turn automatically until project completion, owner stop/pause or genuine blocker. AI-originated question may use voice subsystem; unanswered approval remains paused and recoverable.
9. Provide live owner summary and final report: actual commit, tests, artifacts, device outcomes, issue counts, elapsed substantive work; never present zero-verified replies as active success.

ACCEPTANCE: deliberate crash during a multi-turn cycle resumes; at least 2+ verified meaningful turns, no duplicate send, verified chat rollover across 20-message threshold for ChatGPT provider, concrete real project output and owner-controlled pause/resume/stop. Normal action and cycle status are entirely independent in the UI.

## 2. Native all-rounder AI: task-capable, trainable, ecosystem-aware

- Primary on-device local LLM, optional more capable PC model and optional truly free external model. Evaluate candidates by real Samsung Android 17 memory, sustained tok/s, first-token latency, thermal/power, native tool-call accuracy, coding, research, French/English, context and quality. No predetermined model guarantees GPT-6-level reasoning.
- Runtimes: evaluate llama.cpp/Android, quantization formats/hardware providers and alternatives only after benchmarking. Asterion Intelligence uses local secure tool contracts, not screen-scraping ChatGPT.
- Explicit distinct systems: natural-language planner, deterministic task scheduler, persistent knowledge graph/RAG, episodic project memory, tool registry, retrieval/web browsing with citation/provenance, development worker, evaluation harness, model management, permission engine, audio interface.
- General chat, web research, deep analysis, code generation, repository browsing, debugging, tests/build orchestration, reverse engineering, file understanding, scheduling and all Asterion app capability orchestration. No need for duplicate image/video/audio/3D generation models inside Control; call each specialist app.
- Trainability: (1) editable private memory and retrieval, (2) versioned Skill Studio workflows derived from VALIDATED executions, (3) curated evaluation + LoRA/QLoRA fine-tuning when hardware allows. No automatic blind "self-training" from failures or raw sensitive conversations; model training artifact retains base model/license/benchmark/evaluation.
- Native model's content policy is owner-configurable; avoid adding artificial cloud-style content filters. System access remains governed separately by owner consent, OS constraints, app signature verification, secret isolation and verified destructive operation boundaries.
- Provider switching does not erase task/cycle checkpoints; preserve existing working model datasets and never require external paid API keys.

## 3. Bixby-class voice and Asterion Sound voice packs

- Local wake word "Asterion", streaming recognition, barge-in/interruptions, bidirectional natural multi-turn voice dialog, multilingual (French/English), offline fallback, accurate transcription, explicit microphone state, background speech only where Android service permissions allow.
- Voice requests submit DIRECT native Control tasks; they do not need a ChatGPT composer. Existing wake/recognition/TTS/PendingVoiceStore code is foundation, not complete conversational assistant.
- During authorized tasks or overnight cycles, AI may proactively ask owner decisions by voice, pause for response, and resume without losing task context. No unrelated unsolicited questioning.
- Replaceable, signed, versioned voice profile packages including language, pronunciation dictionary, synthesis model, sample rate, voice/persona metadata, validity checks. Future Asterion Sound produces packages; until then use independent free offline TTS and never block Control waiting for Sound.
- Audio playback coexistence/music-safe focus policy, battery-sensitive local wake detection, speaker-verification optional and not a substitute for Android owner authorization for sensitive operations.
- Measurable recognition accuracy, wake latency, response latency, false triggers and battery drain on actual device.

## 4. Security & Privacy — malware scanning AND access controls

UNIFIED user area with independent subengines:
- File ingest monitor for Android Downloads/MediaStore/content shared via SAF/Control transfers and opted-in partner exports; Windows filesystem watcher for authorized roots. Stock Android cannot read arbitrary apps' protected private data.
- Default STANDARD automatic scanning, auto-DEEP for risky APK, EXE, DLL, scripts, archives, macros/docs, firmware, binary models and malformed file containers. Quick/manual/Standard/Deep/Maximum selectable profiles.
- Hash + true file type + metadata + cryptographic signature + ClamAV-like signature engine + YARA-X-like rules + dangerous archive recursion, expansion and time caps + heuristic/risk classifier. Remote cloud reputation ONLY if free/owner-approved; never upload private samples implicitly.
- Outcomes: confirmed malicious, suspicious, no known threat detected, unscannable, aborted/partial. "No known threat" != guaranteed clean. Quarantine with reversible restore and owner policy, never silently destroy existing data.
- Optional isolated Windows VM/container sandbox for unknown binaries, no untrusted code on host without isolation. Behavioral evidence and provenance stored without dumping private contents into logs.
- File hash/version cache, model and APK signature verification, suspicious app permission review, network/DNS leak checks, credential auditing, encrypted security journals, incident correlation, policy notifications, integrity monitoring and emergency disconnect.
- Previous access levels Normal/Developer/Lockdown/Custom are *remote privilege configurations* not file scanning profiles. Keep least privilege and explicit elevated authorization on owner-approved device; the new content-flexible AI model is independent from these access-level toggles.
- Handle security findings without automatically changing other apps. Existing signing/data/pairing preserved.

## 5. VPN, rotating exits, privacy, Tor and HARD 25% speed gate

- FULL-PHONE traffic protected by default after real user VpnService authorization and a working config; reconnect on reboot/background where Android permits, don't claim enabled until verified tunnel and IP. Existing private Control WSS must remain reachable/isolated.
- IP rotation desired every 30–60 minutes (default 45 min) with actual external IP check before and after, country preference/automatic/fixed, provider/exits pool, intelligent network switching, TTL, avoid interrupting ongoing critical sessions, schedule/backoff and misbehavior logging. SAME IP twice != successful rotation.
- User owns no remote machines in foreign countries; zero-cost geographic exit coverage cannot be guaranteed. Provider modules must discover supported free exits, verify current terms, publicly offered APIs/config import, speed/reliability and provenance. No fabricated foreign host, server rights or endpoint.
- SuperVPN rejected by owner: NO provider integration, no automated external UI routing, no fallback, no recommendation. Support only independently verified free providers with lawful usable configs or owner-authorized direct Tor mode; report unavailable options honestly. The one-active-VPN-app limit remains.
- Android supports only one prepared VpnService, so Control cannot simultaneously own its own WireGuard VPN and SuperVPN's tunnel. If SuperVPN stays selected, Control offers read-only VPN status/speed/IP and honest manual transitions, NOT false native rotation.
- Evaluate audited free providers or free compatible WireGuard/OpenVPN configs if actually exposed; do not rely on paid tiers to meet default. Private WireGuard device pairing and commercial exit VPN are separate.
- Tor mode: Tor-aware isolated browser/proxy and .onion access, separately reported as slower/possibly failing the 25% performance constraint; never promise default full-phone Tor speeds or enforce country-specific Tor onion exits. Do not misrepresent anonymity, DNS protections or traffic encryption.
- HARD GATE: on same phone/network/endpoint period, baseline direct sustained throughput T0, VPN throughput Tv >= 0.75*T0; record repeated samples, uncertainty, p50/p95, upload/download, real network transitions. Target VPN latency Lvpn <= 1.25*Ldirect (p95 also recorded). Report "FAILS_SPEED_BUDGET" if below threshold, compare candidate exits, keep privacy-first/owner selected fallback and never bypass a required tunnel silently. No unaudited switch to unprotected network or fake "rotation succeeded."
- Android full-device VPN versus Tor interaction, competing apps, OS always-on setting and user revocation must respect Android OS permission model. Leak tests must include DNS/IPv4/IPv6, WebRTC where observable, transport identity and Control return path.

References:
- https://developer.android.com/reference/android/net/VpnService
- https://developer.android.com/develop/connectivity/vpn
- https://play.google.com/store/apps/details?id=com.jrzheng.supervpnfree
- historical independent security review: https://www.top10vpn.com/reviews/supervpn-free-vpn-client/

## 6. GitHub MCP and trusted self-directed coding

- Use official GitHub MCP Server as OPTIONAL tools inside local/PC Asterion Intelligence; source https://github.com/github/github-mcp-server . This is NOT the retired ChatGPT-to-Control HTTP MCP gateway; preserve the existing private GitHub bridge as ChatGPT fallback.
- Scopes: read repository/branches/issues/PR/actions; optional guarded write/edit/commit/PR/workflow after owner-approved permission grants. No hardcoded tokens; use scoped credentials in OS-backed store; redact logs.
- Code workflow: inventory active branch/dirty files; inspect prior tested decisions; plan minimal diff; make small branch/patch; perform static analysis/compile/regression; compare output against original requirements; verify artifact SHA/signature/version; commit/PR only verified changes; rollback safely on failures. Do not let the model mark work done based on tool ACK or untested code.
- Train using source-grounded tasks, tool-call trace correctness, regression failures and validated resolutions. Build a benchmark of real Asterion repo issues without modifying any app outside explicitly permitted scope.
- Time-consuming cross-device code/test workflows run as durable tasks or as steps of a distinct long-running overnight cycle. Require signed/typed tool calls and idempotent commit receipts. Risky destructive commands require additional owner scope even if text content has no model moderation layer.
- Internet browsing/research with identifiable citations and verified source freshness; cost-free internet access means using owner's connection without paid API requirements.

## 7. External reverse-engineering and compatibility laboratory

Primary OBJECT: systems, apps, firmware, APIs, protocol/file formats and binary components NOT already possessed as source by the owner; analysis targets third-party closed-source/undocumented systems and available binaries, not only self-owned Asterion project files.
- Intake external APK, EXE, DLL, SO, binaries, ROMs, saved traffic traces, schemas, software packages or observable apps as the owner makes available. Never pretend inaccessible binary/source/assets exist or automatically steal private downloads. Tools can inspect third-party binaries legitimately available for inspection or authorized research.
- Static: JADX/Apktool for Android, Ghidra/radare2 for native, binary strings/symbols, file structure and dependency maps.
- Dynamic: safely isolated authorized instrumented runtime, Frida/ADB debugging where permitted, behavior capture, IPC and error-stage tracing, controlled compatibility tests.
- Compatibility reconstruction: identify invocation protocols, exported capabilities, file formats, undocumented but locally observed behavior, adapters, data import/export, replacement component candidates, source-mapping hypotheses. Decompilation is approximate and not guaranteed to recreate original code or bypass all technical protections.
- AI-generated evidence-backed function maps, confidence/provenance/citations, diff across versions, semantic behavior tests, regression snapshots and reproducibility.
- Preserve trade secrets/credentials, third-party licenses and distribution permissions; avoid publishing someone else's proprietary extracted source or passwords. Source absence should yield evidence-backed unknowns, not fabricated contracts.

## 8. Asterion app orchestration and integration contract

- The native model coordinates existing Asterion specialist systems via signed, owner-approved v1 provider protocol and future additive versions. It does not install a second engine inside each app. It may discover capabilities, request actions, observe progress, collect sanitized evidence, verify output.
- App targets: Art, Core/Nexus, Sound, Writer, 3D Foundry, Adaptive Study, Game/Pilot/Codex, KK, NoWorld, Rounder and other present/future apps. Cross-app source changes must be separately authorized/owned; no Downloader work now.
- Model Laboratory stores app/model ownership, performance baselines, resource budgets, provenance and rollback versions. Follow open model releases from model hub/repository/RSS sources on a configurable cadence (suggest daily/weekly). For each release read license/format/size, actual benchmark relative to app task, quality, security/provenance, RAM/thermal, adoption risk and compatibility. Notify owner with a SPECIFIC recommendation and proof, NEVER auto-replace a production model solely because it is newer.
- Skill Studio creates, versions, tests, scores, activates and rolls back reusable cross-app and development skills based on genuinely successful tasks. Skill parameters include preconditions, permissions, assertions, side effects, checkpoints and safe idempotency.
- No uncontrolled app update or new AI model download; Model Lab may propose and request approval for a change. Show update cost in storage/download/time rather than promising free unlimited resources.

## 9. ALL approved concrete systems: implementation contract

All the following named modules are IN SCOPE, not optional brainstorm. Exact division into class/repo names may change after code inventory. Every visible UI action must call a real handler. All remain planned unless proven otherwise.

01 Asterion Skill Studio — record, parameterize, validate, reuse and revert skills.
02 Model Laboratory — release tracking, compatibility/benchmarks, fine-tuning, cross-app model-change recommendations.
03 Knowledge Graph — correlate projects, repositories, binaries, models, installed versions, tasks, incidents and lessons.
04 Project Inspector — evidence-backed implemented/tested/blocked/missing matrix per project.
05 Automated Test Architect — derive regressions from source diffs, invariants and real failure traces.
06 Source Provenance Tracker — source branch/commit → build process → APK signing identity → installed device hashes.
07 Compatibility Laboratory — Android, ABI, external binary and SDK dependency behavior.
08 Asterion Package Manager — inventory first-party modules with authorized safe update/rollback.
09 Workflow Replay Engine — reproduce approved flows using state assertions and idempotent events.
10 AI Tool Profiler — segment model, queue, transport, execution, verification, user return.
11 Crash Reconstruction — correlate structured events, process exits, source mappings and root-cause confidence.
12 Network Route Laboratory — direct/VPN/Tor route measurements and country/IP evidence.
13 Secure Sandbox Manager — reproducible Windows isolated execution and environment teardown.
14 Voice Skill Builder — owner speech patterns → bounded tested task templates.
15 Cross-App Dependency Graph — identify version/interface/model dependency breakage.
16 Resource Governor — thermal, battery, memory, CPU/GPU/radio and AI contention limits.
17 Task Evidence Vault — private hashed durable artifacts, traces, receipts, export/redaction.
18 Recovery Manager — watchdogs, outage detection, safe resume and nonduplicating replay policy.
19 Offline Research Library — index local technical docs, sources and owner-approved web material.
20 Asterion Capability Registry — dynamic per-app signed capability discovery and permissions.

Additional approved subsystems:
- Cybersecurity: hash/reputation, sandboxing, rule/signature management, file provenance and quarantine.
- Privacy: encrypted vault, DNS/IP leak diagnostics, network visibility and authorized per-app routing.
- Network: route scoring, adaptive handover, secure reconnect and bandwidth controls.
- AI: specialist registry, multi-model evaluation, project memory, retrieval and iterative skill learning.
- Development: code editor, GitHub MCP, diagnostics, reverse engineering, build/test/rollbacks and signature verification.
- Device management: storage analyzer, resource/thermal status, installed-app inspector, owner-granted permissions matrix.
- File systems: duplicate detection, integrity checks, encrypted file vault, atomic/resumable transfers, cross-device sync.
- Reliability: failure injections, immutable receipts, crash recovery, stale-state detection, checkpoint restoration.
- UI: polished minimal dashboards; distinct screens for ordinary tasks, overnight cycles, voice, models, VPN, security/scan, development, evidence, app integrations and settings.

## 10. Cost-free infrastructure policy and feasibility gates

- No mandatory subscriptions, paid model endpoints or rented foreign VPN exit servers.
- Open-weight model licenses and third-party tool licenses must be individually compatible with intended personal deployment; "free" and "open source" are not interchangeable.
- Actual phone/PC thermal, battery, compute and storage budgets determine runnable models and training feasibility; PC-assisted training is conditional on owner machine's real capabilities.
- Free worldwide exit nodes and specific country availability are NOT guaranteed; even free unlimited bandwidth claims require measurement and valid terms. A free VPN with ads still has indirect privacy/commercial tradeoffs, and must pass technical audits.
- Tor can provide onion access but can exceed 25% performance threshold; route mode must signal budget failure rather than claim universal compliance.
- Android cannot globally read all other applications' private files/operations or secretly enable system VPN; no root/Android permission fantasies.

## 11. Test matrix before ANY release approval

R01 Screenshot checkpoint truthful: cycle STOPPED/manual review with zero verified replies, not "running".
R02 Normal action remains separate and independently measured.
R03 Multi-turn overnight cycle performs two genuine substantial turns with source artifacts and observed ACK.
R04 Simulated ChatGPT uncertain send is NOT repeated; real reply verified; 20-message rollover preserves task if ChatGPT chosen.
R05 Crash/reboot/network loss restores cycle checkpoint, no duplicate action or lost project progress.
R06 Local model can answer general prompts and use typed native Control tools offline.
R07 Native model can search web when connected, with provenance; no paid dependency.
R08 Native/PC model accurately edits code and runs regression using GitHub MCP without touching unrelated repositories.
R09 Skill Studio creates, benchmarks, replays and reverts a real owner task.
R10 Model Laboratory discovers new open-weight release, compares against per-app requirements, requests approval; does NOT unilaterally update.
R11 Bixby-class local Asterion wake, two-way natural voice, assistant-initiated question, interruption and Sound voice-pack fallback.
R12 Automatic STANDARD scan on incoming accessible file and auto-DEEP for risky file types, redacted report and quarantine/restore.
R13 Protect clean data from false positives, reject unscannable archives by correct status; no arbitrary app-private storage access claim.
R14 Full-phone VPN consent and actual tunnel; external exit IP verification after activation.
R15 At least two actual IP changes in a long test interval, 30–60 minute rotation, no unsupported country claim or broken Control route.
R16 Same-network throughput >=75% non-VPN baseline; p95 RTT target <=125%; record fail and privacy-preserving owner choice.
R17 Correct behavior when ANY unrelated VPN already owns Android VpnService; no competing second tunnel, silent revocation or SuperVPN dependency.
R18 Tor/.onion mode genuinely reaches supported service and is labeled separately from VPN speed/privacy.
R19 External binary without available source is analyzed with evidence-backed function map; no fabricated reconstruction.
R20 App integration validates signer, owner approval, one real operation and one failure without changing app-owned engine.
R21 No costs charged, paid services invoked or paid credentials required.
R22 Correctly signed original Asterion Control APK, version, hash and installed package/data retained.
R23 End-to-end device acceptance including true on-device latency and battery/thermal impact, without synthetic "pass".
R24 All 20 concrete capabilities available as implemented or plainly marked incomplete; no dead buttons.
R25 Android service resilience, phone/Windows session recovery and no privilege escalation.
R26 Secure export of failure evidence without leaking private data.
R27 AI content configuration independent from OS/tool authorizations, with no imposed cloud moderation layer.
R28 No Downloader code modified, built or installed by Control work.

## 12. Implementation/verification truth as of this design commit

- PREEXISTING VERIFIED: authenticated original paired Control phone/Windows worker; native direct WSS checks; mixed-device native sessions; deployed Windows SQLite diagnostics and SSE stream. Precise limits in PROGRESS and prior dated reports. Do not extrapolate to full 7-star acceptance.
- PREEXISTING SOURCE COMMITTED AND SOME TESTED: Android event journal, owner security levels/permissions UI, optional WireGuard GoBackend, signed app-bridge source; durable Windows session receipts/trace evidence/resumable transfer source. Not installed or fully system-accepted as revised package.
- BLOCKED PACKAGE: Android release signing requires same original owner key; no replacement key or destructive uninstall. Prior online Gradle packaging reached packageRelease and failed because ownerRelease storeFile env not set; this is not proof of a signed APK.
- KNOWN CYCLE SCREEN 2026-11-15: STOPPED / requires_manual_review / prior ChatGPT submission uncertainty, 0 verified replies, no rollover.
- IMPLEMENTATION AUTHORIZED, NOT YET COMPLETE: always-on rotating geo-exit VPN, integrated Tor routing, malware scanner/quarantine, native all-rounder AI, Model Lab/Skill Studio, general reverse engineering, official GitHub MCP inside AI, true native autonomous overnight cycle and advanced voice assistant. Design is approved; source implementation and physical acceptance NOT implied.
- CURRENT OWNER INSTRUCTION: implement Control source and run non-installing tests; do not package/publish/install a new APK or change device/runtime without subsequent authorization.

## 13. Primary references and unverified research

Android official: https://developer.android.com/reference/android/net/VpnService ; https://developer.android.com/develop/connectivity/vpn
SuperVPN free Play listing: https://play.google.com/store/apps/details?id=com.jrzheng.supervpnfree
Older independent security evaluation (not proof current installed APK is same): https://www.top10vpn.com/reviews/supervpn-free-vpn-client/
Official GitHub MCP: https://github.com/github/github-mcp-server
Control source contracts: docs/CYCLE_EXECUTION_CONTRACT.md, docs/CONTROL_CROSS_APP_API_V1.md, docs/7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md
