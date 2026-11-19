# ASTERION CONTROL V6 — Owner corrections, supersession ledger and acceptance contract
Date: 2026-11-19
Status: OWNER-APPROVED PRODUCT REQUIREMENTS / DOCUMENTATION RECONCILIATION. **No claim of working implementation, packaging, service reload or on-device acceptance.**
Canonical repository: Azrazieliz/Asterion-Comander
Active implementation branch: work/control-0927-overnight-cycles-20261111

This file faithfully incorporates the owner's 2026-11-19 direct edits to the interactive specification. It is the **latest owner decision** for conflicting provisions. All non-conflicting requirements in V3, V4, V5, 7STAR diagnostics, CYCLE_EXECUTION_CONTRACT.md and CONTROL_CROSS_APP_API_V1.md remain binding. Existing code, approved UX, Windows worker, original Android package and signer, paired phone, WSS, keys, project data, user models and working specialist apps must be preserved. Old documents remain history; do not edit their old dates or imply their original no-code hold is currently operative after subsequent owner implementation authorization. Documentary approval is not runtime completion.

## 1. Binding owner priority matrix

| Level | Scope | Owner correction |
|---|---|---|
| **P−1, emergency blocking** | Incidents, diagnostics, self-healing, phone/Windows bridge availability | Recurring breakdowns prevent using Control; stabilize before representing other systems as functional. Real, live cross-app diagnosis is indispensable. |
| **P0, required** | Native assistant Asterion Cute and AI | Advanced, genuinely useful reasoning; unrestricted, highly tailorable content behavior; widest **actually executable** capabilities compatible with maximal measured device optimization. |
| **P0, required** | Full Asterion Browser + integrated crawlers | A genuine everyday browser comparable in capability class to Aloha, with broad web handling, capture/download/digitization/archiving and AI research crawlers; not merely a WebView wrapper or static HTML fetcher. |
| **P0, required** | Cellular, native WSS, PC/phone control | WSS is the **primary command and streaming transport** for native app AI as well as remote Control. Reliable cellular, seamless Wi-Fi↔cellular switch, fast commands; GitHub queue fallback, not one queue round trip per tap. |
| **P0, required** | VPN/IP/Tor | Self-contained in Control and fully set up by the implementation workflow as far as actually possible; do not ask owner to download, copy, configure peer files or manually implement providers. |
| **P0, required** | Action/Task/Automation | All earlier distinct execution, concurrency, receipts and recovery rules remain intact. |
| **P0, required** | Continuous development cycles | Preserve genuinely autonomous, repeated substantive turns and durable state; never equate a normal action with a development cycle. |
| **P0, required** | Interactive cross-app ecosystem | Core and Downloader have bridge implementations reported by owner as practically nonfunctional; upgrade real capability contracts, logs, inspections, dispatch and outputs. Include 3D Foundry and every current/future Asterion app. |
| **P0, required** | Security & Privacy | Earlier Standard/Deep scanning, reversible quarantine, confidentiality, permission scope, privacy, VPN routes and no false safety claims remain. |
| **P0, required** | Model Lab/training | Maximize measured reasoning, tool proficiency, app-tailored capabilities and device-specific optimization; no purely cosmetic "model installed" gate. |
| **P0, required** | Software/research/RE | Inspect software/data and observed behavior **outside GitHub**; support independent, rights-respecting functional recreation/compatibility of unavailable implementations rather than exact copied proprietary expression. |
| **P0, required** | Premium UI everywhere | Consistent premium design **through every page/dialog, secondary feature and Advanced screen**, no placeholders, disconnected themes, coding-matrix/raw-command first-party UI or dead controls. |
| **P1, required** | Voice, wake word, Asterion Sound | **English only** for speech recognition, spoken assistant conversations, voice UX and voice tests. Owner reports voice currently entirely nonfunctional; genuine repair/acceptance is required. |

