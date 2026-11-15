# ASTERION CONTROL V4 — VPN Alternatives Investigation + Native General AI/Model Training + Actual Systems
Research date: 2026-11-15
Status: EVIDENCE-BACKED RESEARCH / ARCHITECTURE ONLY — OWNER FORBIDS CODING AT PRESENT. No builds, no dependency installation, no APK publication, no Windows/phone deployment, no Android VPN activation, no model downloading or new provider account creation.
Source-of-truth baseline: docs/CONTROL_V3_COMPLETE_DESIGN_NO_CODE_20261115.md and prior owner-approved V2/7-star contracts. This document adds research findings and more fully specified systems; it does not supersede the strict no-code hold.

## Owner request and constraints

- Asterion Control should eventually reproduce as many feasible capabilities of a ChatGPT-like general-purpose assistant as possible, not merely mimic its chatbot UI: reasoning, research, coding, tool calls, files, documents, data analysis, scheduling, voice, app integration, and independent development. Image/video/music/3D creation is delegated to specialist Asterion apps instead of replicated in Control.
- Evaluate training of the native general model, including the possibility of MODIFYING THE MODEL INFERENCE ENGINE CODE and compatible model weights/adapters. Do not claim exact parity with proprietary flagship reasoning models or access to their private weights/data.
- Supply actual running systems with executors, storage and verification, not vague categories of checks or cosmetic dashboards. New system ideas in this document are design proposals until approved.
- Before any source implementation, research alternative VPN providers thoroughly. Free service only; owner has no foreign servers. SuperVPN is permanently rejected. Full-phone default after first-time Android consent; 30–60 minute genuine exit-IP rotation; preferred country where supported; <=25% throughput loss relative to comparable no-VPN; Control's secure native connectivity preserved; Tor/onion remain in scope. HONEST BLOCKERS if free infrastructure unavailable.
- Normal individual actions, bounded tasks and repeated substantial overnight DEVELOPMENT CYCLES are permanently DISTINCT. Do not blur those terms.

## 1. VERIFIED VENDOR FINDINGS — 2026-11-15

### 1.1 Proton VPN Free — best first conventional privacy route to investigate

Official free VPN product: unlimited data, no arbitrary speed cap advertised, open-source/audited client, independent no-logs infrastructure audit released June 2026.
https://protonvpn.com/support/change-server-free-plan
https://protonvpn.com/support/wireguard-configurations
https://protonvpn.com/support/wireguard-manual-android
https://protonvpn.com/blog/no-logs-audit
- Free server availability: 10 countries documented (NL, JP, RO, PL, NO, CH, SG, MX, CA, US). Their Android app chooses an automatic fastest server and free server changes are RANDOM with cooldown (first 45 seconds, then 10-minute stages). Cannot guarantee specific free country through standard free app.
- CRITICAL integration discovery: Official Proton documentation explicitly permits WireGuard configuration download and third-party standard WireGuard client use; Free plan can generate configurations with only VPN Accelerator option. A native Control WireGuard backend COULD import owner-generated valid free configurations. Multiple configs can be loaded into a standard client, but exact free list of selectable servers, permitted automated switch cadence and whether multiple valid geographically distinct configs exist have NOT been independently confirmed by an authenticated free account. No claim that private Proton account config generator exposes an authorized automation API. No circumventing free-tier server/rotation restrictions, quotas or provider terms.
- One active Android VPN app: Control cannot own a native tunnel while Proton's Android app is also the prepared VPN; choose either (a) owner-imported conforming configs with Control's single VpnService if permitted, or (b) Proton's native app as sole VPN with Control passive network monitoring.
- Privacy evaluation: best evidence among sampled no-fee providers, but still a third-party provider and not proven on owner's phone. Test matched Wi-Fi/mobile speeds, DNS/IPv4/v6 leaks, public exit IP, candidate validity and reliability before adoption.
Status: SHORTLIST 1; native automated 30–60 min distinct-IP and country choice UNVERIFIED.

### 1.2 hide.me Free — viable native app, poor programmable Control integration

https://hide.me/en/help/what-is-the-difference-between-free-and-paid-account/
https://hide.me/en/knowledgebase/does-hide-me-work-with-any-wireguard-client/
https://hide.me/en/pricing
- Free unlimited traffic, one device, 7–8 location count depending on current vendor page; 7-country list in March 2026 help, 8 locations on newer pricing. Do not silently reconcile discrepant vendor pages.
- WireGuard available in provider app Free but STATIC third-party WireGuard configs reserved for Premium; same for outside-app OpenVPN credentials/configs.
- Free speeds limited relative to premium. Country selection possible in free native app, but no verified automation interface for Control.
Status: SHORTLIST as independent native app / passive monitor, NOT a presently verified native Control exit provider.

