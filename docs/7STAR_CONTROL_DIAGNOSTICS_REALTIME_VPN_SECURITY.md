> **LATEST V3 OWNER OVERRIDE · 2026-11-15:** [Complete Asterion Control V3 architecture / design-only hold](CONTROL_V3_COMPLETE_DESIGN_NO_CODE_20261115.md). SuperVPN is discarded; no code/build/deployment authorized yet. Existing 7★ diagnostic/connection requirements below remain as a preserved base, not an instruction to touch Downloader or treat ordinary actions as overnight cycles.

> **OWNER REVISION 2026-11-15 — CANONICAL LATEST REQUIREMENTS:** Read [Control V2 owner-approved architecture](CONTROL_V2_OWNER_APPROVED_ARCHITECTURE_20261115.md) first. V2 requires a cost-free independent native AI, ChatGPT-optional overnight development cycles (strictly distinct from normal actions), cybersecurity + privacy malware scanning, full-phone default VPN with 30–60 min IP rotation and a hard <=25% speed-loss budget, Tor access, Bixby-class voice, Asterion Sound voice packages, GitHub MCP, analysis of external closed-source/missing-source systems, Skill Studio, Model Laboratory release tracking and all concrete integration modules. **Stop all Downloader implementation work under the Control project**; it is assigned elsewhere. V2 source feature design is approved, but owner explicitly forbids a new build/install for now. The original 7-star document below remains intact for historical scope/traceability; where contradictory, latest V2 owner decisions supersede it.

# ASTERION CONTROL — 7★ Universal Diagnostics, Real-Time Execution, Secure Networking and Developer Access
Date: 2026-11-15
Status: OWNER-APPROVED REQUIREMENTS AND IMPLEMENTATION CONTRACT — specification committed; implementation and device acceptance NOT implied.
Primary repository: Azrazieliz/Asterion-Comander
Implementation baseline: work/control-0927-overnight-cycles-20261111, or a verified newer continuation.
Applies to: Asterion Control, Downloader, Core/Nexus, Art, Sound, Writer, 3D Foundry, Adaptive Study, Game/Pilot/Codex, KK, Rounder, NoWorld, all current/future Asterion applications, Android devices, and Windows development/production machines.
Preserve: 7STAR_FROZEN_MASTER.md, signed app/package identity, existing Android/Windows worker, authenticated device pairing, user data, projects, engines, approved designs, existing working features, and provenance history.

## 0. NON-NEGOTIABLE GOAL AND DEFINITION OF DONE

Control must stop being principally a remote screenshot/click tool. It must become an extremely low-latency, robust, self-hosted, event-driven phone/PC controller and multi-app diagnostic system that exposes WHAT failed, WHERE, WHY (or the missing evidence), HOW TO REPRODUCE, and whether a specific fix ACTUALLY WORKED on the target device. An observed app label, ACK or successful build is NOT proof of functional correctness.

Repeatedly rebuilding Downloader for the same HTTP 403, unsupported listener, thumbnail, queued-worker or crash failure without collecting internal evidence is explicitly unacceptable. In ordinary investigation of an instrumented app, one diagnostic scenario must give correlated engine, process, HTTP, file, UI and worker evidence; manual screenshots, hand-entered Logcat, repeated ad hoc commands, and serial per-tap model round trips must not be prerequisites.

"7★" means ALL seven outcomes are actually verified:
1. OBSERVABLE — full permitted end-to-end cross-layer traces, including failures and process-death evidence.
2. ACTIONABLE — exact component, stage, error, causal evidence, reproducible test and owning source location when known.
3. REAL-TIME — persistent, event-driven phone/PC control with measured low end-to-end latency.
4. RELIABLE — reconnect/resume safely across transport loss, process death, changes of network and app switching; no double execution.
5. SECURE — explicit consent, scoped permissions, privacy-preserving instrumentation, encrypted network, auditable access and rapid revocation.
6. UNIVERSAL — small versioned adapters serving all apps without duplicating their engines or building a different remote-control infrastructure for each.
7. PROVEN — regression and real-phone/PC acceptance with persisted receipts and no fabricated success.

## 1. EXISTING INFRASTRUCTURE TO PRESERVE / KNOWN GAPS

RETAIN:
- Paired Samsung Android agent, independent persistent Windows worker, existing authenticated native control/stream channels, native Android Accessibility + Windows UI/input, file/job/health mechanisms, existing signing identity, watchdog and current working connection paths.
- Existing cross-app v1 provider protocol (docs/CONTROL_CROSS_APP_API_V1.md): signed package identity, local owner approval, idempotent request_id, invoke/status/cancel, bounded response and known unknown-outcome handling.
- Existing saved multi-device scripts and command batching: scripts/accept_persistent_worker_pc_phone.py demonstrated six native verified PC/phone actions with worker-local medians near 140–202 ms in prior recorded tests. Do not confuse this with ChatGPT-inclusive latency.
- Current remote command relay only as an emergency/fallback transport. Do not put a repository read/write round trip in every UI action; do not make Control functionality depend on a repository or cloud service. Do not revive retired gateways, pairing systems, or deprecated services.
- Current source branch and working update/signature path; preserve user data and existing installed apps.