Priority P−1 supersedes all prior P0 ordering. P0 entries are all mandatory and critical, but **not necessarily all simultaneously implementable**; prioritize dependency-blocking reliability so later tests can run. A task may implement P1 voice earlier when this unblocks another capability, but cannot silently drop English-only voice.

## 2. P−1 control resilience and universal diagnosis — release-blocking

Owner reported multiple repairs and repeat failures over successive days. A temporary "connected" badge, one successful GitHub command, or an accepted job is **not a repair**.

**Resilience kernel and measurable evidence:**
1. Preserve original worker, watchdog, restart contract, Android agent lifecycle, WSS relay and pairing. Audit and fix watchdog restart failure, relay session staleness, Windows process ownership, local service import errors, storage exhaustion, Unicode input, reconnect loops and missed job dispatch. Do not replace infrastructure just because it is broken.
2. Use a simple persistent event-driven, **authenticated phone-outbound WSS** channel as the normal command path. Keep heartbeats, monotonic receipt IDs, delivery acknowledgment, execution acknowledgment, verified target-state receipt, cancellation, deadlines, idempotency and no blind replay. On-phone native AI uses the same typed, scoped action protocol, not another slower middleware stack.
3. Distinguish **ChatGPT external bridge transport** from **Windows↔Android WSS**: current ChatGPT connector may still require GitHub for entry, but worker-resident task execution must avoid GitHub per gesture. Do not invent a direct ChatGPT socket integration unsupported by available tools.
4. Record recent latency p50/p95 and availability, disconnect reason, last connected vs last responsive, actual network (Wi-Fi/cellular), 503 cause, missed heartbeat, startup issues, dependency health, disk/RAM and queue age. Act on stale sessions, avoid false online status.
5. Where native Android and Windows OS actually permit, collect app own-process logcat, Android ApplicationExitInfo/ANR records, native crash traces, exception journals, worker process stderr, HTTP/queue/download events, source/build fingerprints and app-specific engine events. Android's sandbox does **not** allow silently reading every other app's private logcat: partner-owned signed diagnostic exporters and opt-in instrumentation are required, or owner-approved PC/ADB developer escalation where valid. "Can't read partner logcat" must be shown as an explicit permission or adapter gap, not hidden as success.
6. One owner-facing "Diagnose" must inspect current device + selected app, show **what failed, where, when, severity, impact, evidence, probable vs confirmed cause, reproduction, safe repair path, executed actions and verified outcome**, and intelligently collect a bounded evidence bundle. Include force-stop/crash recovery, direct event subscriptions and incident correlation, not only old snapshots or logs.
7. Implement cross-network true cellular acceptance: Wi-Fi off, mobile data on, fresh direct command and real postcondition; Android screen lock, idle/reboot where supported, network handover, phone-to-Windows WSS reconnect, Windows watchdog/service restart, packet loss and repeated runs. Do not call the routing patch verified before this.
8. Treat stability as a **blocking promotion gate**, with reproducible extended soak/fault-injection evidence and no repeated need for the owner to repair the same service manually. Suggested additional SLOs in §9 are not themselves owner-approved numbers.

## 3. Native Asterion Cute — advanced device-specific all-rounder