### 1.3 Windscribe Free — limited monthly traffic, configs paid

https://windscribe.com/features/use-for-free
https://windscribe.com/knowledge-base/articles/where-do-i-access-my-wireguard-configs
- 2GB/mo without verified email, 10GB/mo with verified email, ten-country free roster. Some media mention bonuses; ignore contingent bonus as guaranteed.
- External WireGuard/OpenVPN config generator requires paid account. Free native app with manual country choice not a callable Control VPN backend.
Status: conditional light-use native alternative, FAILS always-on high-volume zero-cost guarantee.

### 1.4 PrivadoVPN Free — capped, configuration generator Premium

https://support.privadovpn.com/kb/article/1130-how-to-generate-a-wireguard-or-openvpn-configuration-file-for-manual-setups/
https://support.privadovpn.com/kb/article/875-what-is-the-difference-between-the-free-and-paid-vpn-plans/
- 10GB/30-day high-speed allowance, then company documents limited ~1Mbps, one connection; server locations possible in free native client.
- Third-party WireGuard/OpenVPN config generator Premium only, no validated automatic free switch API.
Status: short-term manual country routing, not suitable as 24/7 <25% loss baseline.

### 1.5 VPN Gate — programmability yes, privacy NO

https://www.vpngate.net/en/
https://www.vpngate.net/en/about_faq.aspx
https://www.vpngate.net/en/about_abuse.aspx
- University of Tsukuba research project of voluntary internationally distributed exit relays. Public CSV and native OpenVPN/SoftEther protocols potentially permit selecting exit by country and changing IP freely. Volunteer node bandwidth/trust/uptime uncertain.
- CRITICAL first-party anti-abuse policy: centralized VPN connection records retained **THREE OR MORE MONTHS**, including client IP and destination host information; volunteer node packet-header logs at least **TWO WEEKS**.
- Therefore it FAILS Asterion Control's intended default privacy/no intrusive logging requirement. Do NOT silently substitute because it is programmable. May be described as experimental transparent NON-PRIVATE research/circumvention option only if owner explicitly approves and acknowledges logs. Do not mix untrusted volunteer exits with owner credentials, security scanning uploads or model repository work.
Status: EXCLUDE FROM DEFAULT PRIVACY PROVIDER; available technically but not trusted.

### 1.6 Cloudflare WARP — not location rotation

https://developers.cloudflare.com/warp-client/warp-modes/
- Encrypts device traffic and DNS according to mode. Officially does NOT provide anonymity or foreign-country selection.
Status: useful independent transport/privacy feature but fails geographic rotation purpose.

### 1.7 RiseupVPN — nonprofit/free, unspecified endpoints/control

https://riseup.net/en/android
https://riseup.net/en/vpn/donate
https://riseup.net/en/vpn/limitations
- Free donation-supported open-source-based Android service, no payment required to start, regular full-tunnel model, explicitly warns of possible speed drop.
- No verified external native provider API or selectable scheduled geolocation in available docs. Source/metadata and provider trust still subject to independent review.
Status: optional secure-no-fee provider review, cannot claim country/IP rotation.

### 1.8 Psiphon — censorship access, unverified Control automation

https://psiphon.ca/user-guide.html
https://www.psiphon.ca/en/faq
- Full-device tunneling available in Android and location choice among 20+ or 30+ countries depending on official page version; Android system kill-switch configuration documented.
- Free tier, speed, privacy/log retention, external Control integration, repeatable exit IP changes unverified against owner's hard 75% throughput gate.
Status: censorship/region candidate only pending privacy/terms/performance proof, not qualified for secure native embedding.

### 1.9 Amnezia Free — definitively not full-phone privacy VPN

https://amnezia.org/free
https://amnezia.org/
- Open-source client uses AmneziaWG; Free service forwards only selected socially relevant blocked sites, all other websites use REAL public IP; vendor confirms IP checker sees actual original IP. 8Mbps free speed cap and no location choice on vendor product page.
- Paid Premium and self-hosted options cannot be used as cost-free foreign infrastructure.
Status: REJECT for requested full-phone default. May inform protocol engineering only.

### 1.10 CalyxVPN — current maintenance gaps

