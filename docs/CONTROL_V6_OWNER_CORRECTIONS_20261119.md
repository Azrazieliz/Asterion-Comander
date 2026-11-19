# ASTERION CONTROL V6 — Owner corrections, supersession ledger and acceptance contract
Date: 2026-11-19
Status: OWNER-APPROVED PRODUCT REQUIREMENTS / DOCUMENTATION RECONCILIATION. **No claim of working implementation, packaging, service reload or on-device acceptance.**
Canonical repository: Azrazieliz/Asterion-Comander
Active implementation branch: work/control-0927-overnight-cycles-20261111

This file records the owner's first V6 corrections and the later explicit approval of R01–R08 plus R10. **Second correction (2026-11-19):** the app and assistant are **Asterion Control**; the unrelated name was an unwanted keyboard autocorrection. Browser request = broad **downloads**, not digitization. Extreme built-in ad/pop-up blocking, genuine first-use VPN activation and a fully functional AI (with only large-scale training allowed to continue later) are mandatory. It is the **latest owner decision** for conflicting provisions. All non-conflicting requirements in V3, V4, V5, 7STAR diagnostics, CYCLE_EXECUTION_CONTRACT.md and CONTROL_CROSS_APP_API_V1.md remain binding. Existing code, approved UX, Windows worker, original Android package and signer, paired phone, WSS, keys, project data, user models and working specialist apps must be preserved. Old documents remain history; do not edit their old dates or imply their original no-code hold is currently operative after subsequent owner implementation authorization. Documentary approval is not runtime completion.

## 1. Binding owner priority matrix

| Level | Scope | Owner correction |
|---|---|---|
| **P−1, emergency blocking** | Incidents, diagnostics, self-healing, phone/Windows bridge availability | Recurring breakdowns prevent using Control; stabilize before representing other systems as functional. Real, live cross-app diagnosis is indispensable. |
| **P0, required** | Asterion Control native AI | Advanced, genuinely useful reasoning; unrestricted/tailorable locally controlled content behavior, largest realistically executable capability set, device-specific optimization and **a working installed AI/runtime at release**, not merely AI research or future training. |
| **P0, required** | Full Browser, downloads, ad/pop-up blockers and AI crawlers | A genuine everyday Aloha-class browser with broad direct downloads, comprehensive network/cosmetic ad blocking, tracker protection, non-user-initiated pop-up and forced-redirect blocking, genuine sessions/media handling and AI crawlers. |
| **P0, required** | Cellular, native WSS, PC/phone control | WSS is the **primary command and streaming transport** for native app AI as well as remote Control. Reliable cellular, seamless Wi-Fi↔cellular switch, fast commands; GitHub queue fallback, not one queue round trip per tap. |
| **P0, required** | Working embedded VPN/IP/Tor | Fully functional VPN **from legitimate free-provider retrieval and configuration through first phone activation and verified exit IP**, without asking the owner to perform technical provider setup; respect mandatory Android consent and real provider limits. |
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

## 3. Asterion Control — advanced device-specific native AI

1. **The native AI belongs to Asterion Control.** It is not a differently branded assistant or a cosmetic chatbot. It is an advanced practical reasoning and execution operator, with chat, long-context analysis, research, comparisons, synthesis, coding, program understanding, memory, tasks, planning, diagnostics, language work and complete tool/app orchestration.
2. Highest attainable measured quality and breadth, including sustained reliability on the actual Samsung under combined workload (browser + voice + VPN + incident trace + foreground apps), not lowest RAM or fastest model at any cost. Tailoring includes owner-editable behavior profiles, task-specific system/context conditioning, tool grammar, project memory, verified skills, optional specialized adapters, runtime code optimization and suitably licensed fine-tuning. No imposed generic content-topic blocks inside locally controlled models; device operating-system permissions, credentials, legitimate rights and explicit approvals remain distinct.
3. One or two well-selected, optimized general local models for Control rather than a large uncontrolled inventory; optional PC model and optional actually free provider for heavier tasks. Model decisions must follow measured TTFT/tokens/sec, logical task success, typed tool calls, memory, peak RAM, temperature, battery and offline performance. Do not pretend an untrained 0.6B model is automatically state-of-the-art or independently capable of full ChatGPT product parity.
4. On-device native assistant calls **direct scoped Control WSS/native tools** and partner APIs. Deterministic fast routing should handle obvious intents (image generation→Art, music→Sound, 3D→Foundry, study→Study, downloads→Downloader, document→Rounder) without long serial model or GitHub round trips. More complex requests get advanced reasoning.
5. Use source-linked per-project and **per-app domain knowledge** (real commands, action schemas, model/mode requirements, project state, ownership, known failures, constraints, compatible data interchange). Wrong-provider dispatch and invented capabilities fail acceptance. Owner adjustments should be saved only when explicitly confirmed by owner, and corrections should persist.
6. Training: staged memory/skills/validated tool demonstration, true inference optimization, license-compliant LoRA/QLoRA where compute permits. Continue V5 strict evaluation proposal of **50,000 unique sealed holdout + 200,000 separate stress + 2,000 live workflows + 1,000 adjudicated**; do not claim results before execution and hardware feasibility.
7. Maintain agent source provenance, ability to inspect each real tool dispatch and model choice, and truthful "blocked" when no execution path exists. No self-reported success without verified effect.
8. **Working AI at release is mandatory.** The implementer must choose an actually capable open-weight model for the measured Samsung configuration; retrieve real licensed weights, verify hashes, build/ship the correct ARM64 runtime and tokenizer, integrate inference, streaming, memory, prompt/context and typed tool calls, and prove real useful local chat, offline inference and device/API actions on the phone. The optional Windows engine may support harder jobs but ordinary Control cannot depend on it. No stub model, absent GGUF, arbitrary weak model chosen merely for size, fake “ready” status or unsupported first-use procedure is acceptable.
9. **Only substantial continuing AI training may remain unfinished** while independent and hardware-feasible curation/fine-tuning/evaluation proceeds. Basic functionality, tailoring, model installation, native inference, optimized runtime, memory and tool usefulness must be complete and verified before claiming the app done. Preserve the separate V5 50k holdout, 200k stress, 2k device integration and 1k expert-review targets as real proposed maturity evaluation—not as fabricated test results.