1. **Asterion Cute is the upgraded Asterion assistant**, not an unrelated duplicate chatbot or cosmetic character mode. It is an advanced practical reasoning and execution operator, with chat, long-context analysis, research, comparisons, synthesis, coding, program understanding, memory, tasks, planning, diagnostics, language work and complete tool/app orchestration.
2. Highest attainable measured quality and breadth, including sustained reliability on the actual Samsung under combined workload (browser + voice + VPN + incident trace + foreground apps), not lowest RAM or fastest model at any cost. Tailoring includes owner-editable behavior profiles, task-specific system/context conditioning, tool grammar, project memory, verified skills, optional specialized adapters, runtime code optimization and suitably licensed fine-tuning. No imposed generic content-topic blocks inside locally controlled models; device operating-system permissions, credentials, legitimate rights and explicit approvals remain distinct.
3. One or two well-selected, optimized general local models for Control rather than a large uncontrolled inventory; optional PC model and optional actually free provider for heavier tasks. Model decisions must follow measured TTFT/tokens/sec, logical task success, typed tool calls, memory, peak RAM, temperature, battery and offline performance. Do not pretend an untrained 0.6B model is automatically state-of-the-art or independently capable of full ChatGPT product parity.
4. On-device native assistant calls **direct scoped Control WSS/native tools** and partner APIs. Deterministic fast routing should handle obvious intents (image generation→Art, music→Sound, 3D→Foundry, study→Study, downloads→Downloader, document→Rounder) without long serial model or GitHub round trips. More complex requests get advanced reasoning.
5. Use source-linked per-project and **per-app domain knowledge** (real commands, action schemas, model/mode requirements, project state, ownership, known failures, constraints, compatible data interchange). Wrong-provider dispatch and invented capabilities fail acceptance. Owner adjustments should be saved only when explicitly confirmed by owner, and corrections should persist.
6. Training: staged memory/skills/validated tool demonstration, true inference optimization, license-compliant LoRA/QLoRA where compute permits. Continue V5 strict evaluation proposal of **50,000 unique sealed holdout + 200,000 separate stress + 2,000 live workflows + 1,000 adjudicated**; do not claim results before execution and hardware feasibility.
7. Maintain agent source provenance, ability to inspect each real tool dispatch and model choice, and truthful "blocked" when no execution path exists. No self-reported success without verified effect.

## 4. Genuine Asterion Browser plus crawler/research layer

1. Owner requires an everyday full browser **comparable in functional scope to Aloha**; no assertion of copying Aloha's protected code, branding or private features. Modern engine, rich rendering, usable tabs/tab groups, search, URL navigation, site loading, cookies/login sessions, bookmarks/history, media playback where platform supports it, download manager, downloads list/progress, offline saving, desktop-site mode, incognito/private modes, managed storage, content extraction and appropriate privacy controls.
2. Owner's original phrase **"possibility to digital everything"** is preserved. Practical scope provisionally includes broad webpage/media/document capture, downloads, archiving, readable snapshots, extraction into structured assets, OCR/digitization where useful and offline copies **when technically and legitimately accessible**. The exact meaning of "digital" is not assumed settled; do not silently narrow it to simple HTML text extraction or promise bypass of DRM/private credentials.
3. Intelligent integrated crawlers perform intent-based web search, follow candidate sources, render JavaScript pages when necessary, index/dedupe sources, compare evidence, crawl with bounded throttling and access-policy awareness, and present actual results with URL, capture time, provenance, failure reason and optional screenshots. These are **tools available to Asterion Cute**, so a normal natural-language research request can use them directly.
4. Support login-dependent workflows through scoped secure profiles and owner-supplied credentials where necessary, semantic DOM actions, consented form/transaction submission, verified downloads, retry-safe state and stable long-running browser sessions. Avoid treating an HTTP 403 or site anti-bot challenge as verified geographic denial.
5. Browser and generic crawlers can be shared via owner-approved typed contracts with Game/Codex/Pilot, AI and other apps; **Downloader** continues provider-specific media discovery/parallel downloads and **Rounder** continues file/document reading/format handling, without duplicate engines. Optional PC Playwright handles cases Android WebView cannot support.
6. Tor/.onion requires actual Tor routing and isolation, not just a Browser tab labeled Tor. Preserve per-profile session identity and secrets across VPN IP rotations.

## 5. Cellular & WSS are the native AI's primary action tools