OPEN GAPS, NOT PROVEN COMPLETE:
- Actual real-time ChatGPT-to-device invocation route from this conversation; persistent worker-native speed does NOT eliminate model/connector latency. The only currently documented accessible ChatGPT command route here may incur substantial overhead. The first milestone is to minimize it by worker-resident bounded workflows, and separately measure any future supported direct invocation path. Never invent a callable direct connector.
- Cross-app v1 exists on Control side; live verified provider participation by each partner engine is not established.
- Continuous diagnostic event streaming, automatic crash history, accurate per-download worker tracing, cellular failover, adaptive secure transport, new VPN mode, and full overnight cycle acceptance remain unproven until tested.

OPERATING LANGUAGE/UX:
- Surface the PRIMARY current state and outcome first. Technical transport terms should appear only in an advanced diagnostic section when pertinent.
- Do not repeatedly recommend irrelevant ADB or enumerate the fallback relay as if it were the primary real-time control engine. ADB is an optional **developer-only escalation**, not an ordinary dependency or installation precondition.
- A WebSocket is an implementation detail, not evidence of a healthy control system. Treat repeated disconnects as first-class measurable defects, with reconnect, transport fallback, circuit breaking, and diagnostics. Do not claim connected because an old socket or last-known state says so.
- No reinstall, re-pair, reboot, gateway reintroduction, credential rotation, host migration or new paid service solely to implement this scope.

## 2. PRIORITY AND PHASING

P0A (STOP THE BLEEDING): correlated application-specific logs, crash/ANR/native tombstone where permitted, engine/job/queue snapshots, network/request stages, durable incident ring-buffer, current build/install fingerprint, one-command downloader investigation, self-checking native command batches, connection telemetry.
P0B (REAL-TIME CONTROL): persistent concurrent phone/PC sessions, semantic state-driven actions, event subscriptions, control command queue, safe retries, pipelining, parallel independent jobs, screen diffs, bounded artifacts, encrypted transfer, measured latency.
P0C (SECURITY AND ACCESS): developer-access capability matrix and owner permission guidance, per-app signed authorization, scope/time-bound permissions, configurable security levels, audit/redaction and revocation.
P1: richer profilers, verified secure fast private tunnel and optional VPN, transport failover, full regression replay, full build-transfer-install-test pipeline, per-app engine plugins.
P2: advanced flamegraphs, heap/thread snapshots, scene/frame profiling, distributed tracing across apps, trend/bisect automation, cross-version baselines and full UI polish.

Deliver independently useful functional milestones, with a single shared infrastructure improvement before per-app integration. Do not spend repeated releases on undocumented changes. No APK build solely to mark this specification complete.

## 3. THE UNIVERSAL DIAGNOSTIC EVENT CONTRACT

Create a tiny versioned opt-in diagnostics SDK/adapter and agent collector (Android Kotlin/Java/JNI + Windows Python/process adapters; engine-specific native adapters only where needed). Control MUST NOT copy or replace partner application engines.

Minimum event envelope:
- schema_version, event_id, session_id, trace_id, span_id, parent_span_id, operation_id/request_id, app_package, app_version/versionCode, build_sha, engine_version/model_hash, pid/tid, device_id (pseudonymous), timestamp_wall_utc, timestamp_monotonic, sequence, severity, component, stage, event_type, state, duration_ms, error_code, exception_class, stack_or_artifact_ref, sanitized_attributes, correlation links.
- Explicit stage transitions: created, waiting, queued, runnable, running, retry_wait, blocked, paused, cancel_requested, canceled, completed, failed, outcome_unknown; never represent queued as downloading or cancellation-requested as canceled.
- Use monotonic time for durations and synchronize/estimate clock offset; record dropped-event counters and offsets after reconnection. Stable operation IDs follow UI→scheduler→engine→network→disk→output across phone and PC.
- Bounded, structured, searchable logs; sampling for high-volume telemetry, severity priority, backpressure, compressed batches, deduplication, retention quotas and opt-in sensitive data controls.
- A ring buffer retained across brief disconnects and crash-safe append-only incident journals with corruption/recovery protection.
- Read/subscribe, snapshot, incident, trace, export and replay APIs. Batch metadata is small; heavy trace/log/media data must be paged/streamed via an authenticated artifact channel, not pushed into small provider response Bundles.
- All read access authenticated and authorized by app and capability; redact credentials, access tokens, cookies, personally identifying data, message bodies, user files and media content by default. Never log raw secrets or write user credentials into source control.

## 4. LIVE DEVICE, PROCESS, CRASH AND PERFORMANCE INSPECTION