## 4. Genuine Asterion Browser plus crawler/research layer

1. Owner requires an everyday full browser **comparable in functional scope to Aloha**; no assertion of copying Aloha's protected code, branding or private features. Modern engine, rich rendering, usable tabs/tab groups, search, URL navigation, site loading, cookies/login sessions, bookmarks/history, media playback where platform supports it, download manager, downloads list/progress, offline saving, desktop-site mode, incognito/private modes, managed storage, content extraction and appropriate privacy controls.
2. **Owner correction: “possibility to DOWNLOAD everything.”** Implement extremely broad practical downloading for owner-visible and legitimately available website content: links, webpage files, images/galleries, audio, videos, subtitles where provided, documents, archives, files and user-selected batches. Provide filenames, storage destination, progress, queue, cancel/resume/retry, downloadable-format detection, actual completed-file verification and owner-initiated download handoff. Not OCR/digitization; no invented ability to obtain DRM-protected, credential-inaccessible or unavailable files.
2a. **Extreme native ad and tracker blocker, mandatory.** Block ads, marketing trackers, malicious advertising domains, third-party ad requests, intrusive overlays and page cosmetic advertising through efficient network-resource filters (e.g. compatible EasyList/EasyPrivacy and reputable regional lists), cosmetic hiding where supported, safe annoyance rules, regular authenticated list updates, custom site rules, a visible blocked-request counter and one-tap per-site exceptions. Audit blocking efficiency, false positives, responsiveness and list provenance; do not claim literal 100% suppression on all site architectures.
2b. **Extreme pop-up/pop-under and forced redirect blocker, mandatory.** Deny unexpected window.open/new tabs, non-user-gesture redirects to advertisements, tab-under tricks, unsolicited external-app launches, unwanted notifications, page-specified dialog spam and abusive click overlays. Respect intentional navigation and legitimate user gestures; provide once/site allow and a concise blocked-actions record. Android WebChromeClient.onCreateWindow and WebView navigation hooks can enforce some cases; supplement with actual request and page-behavior defenses rather than a cosmetic toggle.
2c. **Privacy and security protections, mandatory.** Third-party-cookie controls, site permissions for notifications/camera/mic/location, anti-tracking rules, phishing/malware URL and download warnings, unwanted autoplay prevention, per-site settings, incognito profile separation and clearable website data. Coordinate with the *existing single Android VpnService* if offering DNS filtering beyond the browser; never compete with Control's actual VPN for the OS VPN slot.
2d. **Full premium browser downloads, mandatory.** A useful saved/downloading/queued/failed view; source URL, detected file type/size, real bytes, resume where origin supports byte ranges, atomic completion, checksum when available, duplicate-prevention, storage-integrity verification, retries only for recoverable errors, safe background behavior and predictable folder destinations. Direct Browser downloads belong to Browser; site-specific provider extraction and the dedicated bulk media pipeline remain owned by Downloader, using signed cross-app handoff rather than duplicating the engine.
3. Intelligent integrated crawlers perform intent-based web search, follow candidate sources, render JavaScript pages when necessary, index/dedupe sources, compare evidence, crawl with bounded throttling and access-policy awareness, and present actual results with URL, capture time, provenance, failure reason and optional screenshots. These are **tools available to Asterion Control AI**, so a normal natural-language research request can use them directly.
4. Support login-dependent workflows through scoped secure profiles and owner-supplied credentials where necessary, semantic DOM actions, consented form/transaction submission, verified downloads, retry-safe state and stable long-running browser sessions. Avoid treating an HTTP 403 or site anti-bot challenge as verified geographic denial.
5. Browser and generic crawlers can be shared via owner-approved typed contracts with Game/Codex/Pilot, AI and other apps; **Downloader** continues provider-specific media discovery/parallel downloads and **Rounder** continues file/document reading/format handling, without duplicate engines. Optional PC Playwright handles cases Android WebView cannot support.
6. Tor/.onion requires actual Tor routing and isolation, not just a Browser tab labeled Tor. Preserve per-profile session identity and secrets across VPN IP rotations.