- Preserve existing authenticated outbound WSS; prefer it over saved Wi-Fi LAN IP when available, recover across mobile/wireless transitions, and keep local direct route as verified fallback. Only GitHub emergency bridge is long-distance fallback where no direct host action entry exists; do not force per-action GitHub round trips.
- Use actual typed native app actions (action, status, cancel, observe, evidence) with permit/deny and response verification. Trigger complex multi-step workflows worker-resident to avoid repeated model/tool/connector latency.
- Always verify **true** cellular viability with Wi-Fi disabled; a connected WSS heartbeat seen while still on Wi-Fi does not count.
- Guard old phone-bridge compatibility, original signed Android package, native capability discovery and current credentials; no gateway resurrection.

## 6. Embedded VPN with zero manual technical setup

- The owner requires the developer/app to complete provider research, legitimate free provider onboarding/integration, endpoint/config acquisition where freely supported, implementation, preflight, routing, rotation and comprehensive physical verification. The user should **not** have to build infrastructure, manually fetch/copy WireGuard profile files, edit configuration syntax or program VPN drivers.
- The app **cannot bypass Android's one-time VPN consent**, displace another app's prepared VpnService without owner action, fabricate third-party free exit infrastructure, require a subscription, promise provider registration without user consent or violate external provider authorization. Minimal mandatory Android/system consent (and provider sign-in when genuinely required) is an unavoidable explicit exception to "do it without me doing anything."
- After legally obtainable provisioning and consent, native default is full-phone privacy tunnel, real external-IP replacement, verified actual 30–60 minute rotation (45 initial) if provider permits, country-on-demand when technically available, separate Tor/.onion, and measured Wi-Fi/cellular throughput **>=75%** direct baseline. Do not interrupt long downloads invisibly or bypass protection without visible consent.
- If no suitable truly free network satisfies provider/rotation/speed constraints, show precise limitation and alternatives, rather than fake a working embedded VPN. SuperVPN remains excluded.

## 7. Cross-app ecosystem — operational rather than decorative

- Core and Downloader are **reported by owner** as already exposing bridges yet providing little useful operational value; never label bridge discovery/approval as capability acceptance. Verify actual API contract, instrumentation, engine event stream, safe crash diagnostics, operation invocation, progress, outputs, cancellation and error states.
- Expand coverage to **Asterion 3D/3D Foundry**, Art, Sound, Writer, Core/Nexus, Downloader, Adaptive Study, Game/Pilot/Codex, KK, NoWorld, Rounder, and future apps. Include installed package discovery, certificate, real API schema, per-app knowledge profile, current model/mode/resources, operation parameter UI, compatible output artifacts and history.
- Explicitly implement dispatch by **user intent**: images→Art; music/audio→Sound; 3D→3D Foundry; writing→Writer; courses→Study; game research→Codex/Pilot; tags/recognition→Core; web media acquisition→Downloader; documents→Rounder. When ambiguity exists, use minimal intelligent selection and make it adjustable. A multi-app task should route artifacts through signed approved providers, not copy app-private data.
- Content provider v1 `asterion.v1.invoke/status/cancel` and signer/owner approval stay; extend with **typed capability descriptions, per-app diagnostics/events/snapshots, operation and artifact evidence, model/mode compatibility, stream/replay and return codes**. An app without an implemented partner diagnostic API cannot magically expose its private logcat on Android.
- **Preserve other apps' source ownership and dedicated models. Do not rewrite or rebuild Downloader in Control work**; coordinate any adapter additions through the app's independent maintainer/owner. Adding 3D support is mandatory, not a novel proposal.

## 8. English-only real voice

- English-only for spoken UI, wake and conversational STT/TTS, voice skills, owner questions and acceptance. This **replaces** the older FR/EN speech mandate. Text-language support in the general assistant/research may remain multilingual; voice is English.
- Wake phrase **"Asterion"**, actual foreground and permitted background operation, owner-enable/mute, full spoken follow-up, barge-in/interrupt, natural TTS, proactive task-relevant owner question, reliable speech commands into same native execution tools, offline fallback and eventual signed Sound voice packs.
- Owner reports voice currently does not work; a UI toggle, microphone permission, or a TTS demo is not completion. Record exact failure causes and real repeated phone acceptance tests in English only. Voice is P1, with blocker work permitted earlier when necessary.