For each accessible process expose:
- Package, signer fingerprint, installed version/build, foreground/background state, activity/service/lifecycle, start/stop/exit reason, PIDs, thread counts, CPU, RSS/PSS, heap/native allocations when supported, memory pressure, disk storage/free bytes, disk I/O, network traffic, battery/charging/thermal state and throttling where exposed.
- Java/Kotlin crash stack, coroutine/scheduler exception, caught/unhandled exceptions, native signal/tombstone data available to that app, ANR evidence, last process-exit reasons (e.g. ApplicationExitInfo for its own process), relevant preceding events, and exact component affected.
- Thread and coroutine names/stacks when app instrumentation/debug privileges permit; deadlock detection, blocked I/O, main-thread stalls, Binder delays, service death/respawn, watchdog loops.
- GPU/CPU/memory profiles, graphics frame times/jank, shader/asset stalls, thermal counters and Perfetto-compatible traces when available; never fabricate restricted sensor values. Deep profiler/heap/foreign-process traces only through a separately approved debug pathway where OS permits.
- A crash must produce durable last-known-state and process-death report even if the activity never returns; on next launch detect and attach previous abnormal termination. Native tombstones from system-protected paths are only available via legitimate permitted routes.

Provide filtering by app, PID, thread, operation ID, severity, interval, provider, module and error. Correlate log events, trace spans and actual UI/engine transitions. Capture accurate first-error and causal chain, not just the final exception.

## 5. LIVE NETWORK, HTTP AND DOWNLOAD ENGINE MONITORING

Instrumentation within participating apps/clients (OkHttp/HTTP libraries/WebView/download service/engine adapters) MUST expose:
- Provider/source ID, URL category and sanitized endpoint identity, resolver/parser stage, HTTP method, DNS outcome/timing, TCP/QUIC connection and TLS negotiation outcomes, status code, redirects with origin, content-type/length, retry/revalidation/cache status, response timing, bytes in/out, streaming progress, cancellation, per-connection state and exception.
- Authentication/session present/missing/expired (without values), cookie presence and scope (without values), redirect-to-login/captcha/anti-bot classification, request-header summary and server error headers after redaction; never defeat a site's legal/access controls by assuming an automatic bypass.
- Separate failure classes: provider listing failure; thumbnail visible but parser missed; gallery/listener detection; media extraction; authorization/403; redirects; network transport; worker scheduling; bandwidth/stall; disk write/permission; corrupted content; missing exported file; duplicate handling.
- Each download: job_id, source/provider, stages, enqueue time, queue position/reason, worker_id and worker-pool limit, task start/heartbeat, effective concurrency, active receiving intervals, bytes_received, bytes_written, throughput, retries/backoff, file path or opaque file reference, checksum, final size, validation and durable completion.
- Detect starvation (queued despite idle worker), deadlocks, workers lost without final receipt, duplicate jobs, fake progress, incorrect pause/resume label/state, per-provider repeated failures, malformed thumbnail aspect/cropping, aborted transfer, bad MIME/extension and incomplete files.
- True concurrent transfer measurement: per-worker overlapping start/end windows, active transfer counts and connection throughput. UI queue size alone is not evidence of parallel downloading.

FIRST CRITICAL ACCEPTANCE USE CASE — ASTERION DOWNLOADER:
1. Open one diagnostic session and capture each of the six chronically failing providers using the current actual app workflows, including cosplay/Hentaibros, redirect/error sources, Koikatsu cards, failed EPUB and crashes as applicable. Distinguish provider-specific failures; do not assert six named providers without first checking current app configuration.
2. Trace listing → discovery → extraction → authorization → response → receive → disk → validation for each test. Capture HTTP 403 and "no supported public media listener" at the stage that originates them, not from screenshots.
3. Exercise 2–6 independent jobs with assertion of real overlap; detect queued jobs with free workers and request no idle forever.
4. Verify previously downloaded Pixiv/Kuroha IDs are respected and no duplicate transfer occurs; preserve existing data and failed-job history.
5. Produce one per-provider diagnosis with exact source/module, reproduced input, correlated trace, classification CONFIRMED/SUSPECTED/UNRESOLVED, and specific repair proposal.
6. After authorized source repair, run the identical regression inputs and verify actual downloaded bytes, valid files, correct full-proportion images, content imports, no app crash, and no regression on providers that already work.
7. Never use dozens of new APK builds just to learn the same failure. Add instrumentation once; repeat instrumented runs on unchanged builds wherever possible.

## 6. EVERY-APP ENGINE ADAPTERS (WITHOUT DUPLICATING ENGINES)