## 5. Cellular & WSS are the native AI's primary action tools

- Preserve existing authenticated outbound WSS; prefer it over saved Wi-Fi LAN IP when available, recover across mobile/wireless transitions, and keep local direct route as verified fallback. Only GitHub emergency bridge is long-distance fallback where no direct host action entry exists; do not force per-action GitHub round trips.
- Use actual typed native app actions (action, status, cancel, observe, evidence) with permit/deny and response verification. Trigger complex multi-step workflows worker-resident to avoid repeated model/tool/connector latency.
- Always verify **true** cellular viability with Wi-Fi disabled; a connected WSS heartbeat seen while still on Wi-Fi does not count.
- Guard old phone-bridge compatibility, original signed Android package, native capability discovery and current credentials; no gateway resurrection.

## 6. Real embedded VPN — provider retrieval through first activation

- **The target is an actually functioning VPN, not a route-selection mockup.** The implementer must locate and vet presently eligible legitimate free VPN services, obtain permitted connection endpoints/configuration and any authorized credentials, integrate real tunnel code into the existing Control package, establish DNS/IPv4/IPv6 routes, implement secure reconnect and rotation, and complete **first activation on the actual Samsung with a verified replacement public IP and Wi-Fi/cellular performance samples**. Complete all development-controlled procurement, provider retrieval, building, configuration and app-side steps. Do not outsource provider search, profile import, installation of another VPN or scripting to the user.
- VPN service must expose real connection, disconnect, revocation, unavailable/free-exit, public IP verification, latency/speed and failure/health states. A researched provider list, an untested WireGuard profile, a link to a third-party VPN or a decorative connect button is explicitly unfinished.
- The app **cannot bypass Android's one-time VPN consent**, displace another app's prepared VpnService without owner action, fabricate third-party free exit infrastructure, require a subscription, promise provider registration without user consent or violate external provider authorization. Only mandatory Android/system VPN consent, choice if another VPN is prepared, and legitimate provider sign-in where indispensable remain unavoidable user actions; **none** of these excuses manual technical setup.
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

**Phase C — P0 product breadth:** complete Browser with actual ad/pop-up blockers, broad download workflows and AI crawlers; **packaged and working native AI** and Model Forge; **real VPN provisioned from a legitimate free provider through first activation**; Security & Privacy, Software Studio/external RE, autonomous development supervisor, skills, models and original 20 systems. Parallelize only where isolation protects P−1 stability.

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

## 11. Explicitly approved new capabilities and remaining proposals

**Approved by owner on 2026-11-19: R01–R08 and R10.** These are now mandatory Control modules, not optional ideas:

| ID | Approved capability | Acceptance intent |
|---|---|---|
| **R01** | Resilience Sentinel (P−1) | Independent existing-worker-compatible heartbeats, bounded self-heal, crash-loop guards, last-known-good rollback and real human-facing recovery evidence |
| **R02** | Unified Incident Flight Recorder (P−1) | Bounded, time-correlated Control and signed-partner logs/events, native failures, WSS/HTTP/queue traces, verified cause vs hypothesis |
| **R03** | Per-App Knowledge Packs (P0) | Actual versioned modes/models/limits/actions/bugs/data formats and owner changes for every Asterion app, not a generic list |
| **R04** | Native Intent Fast Path (P0) | Immediate deterministic dispatch for basic Art/Sound/3D/Study/etc. requests over native trusted tools and WSS, higher AI reasoning for harder tasks |
| **R05** | Browser Research Workbench (P0) | Real browser source board, crawled evidence, source comparison, pinning/capture, citations and useful AI handoff |
| **R06** | Turnkey VPN Provisioning (P0) | Legitimate free provider retrieval, real native VPN implementation, setup and first phone activation/verified IP; not just a proposal or provider list |
| **R07** | Universal UI Quality Gate (P0) | Every screen and modal premium and functional, real input and states, accessibility, system bars, portrait/landscape, visual regression gate |
| **R08** | Regression Lock (P−1 for repeat Control failures, otherwise P0) | Protect known-good functionality with automated tests and meaningful device acceptance; reject recurring severe regressions |
| **R10** | Functional-Equivalence Studio (P0) | Inspect authorized external app/binary/site behavior and create original, compatible functional implementations with real proof |