## 9. Coding, external research, functional recreation and premium presentation

- Software Studio must inspect beyond GitHub: owner-supplied APK, EXE, SO, DLL, source archives, applications, interfaces, local files, web apps, observed behavior, protocols, formats and firmware **where authorized and accessible**. Use real static/dynamic tools (JADX, Ghidra, PC sandboxes, network behavior analysis) with provenance.
- Purpose is **interoperable, independently authored functional equivalent or modified implementation** where possible, including reconstructing behavior and interfaces from lawful observations—not copying another's protected source, assets, UI expression, licenses, trademarks, trade secrets or unauthorized systems. State when exact recreation cannot be evidenced.
- Premium UI is **universal**: Home, Browse, Voice, Connections, Linked Apps, Security, permission dialogs, incidents, advanced options, recovery, diagnostics, logs, performance, error states and developer tools. Use consistent design tokens, hierarchy, real user-centered phrasing, useful graphs/status visualization, progressive disclosure, real action feedback, semantic accessibility and no fake placeholders. Advanced raw data may exist for technical inspection only, not define normal navigation.
- Continued zero mandatory cost, file/user safety, native identity, private pairing and specialist-engine delegation remain unchanged.

## 10. Immediate execution dependency order and measurable gates

**Phase A — P−1 stop repeat failures:** recover and verify persistent PC worker, phone agent, WSS session, watchdog and free storage; rebuild *existing* signed routes safely; live connected cellular command; proper crash/incident evidence from Control+Core+Downloader; fault-injection and regression baselines. Do not call the project fixed until real device and extended repeat tests pass. Updated 2026-11-18 PROGRESS records further remote-text/unicode and native inset fixes as **source-only**, not verified live; do not regress them.

**Phase B — P0 fast useful tools:** native WSS Action engine and same AI invocation path; correct owner-approved cross-app intent router, signed per-app diagnostics/capabilities, genuine app profiles, meaningful app UI; stable task scheduler and recovery.

**Phase C — P0 product breadth:** full Browser, crawlers, Model Forge and useful local AI, embedded VPN verified against free-provider constraints, Security & Privacy, Software Studio/external RE, autonomous development supervisor, skills, models and original 20 systems. Parallelize only where isolation protects P−1 stability.

**Phase D — P1 English voice and end-to-end integration:** recover real wake/conversation, voice-driven actions, Sound voice packs, premium UI on *all* screens, comprehensive signed real-device release acceptance. Premium UI itself is P0 and cannot be deferred as an afterthought.

Acceptance must distinguish: `OWNER_APPROVED_SPEC` → `IMPLEMENTED_SOURCE` → `STATIC_TESTED` → `BUILT` → `DEPLOYED` → `INSTALLED` → `DEVICE_VERIFIED`. New "fixed" claims need a fresh physical postcondition plus sufficient recurrence/soak evidence; real phone package signer unchanged.

**New metrics recommended (NOT implicitly owner-approved threshold):**
- recurring failure rate per day and unassisted recovery time;
- real P50/P95 command latency **including model/connector** and per-stage breakdown;
- distinct Wi-Fi vs cellular success rates; 24h+ idle/reconnect and repeat incident soak scenarios;
- per-signed-app bridge coverage: actionable operations, diagnostic completeness, true useful outputs;
- AI correct tool selection, reasoning task success, owner-tailoring quality, thermal and battery;
- Browser navigation/JS/login/download/crawl/citation success and session durability;
- VPN provider eligibility, zero manual configuration, verified exit IP and speed gate;
- premium-screen inventory with functional control tests and visual consistency review.

## 11. Further capability recommendations — suggestions, NOT approved features