Mandatory adapters, designed from shared event schema:
- Downloader: provider discovery/parsers, queues, per-worker transfer, network, file validation, duplicate database and crashes.
- Core / Nexus: model/task selection, agent/worker state, context, tool invocation, memory operations, routing, execution timing, failures, inter-agent dependencies, error propagation and artifacts.
- Art: inference/model loading, selected mode and conditioning, inference/text/image stages, pre-generation time, VRAM/RAM, GPU/NN backend, seeds/reproducibility, output files and quality/validation assertions.
- Writer: model identity/load/version, prompt dispatch, tokens/s, output persistence, pause/resume, backpressure, failed generation, continuation and exact errors.
- Sound: waveform/audio buffers, synthesis stages, model/voice identity, generation/conditioning, latency, audio glitches, encoding and export.
- 3D Foundry: reconstruction, generation, mesh/UV/material/rig/animation/export stages, topology validity, model conversion, 3D-print and NoWorld-compatible asset validation.
- Adaptive Study: chapter/course source identity, import transformation, structure mapping, PDF/content artifacts, lesson display, Essentiel/Complet/Comprendre routes, question generation and missing content checks.
- Game / Pilot + Codex: project state, planning, tool runs, source edits, build/test/deploy and resulting game output.
- NoWorld: engine and world lifecycle, asset streaming, level/scene loads, frame pacing, render/shaders, physics, collisions, AI, animation, audio, memory pressure and native crash context.
- KK: Wine bootstrap, executable/DLL/guest process lifecycle, graphics backend, renderable first-window handshake, session/process exit codes and last failed dependency.
- Rounder and future apps: implement the generic lifecycle/task/file/incident contract plus any project-specific stages.

A partner not yet instrumented must say "INTERNAL ENGINE VISIBILITY UNAVAILABLE"; UI observation alone must never be labeled engine monitoring.

## 7. FAST, STATE-DRIVEN AND RELIABLE PHONE/PC CONTROL

Design:
- Keep existing PC and phone agent connections concurrently warm with authenticated live control, separate command, telemetry, media and bulk-transfer lanes (logical multiplexing over existing channels or sidecar only if justified). Never renegotiate every tap.
- Worker-resident deterministic scenario executor: one approved command can perform many semantic actions and verify intermediate predicates, with elapsed times and bounded step count. This is the PRIMARY fix for frequent ChatGPT/model/tool round trips in the present environment.
- Semantic Android Accessibility/approved partner bridge controls; Windows UI Automation/Win32 accessibility and native process APIs. Click-by-coordinate or full image matching only as fallback. Prefer app/engine state subscriptions to screen polling.
- Condition-driven commands: launch app → await exact foreground/package/activity/ready event → act → await engine or UI assertion → capture outcome. No arbitrary fixed sleeps except strictly bounded fallback.
- Pipelining: action acknowledgements contain command ID, device result and independent outcome verification; short batches may be parallel when independent; use dependency DAGs for ordered tasks.
- Stable sequence numbers, durable request IDs, deduplicated execution, replay-safe classifications, deadline/cancel propagation, idempotent GET/snapshot. Unknown execution outcome must NOT trigger a duplicate install, send, delete or destructive step.
- Screen sharing: fresh-frame timestamps, stale-stream indicators, event/delta frames, adaptive bitrate/framerate, both full-device and cross-app capture when approved. Native semantic state preferable; no screenshot after every gesture.
- Cross-device switching: no detour to foreground Control app for each action, no flashing Windows terminals, preserve windows/clipboard/cursor/drafts, restore the SAME original ChatGPT task via Recents rather than launcher. Capture/Accessibility/OS permissions are real, may require the owner.
- Windows and Android persistent script jobs support job IDs, logs, heartbeats, stdout/stderr, bounded timeouts, cancellation, resumability, parallel batches and terminal exit codes.
- File operations: fast compressed/encrypted chunk transfer, partial resume, full SHA-256 confirmation, atomic commit, permissions and actual install/version confirmation. No accepted-transfer-is-done ambiguity.
- Native first, protocol fallback automatically on measurable failure; no reliance on a single repeatedly failing socket. Use heartbeats, session epochs, exponential retry with jitter, circuit breakers, transport race/selection based on real RTT/loss and network changes; candidate protocols can be HTTP/2 stream, QUIC, authenticated HTTPS polling when appropriate. Do not introduce unsupported transports as a magic cure.
- Capture where time is spent: model decision, command queue wait, transport, device execution, UI/engine-ready wait, postcondition verification and result return. Label each measurement correctly, including client-to-client vs worker-local only.

PERFORMANCE TARGETS (NOT CURRENT ACHIEVEMENTS):
- Simple deterministic native local action and verification approximately 1 second; every normal individual user-level action under 10 seconds end-to-end INCLUDING model decisions, subject to honest measurement and reported limits.
- One full submitted diagnostic scenario replaces dozens of repeated round trips. Measure user request → receipt with p50/p95 and each latency segment; worker-only ms is never passed off as end-to-end.
- On transient Wi-Fi/cellular handover, buffered events and ongoing safe tasks recover with sequence continuity. Never claim automatic recovery without real handover/outage testing.
- Reduce device CPU, GPU, memory, heat, radio and battery overhead; do not make continuously streaming video a prerequisite for engine diagnostics.

## 8. DEVELOPER OPTIONS, SPECIAL ACCESS AND ACTUAL ANDROID LIMITS

Owner reports Android Developer Options enabled. Inspect what privileges are presently granted and offer an explicit capability/status matrix; no repeated generic instructions.