**R09 Storage Safety Planner is explicitly NOT approved.** Existing owner-data preservation and safe storage checks remain binding. Original V3 **N01–N30 remain unapproved** unless separately approved; overlap does not grant approval.

### Additional concrete proposals — *not approved yet*

These suggestions are intentionally specific features rather than vague systems. They do not dilute the already-approved adblocker, popup blocker or downloading requirements.

| ID | Proposed Browser/AI feature | Concrete benefit |
|---|---|---|
| **B01** | Video download/stream inspector | Detect available page media files and non-DRM HLS/DASH playlists; offer real quality, subtitle and audio choices where available, instead of guessing |
| **B02** | Media playback suite | Background audio when supported, picture-in-picture, playback gesture controls, speed and position memory, true player capability checks |
| **B03** | Blocking shield dashboard | Per-site ad/tracker/popup/redirect counts, failed script diagnosis, list updates and immediate exceptions |
| **B04** | Page-wide bulk download picker | Enumerate actually available owner-visible images/links/files, filter/preview them, then download or hand off provider-specific batches to Downloader |
| **B05** | Isolated site identities | Multiple browsing profiles with separate cookies, permissions and privacy-preserving private sessions |
| **B06** | Advanced resumable segmented downloads | Optional parallel HTTP range chunks, restart-safe queue, integrity hashes, duplicate prevention and per-host fairness when supported |
| **B07** | Visual element-block picker | Select and hide persistent page elements, customize supported cosmetic rules and safely override a site's filters |
| **B08** | Browser workflow recorder | Record and replay owner-authorized site actions with semantic selectors and verified task outcomes |
| **B09** | Site permissions cockpit | Review/revoke camera, mic, location, clipboard, external intents and push permissions by domain |
| **B10** | Tab memory/performance governor | Hibernate inactive tabs, restore lost sessions, budget RAM/battery, save source-linked offline pages |

## 12. Corrected wording and implementation reality

- **Name:** Asterion Control is both app and native AI. The mistaken previous assistant nickname was caused by keyboard autocorrection; it is not an approved project name.
- **Download:** the user asked to *download* broadly accessible page files and media, not digitize the world. Do not quietly substitute OCR or a text-only crawler.
- **AI deliverable:** install/compile/package/test working optimized AI on real phone and finish practical reasoning+tool functionality. Only longer-term large-scale model training may continue beyond first working release.
- **VPN deliverable:** real free-provider sourcing, real in-app tunnel, setup and first verified phone activation. Android VpnService system consent and legitimate provider authorization cannot be faked. If no lawful no-fee exit meets all hard requirements, show a real blocker rather than claiming completion.
- **Blocking limits:** WebView interception and site techniques are imperfect; 100% blocking of every built-in ad or popup is not a truthful technical promise. Use multiple practical layers, test and measure outcomes. Never evade DRM or external account rights.
- **Software recreation:** implement independently authored, legal functionally equivalent alternatives after external analysis rather than copying protected source/assets.
- **Status:** these are corrected binding requirements and the nine approved module additions, not evidence of new Android/Windows/VPN/AI installation or successful runtime tests.

## 13. Canonical references

- [V3 complete broad architecture](CONTROL_V3_COMPLETE_DESIGN_NO_CODE_20261115.md)
- [V4 executable engines and AI/VPN feasibility](CONTROL_V4_VPN_EVIDENCE_AI_TRAINING_SYSTEMS_RESEARCH_20261115.md)
- [V5 Browser, Codex and Rounder delegation](CONTROL_V5_USAGE_GEO_BROWSER_REUSE_12000_EVAL_20261115.md)
- [V5 final 50k/200k evaluation and geo policy](CONTROL_V5_GEO_USAGE_ROUNDER_MODEL_TRAINING_REVIEW_20261115.md)
- [7★ real-time diagnostics](7STAR_CONTROL_DIAGNOSTICS_REALTIME_VPN_SECURITY.md)
- [signed cross-app v1 protocol](CONTROL_CROSS_APP_API_V1.md)
- [actual implementation and limitations](../PROGRESS.md)