https://calyxos.org/news/2026/05/04/calyxos-progress-update-4/
- CalyxOS report explicitly omits CalyxVPN pending rebuilding maintenance/infrastructure.
Status: NOT production candidate until maintained service demonstrably returns.

### 1.11 Generous VPN — new third-party native WireGuard config option, not yet audited

https://generousvpn.com/
- Provider advertises free plan, downloadable standard WireGuard configs, 2 devices, ad/malware-filtering DNS and fair-share speed cap; free newsletter subscription is required.
- Vendor states servers in Netherlands; no verified broad country selection, speed performance or independent privacy audit from available public evidence. Webapp client requires JavaScript.
Status: INTEGRATION CANDIDATE for valid self-imported configs; NOT qualified as full privacy or fast worldwide service.

### 1.12 VPN clients, not networks

Official WireGuard library, OpenVPN, AmneziaWG, V2Ray/Xray and Tailscale can transport traffic only if the owner has a legitimate available compatible remote exit. They do not conjure geographically distributed free servers. Tailscale Personal provides free private mesh and exit nodes where an actual trusted device exists, but owner has NO devices in other countries.
https://tailscale.com/pricing
https://github.com/2dust/v2rayNG

## 2. TOR/ONION — FIRST-PARTY TOR PROJECT SOLUTIONS

### 2.1 Tor Browser for Android (preferred onion browser)
https://download.torproject.org/tor-browser-for-android/
https://support.torproject.org/tor-browser/features/onion-services/
- First-party Tor Browser supports .onion, circuit isolation, browser privacy and fingerprint reduction. Safe use requires verified official package and avoiding identity cross-linking. The Tor Project discourages adding separate VPN to Tor without advanced configuration.
- Best initial isolated dark-web browser; do NOT write a naïve Android WebView and label it "Tor Browser".

### 2.2 Tor VPN Beta Android — important 2026 development
https://download.torproject.org/tor-vpn-for-android/
https://blog.torproject.org/tor-vpn-beta/
https://support.torproject.org/tor-vpn/features/config-apps/
- Tor VPN Beta is free/open-source, whole-device or selected-app Android VPN with per-app Tor circuits; Tor site advertises exit-country control. Sept 2026 Tor technical article explains underlying Arti+Onionmasq and bridges.
- Tor Project explicitly warns that BETA releases may leak information and should NOT be used for sensitive activities. Cannot be assumed robust or <=25% speed loss. This is a TOR routing mode, not a normal high-throughput commercial VPN.
- Under Android one-prepared-VpnService rule, Tor VPN Beta cannot simultaneously own an independent VPN interface with Control's WireGuard or Proton VPN app. Mode switching requires owner-approved configuration and honest user-facing protected/unprotected state; no silent traffic leak or unsupported dual-VPN claim.
- Potential future Control-owned Tor routing using open-source Arti/Onionmasq only after license, technical compatibility, app-isolation and privacy testing; do not claim easy integration. Standalone Tor Browser is preferable in the meantime.
https://support.torproject.org/tor-browser/general/vpn-with-tor/

### 2.3 Optional other dark networks
I2P and other anonymous overlays are distinct from Tor; if included, they need independent protocol/runtime, service discovery, threat model and user mode. They do NOT automatically open .onion websites, nor necessarily satisfy full-phone VPN performance requirement.
Status: research proposal, no implementation assumed.

## 3. HONEST DECISION ON VPN FULFILLMENT

Priority A: Proton VPN Free with legitimate owner-generated standard WireGuard configs (if/free-account permitted and multiple distinct valid exits exist) + measured phone-native VPN integration.
Priority B: Tor Browser for .onion, plus separately evaluate Tor VPN Beta for full-device/app-specific TOR mode, accepting beta risk and potential substantial slowness.
Priority C: Review remaining free provider apps or standard configs as optional fallback only when externally documented and actually meeting privacy/speed/rotation. hide.me native, Riseup native, Generous free WG are relevant but not proven integration.
Privacy FAIL: VPN Gate for default identity protection, SuperVPN (owner rejected), random volunteer "free keys", unknown proxy lists, public SOCKS endpoint pools, stealth app repacks.
Functional FAIL: Amnezia Free split-only, Cloudflare WARP for country/IP rotation, paid-only static configs on Windscribe/Privado/hide.me, foreign self-hosted machines (none owned).
NO provider currently verified to satisfy **all**: free, trustworthy no-intrusive-logging, native Asterion Control integration, automatic distinct new IP every 30–60 minutes, user-selected country and >=75% actual throughput baseline on Samsung Wi-Fi+cellular.
Status: ARCHITECTURE COMPLETE, PROVIDER REQUIREMENT EXTERNALLY UNRESOLVED. Do not code fake rotation.