Three access modes:
A. STANDARD NATIVE (default): current Accessibility after user permission, MediaProjection after real OS consent, foreground app/notification/file access within Android permissions, app's own diagnostics/exit history and partner explicitly authorized IPC.
B. DEVELOPER-ASSISTED (optional, user initiated): Android's supported wireless developer debugging / profiling / bug report / system tracing facilities and approved local developer tooling, when available and already authorized; cleanly expose missing prerequisite only for a concrete task that needs it. No permanent USB tether and NEVER demand ADB for ordinary tasks.
C. ADVANCED PRIVILEGED (only if actually provided by supported OS/owner configuration): eligible device-owner or enterprise APIs, privileged/system build or independently installed root manager as appropriate; never claim normal Developer Options unlock protected other-app logs, memory or arbitrary permissions. Never attempt privilege escalation, silent rooting, permission bypass, hidden surveillance or circumventing Android security dialogs.

Permission matrix must explicitly show: feature; current permission; required action; why; risk/scope; time/expiry; operational status; and whether supported on this Samsung/Android version.
Potential Android owner-initiated accesses: Accessibility service, notification listener, usage-access stats, file/document picker/SAF grant, MediaProjection, battery optimization exemption where warranted, local VPN service authorization, developer tracing. Prevent granting irrelevant permissions. Sensitive content is excluded/redacted unless narrowly authorized.
Ordinary third-party apps cannot silently collect global Logcat, other packages' private memory, protected screenshots or secure content. Instead use app-provided events and specifically approved developer traces. Do NOT misrepresent a special access toggle or developer options as root/system authority.
Use Android ApplicationExitInfo where appropriate for the app's own exit causes; real native/ANR diagnostic availability depends on OS/privacy rules.
Platform references: https://developer.android.com/reference/android/app/ApplicationExitInfo ; https://developer.android.com/studio/debug/dev-options ; https://developer.android.com/reference/android/net/VpnService .

## 9. FAST PRIVATE VPN + SECURITY LEVELS

Purpose: OPTIONAL privacy-preserving encrypted direct connectivity between trusted owner devices, including cross-network/cellular access; optional user-selected privacy VPN functionality. Do NOT replace existing working pairing or relay merely to implement a VPN. VPN is NOT automatically faster than direct networking and can introduce overhead; measure real latency and loss before selecting it.

NETWORK MODES:
0. Existing direct secure connection (default and preserved; no VPN required).
1. PRIVATE DEVICE VPN (preferred optional): low-overhead encrypted UDP tunnel between owner-controlled Android and Windows, using a mature audited implementation/protocol such as WireGuard and modern well-reviewed libraries; authenticated peer keys, least-route split tunneling only for Control/approved LAN resources; deterministic address/route handling. Self-hosted PC endpoint or owner-controlled relay where NAT/CGNAT prevents direct reachability.
2. OPTIONAL FULL-TUNNEL PRIVACY VPN: explicit user choice; private DNS, DNS/IP leak protection, endpoint selection, on/off, split/excluded apps/hosts, throughput/latency metrics and optional strict kill-switch/always-on where Android permits. Clearly explain that a self-hosted home exit is not an anonymity service and full tunneling may slow downloads.
3. VPN NOT AVAILABLE / another VPN active: preserve existing Control connection and respect the other VPN. Never silently take over Android's one-active-VPN slot.

Android VpnService requires system approval and only one active prepared VPN application at a time. Call VpnService.prepare; honor onRevoke, foreground service expectations and Android's always-on/lockdown behaviors. Never launch a fake consent screen, bypass actual approval or silently displace the user's unrelated VPN.
Do NOT log or intercept third-party encrypted content in a general VPN traffic scanner. Per-app HTTP instrumentation is the correct path for finding Downloader failures; a VPN will NOT fix a provider HTTP 403 or engine bug.

FAST NETWORK REQUIREMENTS:
- Prefer private direct route when it benchmarks best; reuse established authenticated sessions; UDP-friendly low overhead tunnel; measure RTT, jitter, packet loss, throughput, reconnect count and battery. Compare direct vs VPN on Wi-Fi and cellular.
- Graceful handovers, NAT rebinding where supported, periodic keepalive appropriately tuned, loss detection and backoff; UDP blocked → secure supported fallback without silently switching to insecure cleartext.
- Optional local-only operation without Internet; no hardcoded third-party commercial VPN, no monthly subscription, no new permanent public endpoint, no mandatory cloud.
- Encrypt sensitive local journals and exports appropriately; encrypted authenticated transport for ALL remote control modes, not only VPN mode.

SECURITY LEVELS (user-facing explicit selector; independent from diagnostic verbosity):
- NORMAL: existing encrypted paired devices; owner-approved local access; screen & command permissions individually scoped; safe non-destructive operations.
- DEVELOPER: independently enabled, time-limited advanced diagnostics/profiling and shell/build operations through existing authorized worker, highly visible session state; full audit, explicit partner approval and no unprompted elevation.
- LOCKDOWN: require strongest feasible authentication/reconfirmation for sensitive actions, trusted-peer allowlist, tight operation scopes/expiry, optional hardware-backed Android Keystore identity, encrypted storage, privacy-first logging, revocation/kill switch (for VPN only), no public listening ports, no sensitive remote commands without approval.
- CUSTOM: per-capability owner policy and timeout for remote terminal, app install, file deletion, screen capture, network capture, app debug, logs, VPN and data export. Never silently decrease security when a command fails.

