# ASTERION CONTROL — OWNER-APPROVED 7★ SCOPE EXPANSION

**Date:** 2026-11-15  
**Status:** Owner-approved **design/implementation requirements ONLY**. NOT a claim that this functionality has been implemented, compiled, installed, or verified.  
**Repo/branch:** \`Azrazieliz/Asterion-Comander\` / \`work/control-0927-overnight-cycles-20261111\`  
**Companion:** [Galaxy AICore / VPN feasibility](ASTERION_CONTROL_GALAXY_AICORE_VPN_FEASIBILITY_20261115.md)  
**Previous 7★ baseline:** [Universal Control contract](7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md)

> **DO NOT BUILD YET.** No APK/package generation, Android install/uninstall, signing change, active VPN switch, data migration, pairing reset, model download, public cloud deployment, or production-worker replacement without a new explicit owner instruction. **DO NOT work on Asterion Downloader** in this Control assignment.

## A. Non-negotiable owner requirements

1. Preserve all existing Asterion Control designs, paired Android/Windows device service, native secure WSS, operating worker and fallback GitHub bridge, installed app signature/package \`com.asterion.control\`, locally installed models, owner accounts/tokens/settings and all other Asterion apps. Use the existing sources and approved infrastructure; do not rebuild or replace it.
2. **No mandatory recurring or per-use cost:** no paid cloud AI, API calls, licensing, subscriptions, foreign VPSs or paid VPN exit servers. Free online services may be optional if their real limitations and privacy terms are disclosed; phone and existing PC are the only assumed compute resources.
3. Security includes BOTH **cybersecurity and privacy**. The previous Normal/Developer/Lockdown/Custom **remote-access permission modes** remain, but are NOT file-scan levels or content moderation policies.
4. Local AI should support a broad range of content and user-controlled prompts without adding an artificial, OpenAI-policy-based content-filter layer. Choose open-weight models and allow user personalization. Do not pretend third-party models or Android system AI services are free from their own hardcoded behavior. Retain essential ownership/authorization checks for tools, device actions, secrets, and irreversible operations; model content flexibility is NOT unrestricted system privilege.
5. Full-phone VPN on by default **after** real Android OS VPN consent and provisioning, public exit rotation every 30–60 min (target 45 min), real selectable country endpoints when available, optional Tor/onion access, and no degradation in measured throughput exceeding 25% versus comparable unprotected service. Preserve secure phone/PC Control traffic. Owner has NO machines/servers abroad. Owner's historical free VPN: \`com.jrzheng.supervpnfree\` (\`https://play.google.com/store/apps/details?id=com.jrzheng.supervpnfree\`); do not assume its free service offers third-party programmable routing or rotation.
6. **Normal actions and overnight development cycles are strictly DIFFERENT systems.** No 25–30-minute work-duration concept, ChatGPT rollover, or cycle turn count in the ordinary control-action engine.
7. Voice assistant should approach Samsung Bixby's usability, but not its limited reasoning: locally wake on **"Asterion"**, carry on natural conversation, allow the assistant to initiate spoken questions while working, and accept owner replies tied to the correct pending task. Asterion Sound voice packages should be accepted when available; Sound is currently not operational and MUST NOT prevent baseline voice.
8. Native generalist Asterion Intelligence: independent on-phone open-weight LLM, optional existing PC model, no paid cloud. Tools, internet retrieval, coding, debugging, GitHub MCP, reverse engineering of **things the owner does not already possess**, access to app-owned specialist engines, trainable skills and versioned memory. Do NOT duplicate Art/Sound/Writer/3D media generation in Control.
9. Skill Studio, Model Laboratory, public model-release monitoring with conditional requests to swap specialist models in other Asterion apps, AND every additional concrete system in Section I are **approved future implementation scope**. Never silently install a new model into another app.
10. Galaxy AICore is a possible **supplementary** local Android inference provider; evaluate real SDK/API availability and device behavior. It must NOT become a prerequisite for the unrestricted primary native model, offline assistant or overnight cycles.
11. Owner specifically wants **reverse engineering for missing software, unavailable source, unknown formats, and things they do NOT already have**, not spending effort decompiling existing first-party source already in their repos.
12. Only after the owner separately authorizes construction may an APK be built. All implementation must be genuinely tested in isolation and ultimately with owner-signed on-device acceptance.

## B. Two independent execution systems

### B1. Ordinary Control action engine — quick device/project operations
- Inputs: text, voice, installed AI tool call, owner UI, approved automation.
- Bounded task graph, typed preconditions/postconditions, phone+PC native executors, network/permission availability, idempotent request IDs, cancellation, dependency-aware concurrency.
- Accurate outcomes: \`running\`, \`verified\`, \`failed\`, \`outcome_unknown\`, \`not_supported\`, \`permission_required\`; never equate a tap or transport ACK with completion.
- Optimize semantic native actions, low-latency verified results, correct device state, real p50/p95; no arbitrary wait per action. **No chat rollover, cycle turn number or "30 minutes per action."**

### B2. Continuous OVERNIGHT development cycle — automatic substantive project advancement
- Explicit owner-enabled project/work goal, sequential substantial development turns, automatic next **project-specific request**, real reply observation, source/build/test/artifact evidence, priority decisions, quality gates, persisted status, morning report.
- ChatGPT-backed cycle: after verified response and real advancement, generate next request and submit through currently supported owner-authorized ChatGPT UI, verify correct conversation and new reply. Use exact original ChatGPT chat as far as possible; automatically roll over to a new chat only when needed, carrying a durable context and checkpoint, preserving correct project and source identifiers.
- Native-AI-backed cycle: use independent local/PC model without ChatGPT GUI or 20-message rollover; still require substantial output and verified tests/receipts.
- Owner's screenshot on 2026-11-15 shows \`stopped\`, \`active=false\`, \`turn=1\`, \`verified_replies=0\`, \`0/20 messages\`, \`rollovers=0\`, \`continuation=true\`, \`requires_manual_review\`, prior ChatGPT submission operator-review error. This demonstrates a **blocked cycle**, not a completed overnight turn.
- Existing per-substantive-turn target \`~30 min\` with \`25 min quality warning\` applies ONLY here and is not proof of work quality. Allow early genuine completion if artifacts and tests prove progress.
- Durable cycle ledger should include: \`cycle_id\`, \`project_id\`, \`goal\`, \`source_reference\`, \`turn_id\`, \`request_id\`, \`conversation_id\`, \`next_request\`, \`submission_phase\`, \`reply_id\`, \`reply_verified\`, \`test_artifacts\`, \`build_signature\`, \`checkpoint\`, \`time_budget\`, \`failure_class\`, \`expected_next_action\`.
- Ambiguous send => \`requires_manual_review\` with enough redacted evidence to reconcile the pending request, **NO blind resend**. Local watchdog and task resumes must never double-send or destroy the previous chat.
- Distinct \`start/pause/resume/stop\` actions and protected owner override; no forced restart/prompt when cycle is stopped.
- Acceptance: simulate uncertain send, disconnect, model context compaction, forced app restart and genuine two-substantive-turn cycle; zero duplicate destructive or chat-send actions, maintain exact project and evidence.

## C. Asterion Intelligence — independent trainable local AI

**Core:** open-weight LLM on the phone with independent runtime such as llama.cpp, optional existing Windows AI acceleration; no mandatory paid endpoints or external login. Open-weight "all-rounder" benchmark requirements: coding, debugging, web/document research, repository inspection, planning, reliable tool calling, French/English, question answering, working memory and project management. Characterize actual RAM, GPU/NPU, generation speed, battery and thermal before choosing size/quantization. Don't promise equivalence to GPT-6 based solely on parameters.

**Architectural elements:**
- Asterion AI provider API: \`local_primary\`, \`pc_local\`, \`aicore_optional\`, \`free_external_optional\` (only where genuinely free).
- Router chooses by task complexity, privacy, device resource budget and measured output quality. Local primary must still function without Internet.
- Tool registry: Control native actions, GitHub MCP, authenticated files, browser/web retrieval, terminals, build/test execution, app capability registry, security scans, VPN reporting, voice, reverse engineering, Skill Studio, Model Laboratory.
- Structured tools with correct schemas, permission scopes, idempotent receipts, sandbox/working branch for code, test/compile evidence and audit. Do not give an LLM remote unrestricted OS access as a side effect of content freedom.
- Persistent local project graph and evidence-backed retrieval with edit/erase controls. Store provenance for each learned fact and decision; no unbounded chat transcript as the only memory.
- Training: (a) retrieval preferences/project history, (b) validated reusable skills, (c) curated Asterion failures/fixes and public code benchmarks, (d) optional LoRA/PEFT on capable existing hardware, (e) regression eval and rollback. Never train on secret tokens or copy privately licensed content without permissions. Deploy changed weights only after benchmark improvement.

### C1. Galaxy AICore
- Blank AICore Android app page is **not** proof of absence or unusability; it's a system-serving component rather than a regular conversation UI.
- Evaluate published ML Kit GenAI / Prompt API availability, feature \`checkFeatureStatus()\`, model download/initialization states, actual supported Samsung firmware/device and inference, structured output/streaming/tool metadata if exposed.
- Document supported OS/build/API/model limits and foreground execution requirement/quotas. System policy restrictions mean AICore cannot be the restrictionless default and should not run the core overnight cycle.
- No assumption that device's NPU is accessible to arbitrary third-party open-weight models via AICore. Keep independent local inference working even if the probe fails or SDK unavailable.

## D. Voice: "Asterion" assistant + Asterion Sound voice packages

- Wake phrase "Asterion", optional locally trained wake variants, owner-controlled always-listening service respecting Android foreground/background microphone/privacy limitations.
- Offline STT and natural TTS with streaming/partial recognition, VAD, minimal wake latency, English/French multilingual responses, speech interruption, continuation context and music-safe focus.
- Owner-initiated voice request goes straight to the normal Control task/AI router, **not obligatorily via ChatGPT UI**.
- Assistant may proactively request approval/question during a real task/overnight cycle. Its voice prompt must identify the exact pending \`task_id/question_id\`, persist for later if unavailable, avoid repeated prompts, wait for reply, then continue only the originating operation. Native voice must work without Sound.
- Asterion Sound optional Voice Package v1: \`voice_id\`, \`version\`, \`language\`, \`backend\`, \`model_assets\`, \`checksum\`, \`phoneme_dictionary\`, \`synthesis_params\`, \`sample_rate\`, \`license\`, validation benchmark, fallback; package install/update/revert.
- Voice benchmark: wake recall and false positive, offline ASR accuracy, time to first spoken response, barge-in, background/locked-device behavior, CPU/battery, French+English, naturalness, media coexistence. Never claim Bixby quality until comparative real-device test.

## E. Security & Privacy — scan incoming files AND preserve remote-device protections

### File scanner
- Automatic STANDARD scan of files Control can access or partner apps explicitly share. Escalate to DEEP scan for executable/APK/DLL/scripts/archives/PDF/EPUB/model archives, abnormal types, suspicious signature/manifest and unexpected install packages.
- Free components: ClamAV (prefer PC for expensive scans), YARA-X/rules, known-bad checksums, true MIME/magic identification, bounded safe archive recursive extraction (bomb protection), static executable/manifest checks, optional isolated PC sandbox behavior analysis.
- Signature/rule feeds must be authenticated and versioned; no upload of private files to third-party reputation services by default. Hash cache key includes SHA-256 and ruleset version.
- Dispositions \`clean_at_scan_time\`, \`suspicious\`, \`malicious\`, \`unscannable\`, \`error\`, \`in_progress\`; no absolute guarantee. Quarantine/review/restore/delete only under applicable owner permissions.
- Android scoped storage cannot see every third-party application's private directories; integrate documented Storage Access Framework, MediaStore and opt-in app adapters. Surface coverage gaps.
- Keep the previous access profiles: Normal, time-limited Developer, Lockdown, Custom as *remote tool authorization* only; no content restrictions from these profiles.

### Privacy engine
- Encrypted sensitive credential/config storage, file provenance and trusted signature checks, app package/certificate and permission-change audit, controlled network access, leak testing, user-controlled retention, security incident timeline, emergency disconnect/revoke.
- No pretend global malware monitoring or unrestricted Android root capability on non-root Android.

## F. Network Route Manager — fully protected, cost-free and speed-gated

1. Owner intends FULL-PHONE VPN on by default when first configured. Android explicit OS VPN consent is mandatory; after authorization use always-on when supported and owner enabled. Preserve existing native Control paired connection, which must never rely on Tor for basic functioning.
2. Actual verified **public exit IP** rotation 30–60 minutes, preferred 45. Country selection only among real current available servers. User owns **no foreign servers**. Do not pretend free international endpoint infrastructure or guaranteed chosen country exists.
3. Existing SuperVPN \`com.jrzheng.supervpnfree\` is an owner-provided reference, not an approved safe SDK. Preserve its installed app and credentials; check official supported interfaces and actual live connection/speed before any integration. No unsupported programmatic server switching, no covert reverse-engineering for server login credentials.
4. One-active-VpnService reality: Control must either own a validated VPN backend OR respect the existing service. Cannot silently run both full-device VPNs at once. Tor mode needs isolated compatible proxy/browser policy rather than pretending two conflicting Android VPN apps work concurrently.
5. Full-route performance gate: **VPN throughput >=75% of direct comparable median baseline** on representative Wi-Fi/mobile conditions; log down/up Mbps, latency p50/p95, DNS/IPv6/WebRTC leaks, reconnect count, battery overhead and country/IP verification. Gate is a TARGET with real pass/fail per route, not an upfront guarantee.
6. No acceptable exit or path meeting speed floor => present \`no_verified_route\`, \`privacy_vs_speed_conflict\`, or \`country_unavailable\`; prefer staying protected or owner-selected existing trusted tunnel rather than silent direct leakage. Owner can explicitly override speed gate.
7. Rotate at suitable safe boundaries, but observe real active transport and established data sessions. Do not claim successful country/IP change from changing the VPN profile; validate external IP after switch.
8. Separate Tor/onion browser mode from ordinary high-throughput full-device tunnel; no unconditional Tor-all-apps that destroys bandwidth. Preserve torrent/app restrictions of actual provider if any.
9. Policy: fail closed when strict kill switch is owner enabled and route dies; do not accidentally block emergency/native owner communications without a documented recovery path.
10. Zero subscription/provider constraint: identify actual free server candidates and independent reproducible benchmarks BEFORE guaranteeing usable hourly rotation; never claim VPN provider selection can be integrated without an API.

## G. GitHub MCP, engineering & reverse engineering of things NOT owned

### GitHub
- Use official GitHub MCP server or compatible typed repository tools inside native AI, through an explicit trust/credential handling layer. This is distinct from the **retired** ChatGPT-to-Control MCP gateway; leave established \`Asterion-Control-Bridge\` as operational fallback.
- Repositories: inspect existing code/progress/spec/branch, isolated source modifications, code search, PRs, issues, workflow status, build/test evidence, model manifests, rollbacks. Verify exact commit SHA and original APK signing before deployment. No duplicate unsupported "fixed" claims.
- Code trust gates: source diff, format/compile/unit tests, integration tests, regression on the original target, artifact hash/signature, separate \`implemented/tested/packaged/installed/device-verified\`.

### Reverse engineering: SPECIFIC OWNER CORRECTION
- Focus on **software/assets/formats/dependencies the owner does not currently HAVE** or whose original source/implementation is unavailable. For missing targets, first locate actual obtainable distributions, public artifacts, compatible alternatives, docs and observed interoperability behavior. NEVER prioritize decompilation of an existing user-owned first-party source tree.
- For available external binaries/APKs and unknown formats: identify file/container fingerprints, versions, library dependencies, manifests, behavioral APIs and compatibility constraints; isolate suspicious files; use JADX/Apktool/Ghidra/authorized runtime instrumentation as appropriate.
- When source/binary unavailable: reconstruct a **compatible implementation from observed evidence**, public interfaces or documented formats. Explicitly label impossible exact reconstruction when bytes, specifications and runtime evidence are absent. No fabricated original code.
- Outputs: source-mapped findings, version comparison, reconstruction confidence, testable replacement/reader/wrapper, license/provenance and reproducible acceptance evidence. Target acquisition/inspection must be authorized and legitimate.

## H. Skill Studio and Model Laboratory

### Skill Studio — owner-approved
- Skills are versioned, editable tested workflows: declared trigger, authorized tools, dependency graph, input/output schema, pre/post conditions, error/replay policy, example fixtures, expected evidence.
- Can target normal tasks or be explicitly invoked by overnight cycle; **skill != cycle**. Capture only proven successful recipes; dry-run, replay/benchmark, enable/disable, rollback and export/import. Skills cannot modify privileges by hiding commands.

### Model Laboratory — owner-approved
- Inventory all current Asterion apps' models, versions, model SHA, quantization, license, memory/latency, training data sources (when known), benchmarks, compatibility and installed-version record. Maintain app specialist models independently (usually 1–2 per app), Control all-rounder separate.
- **Follow model releases automatically** from owner-approved official/public model feeds (e.g. Hugging Face). Ingest verified release/version notes and metadata on a configurable cadence. Not every new model is an upgrade.
- If a relevant release may improve an app, run lightweight compatibility screen and candidate task benchmarks where actually available; compare to current baseline (quality, tokens/s, RAM, thermal, offline, license, tool calling, context, app-specific tasks).
- **Request an owner-approved model change for a specific Asterion app only when beneficial and supported**. Explain exact intended swap, data/download size, mobile performance, regressions and rollback. Never silently replace app models or incur paid inference/download fees.
- Trainable generalist/specialist LoRA via curated verified task data and actual existing PC capability; evaluate trainability/cost/time realistically. Reward passing tests, not unchecked generated code.

## I. All concrete capability modules approved for future implementation

| # | Module | Exact user outcome |
|---|---|---|
| 01 | Asterion Skill Studio | Build, validate, replay and package trusted custom agent skills. |
| 02 | Model Laboratory | Inventory/benchmark/quantize/fine-tune models; proactively monitor releases and propose appropriate per-app swaps. |
| 03 | Knowledge Graph | Persist searchable relationships between apps, devices, sources, failures, projects, decisions, models and evidence. |
| 04 | Project Inspector | Show implemented, compiled, tested, packaged, installed and actually verified states separately. |
| 05 | Automated Test Architect | Generate focused regression cases from diffs and defects, then run authorized validation. |
| 06 | Source Provenance Tracker | Map APK and other artifacts to commit, branch, signature, version, tools and evidence. |
| 07 | Compatibility Laboratory | Evaluate Android APIs/ABI, runtime dependencies, model and external binary compatibility. |
| 08 | Asterion Package Manager | Verify, install with OS consent, update and roll back approved internal components. |
| 09 | Workflow Replay Engine | Reproduce bounded authorized scenarios with semantic state assertions and deduplication. |
| 10 | AI Tool Profiler | Separate model decision, queue wait, network, execution and verification latencies. |
| 11 | Crash Reconstruction | Connect logs, process exits, native failures, events, snapshots and source frames. |
| 12 | Network Route Laboratory | Benchmark direct/private-VPN/Tor throughput and leaks before route changes. |
| 13 | Secure Sandbox Manager | Isolate unknown files and destructive tests using resettable authorized environments. |
| 14 | Voice Skill Builder | Define and test custom spoken intents, aliases, slots and voice conversations. |
| 15 | Cross-App Dependency Graph | Identify when updates break downstream Asterion app dependencies. |
| 16 | Resource Governor | Enforce device thermal, RAM, CPU/GPU, battery, bandwidth and task concurrency budgets. |
| 17 | Task Evidence Vault | Save immutable hash-verified evidence from source edits, scans, builds and on-device checks. |
| 18 | Recovery Manager | Resolve stalled jobs, connection drops and unknown outcomes without blind replay. |
| 19 | Offline Research Library | Index technical documents for local, citation/provenance-backed AI retrieval. |
| 20 | Capability Registry | Discover real app/PC tools with versioned schema, authorization and availability. |
| 21 | Download/file provenance | Track file source/hash/signature and changed install permissions without editing Downloader. |
| 22 | Security & Privacy Dashboard | Present malware verdict, quarantines, VPN status, leaks and risk notices. |
| 23 | Credential & Revocation Console | Owner-controlled trust scopes, token revocation, access audit and secure reset. |
| 24 | Transfer Integrity | Checksum/resume/duplicate detection with device acknowledgment and artifact verification. |
| 25 | Explainable AI history | Display task planning, approved tools, evidence and why actions passed/failed. |
| 26 | Scheduled Project Monitoring | Run owner-approved checks or overnight cycles with durable stop/summary. |
| 27 | Model & Skill Release Gate | Monitor dependency updates, benchmark and request changes only when useful. |
| 28 | Secure Cross-Device Search | Authorized unified search with encryption and explicit content scopes. |

## J. UX requirements

- Home: real-time phone & PC state, current action, scheduled overnight cycle (separate card), voice readiness, AI provider, security posture, VPN public IP/exit country/throughput status.
- Distinct navigation: **Control**, **Development Cycles**, **Asterion Intelligence**, **Voice**, **Security & Privacy**, **Network/VPN/Tor**, **Skill Studio**, **Model Laboratory**, **GitHub & Engineering**, **Reverse Engineering**, **Projects & Apps**, **Diagnostics**, **Settings**.
- No decorative fake controls. Real states: inactive, checking, ready, degraded, permission_required, scanning, blocked, route_below_speed_floor, no_free_exit, unverified, verified.
- Default UI must be understandable. Advanced transport, Android restrictions and kernel logs belong behind expandable diagnostics. Never expose credentials or assume a stale status is live.
- Owner approvals should be contextual and scoped; natural voice ask/answer where permitted.

## K. Acceptance and evidence before any completion claim

- Native model: offline operation, coding/agent benchmark, tool correctness, latency/thermal/memory, PC switching, owner preference tuning and content configurability.
- Galaxy AICore: actual Samsung runtime capability check, real inference call, no cloud fallback claim, truthful supported/blocked status.
- Voice: reliable wake "Asterion" and proactive question/answer, French/English, music-safe, voice pack compatibility, low false wakes and measured latency.
- File security: clean/suspicious/malicious/unscannable outcomes, deep scan of risky archives and APK, corrupted archive and decompression bomb bounded.
- VPN: confirmed public exit IP, 45-minute schedule behavior, country availability, measured >=75% baseline throughput, leaks, roaming, protected Control link, another VPN already active, Tor onion access.
- GitHub/coding: isolated branch, tests, verified code outcome and rollback; model can declare uncertainty.
- Missing-target reverse engineering: verifiable newly obtained sample, original-source absence confirmation, matching observable behavior/format and reproducible compatibility test.
- Cycle: **separate** overnight >=2 substantive verified turns, correct 20-message rollover where applicable, ambiguous send never replayed, correct recovery after process restart and morning progress report.
- All progress reported separately as **specified, source-implemented, tested, built, deployed, installed, device-verified**. Never claim future planned modules were implemented merely by committing this document.

## L. Implementation precedence (ONLY WHEN OWNER AUTHORIZES BUILD)

1. Freeze/check baseline source, existing productive Windows modifications and installed Android signer. Reconcile prior unverified Control source, native health, diagnostics, security and voice without disrupting pairing.
2. Stabilize current Control core and **separately** repair overnight development-cycle workflow. Instrument cycle reply/receipt verification and correct rollover.
3. Integrate independent local AI provider, tool router, secure task execution, voice dialogues and optional AICore backend.
4. Add full Security & Privacy (file scanner, quarantine, app auditing), routing/privacy tests; provision actual free exits before promising rotating country IPs.
5. Integrate GitHub MCP, Skill Studio, Model Laboratory/release monitor and missing-target reverse engineering.
6. Implement all I modules through narrow compatible, tested increments.
7. Owner-signed release APK **only after explicit authorization**, real Android acceptance, no data loss/no signature mismatch. Preserve original app state. Keep Downloader and other app engine development out of this Control assignment.

**Contract conflicts:** This document supersedes older Control plans wherever they conflate normal actions with overnight cycles, prioritize fixing Downloader under Control work, require paid infrastructure, or portray an optional WireGuard single config as a complete rotating, privacy-safe VPN.