## 4. VPN ACCEPTANCE PLAN BEFORE PROVIDER ADOPTION (NO TEST RUN YET)

A. Trust check: first-party policies and audits dated/current, package SHA and signing, conditions for free configurations, geo-exit pool, account restrictions, local key handling and lawful use; no captured secret keys in logs.
B. Feasibility check: obtain allowed free protocol config through user's own approved account if relevant. No scraping private API or bypassing plan restrictions.
C. Route check: Android full-device VpnService actual consent, tunnel state, public IPv4/IPv6, DNS, WebRTC where observable; phone/PC native Control WSS still authenticated and reachable.
D. Speed: comparable target server and network time on Wi-Fi and cellular, direct and tunneled samples, ideally >=3 repeated download/upload samples; report throughput ratio and RTT p50/p95. Requirement VPN >=0.75 direct; p95 RTT <=1.25 direct aspirational, not silently conflated with throughput.
E. Rotation: several real, different outbound IPs with documented 30–60min schedule, independent endpoint verification, actual country inference, no DNS leaks/Control session loss, provider terms respected.
F. Failure: reboot, Android revocation, no free exit, VPN collision, battery/thermal/network handover; show exact UNSUPPORTED/SLOW/PRIVACY_BLOCKED/NO_NEW_IP status rather than falsely claim protected or rotated.
G. Cost: no unexpected charge, paid feature or hidden infrastructure prerequisite. Untrusted servers not an acceptable performance shortcut.

## 5. ALL-ROUNDER "DO WHAT CHATGPT CAN DO" — FUNCTIONS AND REAL EXECUTORS

**Core**: a high-capability local general LLM provides language/reasoning/orchestration, but *ChatGPT product breadth* comes from distinct tools, systems, datasets and services. Matching every proprietary model/tool/service exactly is not guaranteed or technically obtainable from local model weights. Below are REAL EXECUTING SYSTEMS rather than dashboard names.