ALL LEVELS: secure authenticated pairing preserved, certificate/signature verification, credential rotation only when deliberately authorized, mTLS or well-specified authenticated session keys where appropriate, replay protection/nonces, remote user/operator identity, IP/device allowlists where useful, rate limits, inactivity timeout, full audited privileged actions, emergency revoke/disconnect, versioned policy, explicit permission ownership and key storage in Android Keystore/Windows protected credential storage. No credential/debug tokens in screenshots/logs/commits.

SECURITY TESTS: wrong peer, stolen/replayed command ID, changed partner signature, expired permission, revoked VPN, network switch, disconnected/reconnected state, unapproved app, artifact leak attempt, forbidden file path, duplicate destructive request, invalid key/cert and downgrade attempts must fail closed without erasing working configuration.

## 10. CROSS-APP IPC V2 EXTENSION (KEEP V1 COMPATIBLE)

Extend docs/CONTROL_CROSS_APP_API_V1.md and version as additive opt-in capabilities. DO NOT require each app to implement raw shell, export secrets, shared UID, root, or global debugging.

Method namespaces proposed (exact versioned schema to finalize during code implementation):
- diagnostics.capabilities — actual available engine/log/network/process/trace/incident features and permissions, including unavailable reason.
- diagnostics.attach / detach — scoped session start/end with owner permission and quotas.
- diagnostics.snapshot — one time engine/app/process/queue/network/performance snapshot.
- diagnostics.subscribe / unsubscribe — correlated filtered event stream; sequence resume cursor, bounded buffer, dropped counter, backpressure.
- diagnostics.incidents / incident.get — list/query crash, ANR, HTTP, scheduler and workflow failures.
- diagnostics.capture.start / stop — time-bounded selective trace/profiler/recording.
- engine.inspect / engine.jobs / engine.trace — engine components, tasks, workers, spans and stage state.
- network.inspect / downloads.inspect — authorized app HTTP and job data (not indiscriminate network sniffing).
- scenario.run / status / cancel — deterministic approved reproduction with postcondition assertions.
- artifacts.list / fetch — streamed, authenticated, redacted evidence/trace exports with checksum.
- control.capabilities / control.health / control.performance — current real connection route, privilege status, queue/stream/session health and measured latency.

Maintain v1 signed-package and explicit partner approval rules, sender UID/certificate verification, no arbitrary Intent, bounded control payloads, request-id durability and identity checks. For sustained subscriptions use an independently secured bulk/event transport through the existing architecture; Binder/ContentProvider is control plane, not a megabyte-per-call stream.
Partner app can have zero developer rights and still expose its own internal state, errors and logs securely after owner approval.

## 11. INCIDENT SYSTEM, ROOT CAUSE AND REPRODUCTION

On monitored failure trigger a bounded rolling pre-event snapshot (default target ~5 minutes configurable by event rate/storage) and short post-event capture; keep exact event sequence and graph. Triggers:
- crash/ANR/native exit, timeouts, no new frame or app heartbeat, engine invariant broken, HTTP 403, unsupported media/listener, redirect loops, missing thumbnail/gallery extraction, stalled/queued download, dead worker, failed model load/generation, export corruption, memory/thermal limit, asset/shader error, build/install/signing mismatch and control connection churn.

Each immutable incident bundle contains:
- fingerprint (stable logical cause grouping), precise trigger, app+engine+model+commit+APK install hashes and signature, session/trace IDs, previous and subsequent state snapshots, relevant redacted network stage, process exit reason, stack if available, worker task timeline, structured logs, metrics, screenshot/short video ONLY if actually needed and consented, crash-safe journal, source-mapped frame/module, sanitized inputs, reproduction script, expected/actual assertions, artifact SHA-256, confidence rating.
- Always distinguish CONFIRMED root cause, SUSPECTED hypothesis, UNRESOLVED missing evidence. A repeated symptom does not prove the same underlying cause until traces corroborate it.
- Automatically group identical fingerprints, compare good-vs-bad traces and detect regression by version, device, network, app provider, source commit or model.
- No "fixed" from compilation success, green button, worker ACK or nonzero byte count; prove validated final output from real scenario.
- Preserve all user content, downloaded media and existing job histories; incident journals must be prunable and user-controlled.

## 12. REAL TEST EXECUTION, BUILD, INSTALL, FILES AND ARTIFACTS

Windows worker:
- Inspect authorized repositories/branches/diffs/commits, build dependencies and SDK presence, process trees/services, ports, CPU/GPU/RAM/disk, active Python/PowerShell/Gradle/build tasks, exact stdout/stderr, tests and exit codes.
- Run parallel independent checks; ordered dependency-aware build → tests → artifact signing/checksum → authenticated file transfer → Android package/install status → app launch → diagnostics attach → scenario replay → outcome validation.
- Use current signed app identity; do not overwrite data or cause package name conflicts; owner-mediated Android OS installation gates honored.
- File operations with allowlisted roots, resumable encrypted chunk transfer, checksum, atomic rename, integrity confirmation, transfer bytes and separate states accepted/running/finished/verified.
- Real installation proof from Android package manager versionCode/packageName/signing fingerprint, then real in-app functional proof. Preserve all source/previous artifacts and exact failure logs.
- Stop repeatedly building when known failure is engine/provider logic. Investigate once with deep instrumentation before another release unless a missing capability requires the one instrumentation build.
- Output test report: evidence and exact trace bundle, verified vs unverified functions, error fingerprint, reproduction command, source/commit, actual fix and rerun result, outstanding risk and follow-up.