Keep **N01–N30 in V3 as unapproved proposals**. To make this V6 correction actionable, recommend prioritizing:
- **R01 Resilience Sentinel:** independent minimal local health monitor with signed service startup/heartbeat, constrained automatic recovery, last-known-good worker version, crash loop circuit breaker and authenticated human-visible incident log; never duplicate main agent or leak credentials.
- **R02 Unified Incident Flight Recorder:** bounded cross-app trace capture with diagnostic completeness score, OS-appropriate log permissions, correlation across AI/transport/engine/UI and reproducibility receipts.
- **R03 Per-App Knowledge Packs:** versioned capability schemas, mode/model requirements, known faults, compatibility links, routing examples, benchmarks and owner-custom corrections for each specialist.
- **R04 Zero-Round-Trip Native Intent Dispatcher:** rule/grammar fast path for common user intents; complex requests move to powerful reasoning, both execute through same authenticated native WSS.
- **R05 Browser Research Workbench:** AI-visible source board, pinned tabs, public-page crawl graph, source comparison, clip-to-knowledge, session-specific private profiles and provenance.
- **R06 Provider-Free VPN Provisioning Lab:** catalog real eligible no-cost providers, onboarding automations limited to public legitimate APIs, route/IP/speed evidence and transparent failure; no phantom worldwide servers.
- **R07 Universal UI Quality Gate:** enumerate every view/modal, screenshot compare portrait/landscape, keyboard/system bars, accessibility, binding to actual handlers, reject placeholder/data-matrix regression.
- **R08 Failure Budget & Regression Lock:** automatically link repeat faults to prior bug IDs, hold promotions when known failures recur, protect current usable phone/PC baseline.
- **R09 Storage Safety Planner:** evaluate owner-approved safe cleanup for build/model space, especially low-disk worker conditions; never delete unrelated files autonomously.
- **R10 Independent Functional-Equivalence Studio:** lawful external app behavior recording, format/protocol identification and original prototype verification without copyrighted code/asset copying.

The above recommendations do not override or replace V3's original N01–N30. No approval is inferred from the owner's instruction to suggest new things.

## 12. Unresolved wording and feasibility notes (without discarding requirements)

- "**Digital everything**": preserved exactly; broad digitization and captures are the working interpretation, but a future explicit owner correction can specify whether this principally means *download everything*, *digitize physical information*, *archive all browser media*, or *all types of interactive content*. No such additional interpretation is silently approved.
- "**Unrestricted AI**": owner-controlled local content/model expression with maximum feature configurability, **not** unrestricted file permissions, unsafe credential disclosure or bypass of device/third-party systems.
- "**Without me doing anything**" for VPN: full developer completion and no manual technical configuration; Android OS consent and any legitimate provider sign-in cannot be forged.
- "**Recreate the same thing modified not to go against copyrights**": functional interoperability through independent implementation; not guaranteed exact source extraction, protected assets or an entitlement to private systems.
- **No new results** are claimed in this document: the latest available PROGRESS evidence indicates the 2026-11-18 source fixes and unresolved remote diagnostics, not a new runtime acceptance.

## 13. Canonical references

- [V3 complete broad architecture](CONTROL_V3_COMPLETE_DESIGN_NO_CODE_20261115.md)
- [V4 executable engines and AI/VPN feasibility](CONTROL_V4_VPN_EVIDENCE_AI_TRAINING_SYSTEMS_RESEARCH_20261115.md)
- [V5 Browser, Codex and Rounder delegation](CONTROL_V5_USAGE_GEO_BROWSER_REUSE_12000_EVAL_20261115.md)
- [V5 final 50k/200k evaluation and geo policy](CONTROL_V5_GEO_USAGE_ROUNDER_MODEL_TRAINING_REVIEW_20261115.md)
- [7★ real-time diagnostics](7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md)
- [signed cross-app v1 protocol](CONTROL_CROSS_APP_API_V1.md)
- [actual implementation and limitations](../PROGRESS.md)