S01 ASTERION BROWSER ENGINE: native controlled Chromium/Firefox-based browser via available Android/PC browser automation (Playwright/DevTools where permitted), DOM navigation, tab/viewport, structured extraction, authentication through secure credential broker, opt-in click/form submissions and downloads, snapshots and receipts. Internet access is connection-based, not paid browser API.
S02 ASTERION RESEARCH ENGINE: official website/feed retrieval, configurable provider web search where freely available, dedupe, content extraction, primary-source attribution, date/version checking, citation-backed report, comparison, owner research library. Avoid unsupported commercial search quota assumptions.
S03 ASTERION SOFTWARE STUDIO: real Git repository workspace, code editor/diff, language servers, GitHub MCP, source writing, compilers/test runners, build and signed-artifact validator on approved Windows environment, issues/PR integration, local code sandbox and rollback. Model's claims require verified compilation and outputs.
S04 ASTERION COMPUTER OPERATIONS: Windows native files/processes/terminal/app/service/UI; Android permitted Accessibility/scoped files/APIs, screenshots/stream/gestures; independently measured action latency and permission status. Existing original worker preserved.
S05 ASTERION DATA SCIENCE ENGINE: local Python/NumPy/pandas and optional numerical/statistical libraries, structured SQL, actual plots/charts, reproducible notebooks and tabular exports; execute code safely under resource/time limits.
S06 ASTERION DOCUMENT FACTORY: real read/write/edit DOCX, PDF, spreadsheet XLSX/CSV, presentations PPTX, HTML, markdown, EPUB and text files. Layout rendering, conversion, formulas and citations; preview/acceptance. Editable artifacts, not merely generated images.
S07 ASTERION KNOWLEDGE & MEMORY SERVER: local full-text/vector search, provenance and expiration, project knowledge graph, controlled imports, durable tasks/context and correction/forget. No phantom "memory" claims.
S08 ASTERION PERSONAL AUTOMATION SERVER: natural-language recurring automation, reminders, event triggers, condition watchers, workflow scheduler, time-zone and sleep-aware durable queue; explicit start/stop, no self-start without authorization.
S09 ASTERION OVERNIGHT DEVELOPMENT SUPERVISOR: separate from S08 and normal tasks; substantial autonomous project turns with actual tests, verified replies, repositories, checkpoints, platform-specific ChatGPT rollover and native-AI context compaction.
S10 ASTERION MCP & CONNECTOR HOST: tool registry, permissioned standard MCP clients, GitHub official MCP, local filesystem services, third-party provider connectors only when allowed, optional custom Asterion integrations, typed output/trace receipts.
S11 ASTERION VOICE CONVERSATION SERVER: local wake "Asterion", offline STT, streaming TTS, multimodal question/answer, voice-triggered commands, context/consent inbox and versioned Sound voice packs.
S12 ASTERION REVERSE ENGINEERING WORKSTATION: external source-absent authorized APK/EXE/firmware/protocol/file investigation through isolated Ghidra/JADX/Apktool/Frida/tracing, evidence-backed function/format maps and compatibility shims.
S13 ASTERION SECURITY OPERATIONS CENTER: malware scan incoming accessible files, Standard/Deep, hash/signatures/YARA, quarantine, suspicious archive analysis and isolated sandbox, supply-chain checks, permissions/credentials monitoring and incident response.
S14 ASTERION NETWORK ROUTER: Android VpnService owner-consented full-phone tunneling, imported eligible free WireGuard endpoints, provider selection, verified external IP switch, throughput/privacy policy, DNS leak checks, protected Control connectivity and separate Tor mode.
S15 ASTERION APP ECOSYSTEM ORCHESTRATOR: signed cross-app capability registry and tasks for Art, 3D, Sound, Writer, Core, Adaptive Study, Game etc.; preserves specialty engines and separate developer ownership of other apps.
S16 ASTERION LOCAL MODEL FORGE: installs/evaluates licensed open-weight language models with owner consent, quantization/benchmark, LoRA/adapters, approved inference runtime/source patches, checkpoint/rollback and release watchers.
S17 ASTERION SKILL STUDIO: derive typed versioned executable skills from verified workflows, simulation, test, permission policy, safe replay, rollback and metric history.
S18 ASTERION INTERACTIVE APPLICATION BUILDER: owner-approved mobile/web/desktop UI prototypes and runnable code, components/assets from existing apps, edit source, device preview and automated accessibility checks.
S19 ASTERION DEVICE SIMULATION/TEST FARM: emulator/test fixtures, network fault injection, controlled phone UI tests, Android API compatibility, signing upgrade proofs and crash recovery scenarios, preserving real device.
S20 ASTERION DATA CONNECTORS & COMMUNICATIONS: provider-based email/calendars/notes/contacts if available and consented, draft/search/send with explicit scope and receipts; no pretend connectors without supported API.
S21 ASTERION PRIVATE WORKSPACE SEARCH: unified opt-in indexing of local/approved cloud files, repositories, conversation summaries and documentation, content permissions inherited from source.
S22 ASTERION MEDIA UNDERSTANDING ROUTER: read/analyze images, audio, video and 3D metadata through local suitable models or companion Asterion apps, while GENERATION belongs to Art/Sound/3D/etc., avoiding duplicated heavy generators.
S23 ASTERION TRANSLATION & EDUCATION ENGINE: multilingual translation, lessons, source-based explanation, adaptive quiz generation where appropriate, code interpretation, Study integration via existing partner interfaces; not an unbounded new language model.
S24 ASTERION LOCAL SERVICE HOST: permissioned APIs and controlled extensibility/plug-in workers; process isolation, update manifest, versioning and port discovery, no public unsigned open endpoints.

Owner also approved V3's prior 20 concrete modules (model release tracking, capability registry, crash reconstruction, provenance, skill studio, task evidence, etc). New S01–S24 are suggestions to implement as true engines, not title-only pages.

## 6. MODEL TRAINING / MODEL SOURCE MODIFICATION EVALUATION

Known device hardware: SM-S948B is Galaxy S26 Ultra, Snapdragon 8 Elite Gen 5 (Samsung source), possible 12GB RAM or 16GB RAM depending variant. EXACT installed memory, free RAM, available storage and thermal profile must be observed before model choice. A large LLM can coexist with phone OS, VPN, wake and scanner only within measured headroom.
https://www.samsung.com/de/support/mobile-devices/vergleich-galaxy-s26-ultra-vs-galaxy-s26plus-vs-galaxy-s26/
Existing owner model strategy: 1–2 efficient specialist models per app where helpful, and 1–2 for Control as primary reasoning; use PC optional for heavy context/training, not a requirement to use 15 separate models.
Open candidates (EVALUATION ONLY): Qwen3.5 4B/9B variants, other Apache-2.0 or equally free permissive models proven to run efficiently on Android; optional PC candidate gpt-oss-20b (license/policy must be checked). Do not hardcode a selection based on press release or leaderboard. Example:
https://huggingface.co/Qwen/Qwen3.5-4B
https://openai.com/open-models/