REGRESSION:
- Parameterized scenario library per app, deterministic test inputs, before/after comparison, screenshot/video only if visual outcome is the acceptance criterion, security/permission regression, real Wi-Fi and cellular routing, real task switching and crash/restart recovery.
- Trace replay must not repeat destructive/irreversible side effects without explicit authorization; use dry-run and idempotent operation ID where supported.

## 13. UI — QUIET, CORRECT, AND INFORMATION-DENSE

User UI: two device connectivity cards; true connection route, live RTT/loss and current operation; app picker and engine availability; incidents and last verified outcome; CPU/RAM/battery/network; VPN on/off + security-level selector; permissions/access matrix; session start/stop; transfer status; no inflated claims or unnecessary terminal/log clutter.
Operator diagnostics UI: synchronized event log, crash inspector, causal timeline, app engine tree, active workers/queue, network stages, trace viewer, performance charts, per-incident grouping, reproduction runner and full evidence export.
Protect sensitive data. No decorative/inert controls; every action needs a real handler, loading/error/success states, cancellation and verified outcome. UI status must say disconnected, reconnecting, ready, degraded, stream_stale, permission_required, not_supported, running or verified as appropriate; NEVER use "connected" based on a historical receipt.
Avoid repeatedly exposing ADB/GitHub/transport vocabulary in normal interface. Reveal low-level diagnostics only on demand.

## 14. IMPLEMENTATION ROADMAP — EXACT ORDER AND FILE OWNERSHIP

MILESTONE 0 — Baseline/diagnose without disruption:
- Inventory existing runtime workers, Android app, current dev source, signing/update state, transport reconnect bugs, current installed app permissions and current cross-app provider support; gather actual evidence first.
- Benchmark 20+ semantic native phone/PC operations and 3+ end-to-end requests using timestamps across all hops; inspect failure modes and count user actions, round trips and reconnects. Persist before baseline.
- Identify existing diagnostics, transport, process and cross-app modules; reuse them; no speculative rewrites.
- Deliver architecture map and capability gap table with files/functions to modify.

MILESTONE 1 — Instrument Control and standard SDK:
- Implement structured events/ring buffer, crash/exit hooks, operation IDs, trace viewer/export, permission matrix, bounded artifact stream, worker command telemetry, connection health and incident capture.
- Add compatibility-safe cross-app diagnostics extension and a reference app adapter.
- Acceptance: controlled crash/ANR and deliberately failing HTTP request generate accessible post-restart evidence with correlated IDs; secure access checks, large artifact retrieval and no data leakage.

MILESTONE 2 — Downloader critical blocker (priority):
- Add diagnostic SDK and per-provider parser/request/worker/file tracing to the existing Downloader app, preserving existing successful modules.
- Reproduce failures in the actual app once; produce confirmed detailed diagnosis before modifying provider code; add regressions.
- Fix proven causes and verify on physical Samsung with real downloaded files and parallel transfers. Keep exact source/test/build/installed statuses separate.

MILESTONE 3 — Real-time control:
- Implement worker-resident semantic batch/scenario executor and event subscription, parallel commands, persistent phone+PC state, screen delta, reconnect/circuit breakers, resilient job journals, direct file streaming.
- Instrument decision/queue/transport/execution/verification; fix actual recurring WebSocket/session failures with logs and tests, not assumptions.
- Acceptance: multi-action cross-device procedure with state assertions; fault-inject dropped channel/network switch, prove no double action, bounded reconnection and accurate stale-state UI.

MILESTONE 4 — Developer access + security + VPN:
- Implement permission/capability discovery and per-feature consent; NO silent privilege grants.
- Add configurable Normal/Developer/Lockdown/Custom policies, local approval and full audit; optional private split-tunnel VPN using vetted libraries; measure direct and tunnel performance.
- Acceptance: wrong-device/unauthorized partner/replayed request blocked; owner can disconnect/revoke; other VPN respected; no connection loss from a disabled or unapproved VPN.

MILESTONE 5 — Universal app integration:
- Add adapters in small versioned change sets to Core/Nexus, Art, Writer, Sound, NoWorld, 3D, Adaptive Study, KK, Game, Rounder. Use existing app-owned engine APIs rather than invasive rewrites.
- For each app establish at least one real normal scenario and one deliberately failing scenario with correlation, stable incident bundle, real output verification, and performance overhead measurement.

MILESTONE 6 — Acceptance and consolidation:
- Run full benchmark, regression suite, security tests, Wi-Fi/cellular handover and recovery. Keep a tabular implemented/source-tested/built/published/installed/device-tested verdict for every capability.
- Update README/PROGRESS and relevant cross-app contract to reflect verified current behavior; remove redundant legacy references only after confirming they are not active dependencies.
- Do not claim whole 7★ completion before all seven outcomes in Section 0 are demonstrated.

## 15. PASS/FAIL TEST MATRIX

T01 Read-only diagnosis of existing installed app without changing its data — capture app/build/engine/version correctly.
T02 Controlled Java/Kotlin crash and next-launch process-exit incident recovered.
T03 Native crash and ANR captured to the maximum actually authorized fidelity; explicitly label unavailable system-protected traces.
T04 HTTP 403 categorized with full instrumented stage, redirects, session-present flags and sanitized metadata.
T05 Listener/thumbnail/media resolver discrepancy localized in source stage; visual metadata is not conflated with media URL existence.
T06 3+ simultaneous transfer workers demonstrate overlapping active receiving; idle-worker queue stall caught.
T07 Download output validated on disk by checksum/type/full media dimensions; no duplicate using existing downloaded-ID index.
T08 App crash during active download retains last state and incident; safe resume does not silently corrupt or duplicate file.
T09 Native phone/PC simultaneous control, verified semantic actions, batch dependency checks, initial/restored state and correct elapsed metrics.
T10 2 forced transport disconnections and one Wi-Fi/cellular switch do not yield silently lost receipts or duplicate side effects.
T11 Stale screen, permissions, unavailable engine adapter and disconnected app correctly displayed as such.
T12 Exact package identity, signing, versionCode and SHA verified across source/build/transfer/install/run.
T13 Large trace exported/resumed with hash and protected from unauthorized access.
T14 Standard mode cannot use developer-only features; Developer mode requires explicit local authorization and expires/revokes.
T15 Security Lockdown blocks wrong peer, wrong signature, replay, expired token, unauthorized app, path escape and unapproved action.
T16 VPN OFF preserves current connection; VPN ON requires Android system approval, measures overhead, respects competing VPN and revocation.
T17 20+ repeated native operations benchmarked at p50/p95, with end-to-end including model hop measured separately and honestly.
T18 A known Asterion Downloader bug is diagnosed and rerun without needing a new APK just to see the internal cause.
T19 Each integrated app provides one real happy-path trace, one failure trace and validated output/incident.
T20 Stop/pause kills no unrelated apps, does not erase user data, and preserves resumes and exact original ChatGPT conversation.

FOR EVERY TEST: record test ID, app/device, date, branch/commit, versions, permission/transport mode, command trace, exact result, evidence path/hash, p50/p95 where relevant and PASSED/FAILED/BLOCKED/NOT-RUN. No synthetic test or README claim substitutes for phone/Windows receipts.

## 16. HARD LIMITS AND NON-GOALS

- Control is deterministic infrastructure, NOT another on-device AI model. ChatGPT diagnoses and writes code; Control collects evidence and executes explicitly authorized workflows. No automatic bypass of platform permission/security features.
- Developer Options are not global root; app-level instrumentation is mandatory for reliable engine-level monitoring across normal Android installations.
- Third-party HTTP 403/DRM/provider blocks may be genuine server policy; diagnosis is required but an unauthorized bypass is not an acceptable "fix".
- VPN does not fix crashes, download parsing, queues, API incompatibility, or ChatGPT inference/tool latency. It can improve private connectivity/reliability in some networks; benchmark, don't assert speed.
- No requirement for perpetual ADB, permanent USB, custom ROM/root, paid VPN, public API gateway, third-party remote-desktop service, additional pairing or a replacement for currently working transport.
- Partner integration requires changes to each partner repository and an installed version of that partner. The present file authorizes the engineering scope, not any claim that other apps are already instrumented.
- Preserve history and provenance. Change only the necessary files and keep owner-approved scope frozen until a genuine conflict is documented.
- Success means observed defects are fixed and accepted, not another nominal "patch" release.

## 17. RELEVANT EXISTING CONTRACTS AND CURRENT EVIDENCE

- ./7STAR_FROZEN_MASTER.md — frozen overall user requirements; do not rewrite.
- ./docs/CONTROL_CROSS_APP_API_V1.md — existing app signed-provider permission, request ID, invoke/status/cancel. This v2 extension is additive.
- ./docs/CYCLE_EXECUTION_CONTRACT.md — complete workflow and accurate time measurements.
- ./PROGRESS.md — current historical/verified state; always distinguish source, tests, built, transferred, installed, phone-verified.
- Existing Asterion Control worker, native multi-device scripts, Android app agent, release path and current paired identity must be reused.
- Android official platform limitations: https://developer.android.com/reference/android/net/VpnService ; https://developer.android.com/reference/android/app/ApplicationExitInfo ; https://developer.android.com/studio/debug/dev-options .

FINAL DELIVERY CONTRACT: implement once, instrument first, locate the cause with live evidence, repair a proven defect, and verify that the real phone/PC output works. No more blind rebuild iterations.