### Modifications possible

L0 NO-WEIGHT CHANGES: system/developer prompts, tool call schemas, context compression, sampled self-critique with deterministic verification, RAG and project knowledge; most cost-effective route to useful AI tools.
L1 APPLICATION/INFERENCE CODE PATCHES: use open-source llama.cpp/Android (or equivalent) source; owner can change decoding and sampling, batching, quantization, KV/cache policy, token streaming, ARM kernels, Android lifecycle/foreground service, context memory, fine-tuned grammar/tool schema, concurrency/battery limits; maintain tested vendor fork and compatibility.
L2 TRAINABLE ADAPTERS: LoRA/QLoRA/PEFT on appropriately licensed base weights. Train on verified general reasoning, bilingual task execution, tool calls/GitHub MCP, research citations, coding/test repair tasks, OS operation and Asterion specialist coordination. Preserve base model immutable and version adapters with hold-out evaluation. Use existing PC for training IF compute allows; no model weight training from scratch required.
L3 WEIGHT CHANGES: merge compatible LoRA, distillation from legally licensed teacher responses/data, continued pretraining with suitable documents, quantization-aware calibration, supervised fine-tuning, preference optimization (where feasible). Model cards, license, hashes, rollback, benchmarks required.
L4 ARCHITECTURE CHANGES: transformer head/layer/routing/hidden-size changes break compatibility with unmodified pretrained weights and may need expensive additional training. Directly editing a "model code file" alone does NOT magically upgrade its reasoning ability; prioritize evaluation-backed architecture optimization rather than arbitrary rewrites.
L5 FOUNDATION FROM SCRATCH: mathematically possible but financially/computationally unrealistic under owner's zero-cost and available-hardware goal; not recommended.

### Objective training gates, not self-reported success

Benchmark suite must be saved as a sealed task corpus with immutable ground-truth tests:
- 150+ general assistant questions, FR/EN, user-intent understanding, accuracy, explicit uncertainty.
- 100+ typed tool calls with valid schemas, missing permissions and no fake success.
- 100+ real coding tasks (small edits, bugfixes, test-gated multi-file changes), GitHub branch/commit identity.
- 50+ source-grounded web research tasks with fresh citations, source conflicts, correctness.
- 50+ device automation scenarios with Android/Windows target and actual postcondition checks.
- 50+ Asterion ecosystem scenarios with true provider availability, owner permission, no invented app capabilities.
- Privacy/safety/cost boundary tests to ensure content preference does NOT bypass OS permissions or result in silent paid requests/secret disclosure.
- Model performance: exact APK/model, quantization, RAM peak, tok/s, TTFT, prompt processing, battery draw/thermal, 5+ min sustained profile, crash/ANR.
- HOLDOUT test cannot be the same examples used to train. Compare control baselines vs modified runtime/LoRA; rollback regressions; never interpret a model stating "done" as proof.

Feasibility: memory-based personalization/tool design very feasible; Android open-source inference runtime patches feasible; small/medium LoRA training conditional on available PC accelerator; full foundation parity not guaranteed. Product breadth needs running S01–S24 engines regardless of model choice.
https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md
https://huggingface.co/docs/transformers/peft
https://huggingface.co/docs/peft/en/package_reference/lora
https://help.openai.com/en/articles/11870455-openai-open-weight-models-gpt-oss

## 7. END-TO-END ACCEPTANCE / HONEST STATUS CONTRACT

- Source document is research, NOT proof: no VPN tests done on Samsung, no free accounts created, no model benchmarks, no code patched, no application built.
- User's VPN constraints cannot currently be simultaneously verified from public information. PROMISING a specific exit country or <=25% slowdown is forbidden until real device tests and eligible exit infrastructure established.
- Native AI requirement is full tool-assisted product, NOT mere "train a model to answer similarly"; the S01–S24 execution systems must be truly available, producing verified outcomes.
- Tor first-party beta status must be disclosed whenever used for sensitive context, no dual Android prepared VpnService invented.
- The existing Android/Windows Asterion Control identity and infrastructure must remain unchanged.
- Normal actions != finite tasks != overnight continuous substantive development cycle.
- All source/code/build/installer and device mutations remain PAUSED pending fresh explicit owner authorization after this research.
