> **LATEST OWNER OVERRIDE · 2026-11-19:** [V6 product scope](CONTROL_V6_OWNER_CORRECTIONS_20261119.md) makes a genuinely full-featured everyday Asterion Browser and AI internet crawlers **P0**, not just a shared hidden automation layer. Preserve Rounder/Downloader/Codex engine ownership. Latest independent AI evaluation target is the stricter V5 review's **50k sealed holdout + 200k stress + 2k integration + 1k human adjudicated**, not the older 12k. Bridge failures/diagnostics are P−1; spoken language English only.

> **OWNER CORRECTION — FULL BROWSING SCOPE, 2026-11-15:** The usage/location assessment below must consider the owner's ACTUAL browsing/media interests, not only Asterion software. This includes anime/Japanese visual media, Pixiv/FANBOX artworks and region-specific creator restrictions, cosplay and character assets, Koikatsu/visual novel and game mod resources, manga/manhwa/web novels, adult video/media sites and other region-dependent sites, as well as technical GitHub/model research. Geographic exit capability is **WORTH RETAINING AS ON-DEMAND** because some content is objectively region-limited. The normal default is still fast secure full-phone VPN with a DIFFERENT public exit IP and >=75% direct throughput. Geographic choice is not needed for every session; use country only when site-specific evidence supports it. No promise that any IP change bypasses payment country, age-verification, login identity, session/browser fingerprints, anti-bot rules, service rights or legal obligations. All tests remain >=10,000 distinct held-out cases (12,000 recommended), not 500. DO NOT CODE YET.

# ASTERION CONTROL V5 — Usage-aware VPN, shared Browser, app-engine reuse and >=10,000 independent AI evaluations
Date: 2026-11-15
Status: DESIGN / ANALYSIS ONLY. NO CODE, MODEL TRAINING, BUILD, DEVICE TEST, INSTALLATION, VPN ACTIVATION OR RUNTIME CHANGE AUTHORIZED.
Primary source: docs/CONTROL_V4_VPN_EVIDENCE_AI_TRAINING_SYSTEMS_RESEARCH_20261115.md, with V3 complete design and older frozen contracts preserved.
User correction: investigate whether specific country selection materially benefits actual usage/preferences, use an anonymous replacement public IP for ordinary use if it does not; provide shared Asterion Browser usable by Codex; avoid duplicate functions already owned by other Asterion apps such as Rounder; require at least 10,000 tests of the native all-rounder; assistant is expected to perform later authorized model training.

## 1. Usage-first conclusion: on-demand geo, not permanent country changing

Known actual usage and project constraints:
- Device is Samsung Android phone, Control via existing Windows worker; no owner-operated foreign exit infrastructure and no paid VPN subscription.
- Asterion Game/Codex retrieves game guides, public character/mechanic pages and synchronizes source data; may encounter regional source domains.
- Research/development uses GitHub, public documentation, model releases and tooling, where stable authenticated browser and developer sessions are more valuable than random country hopping.
- **Broader content-specific use**, distinct from app projects: Pixiv and FANBOX fan artwork/creator content, Japanese anime/doujin and visual novel media, adult video and hentai sites, cosplay imagery, Koikatsu character-card/mod resources, manga/manhwa, web novels, games and site browsing. Relevant primary evidence: pixiv explicitly states that some works are restricted based on accessing geographic region, and provides separate website account location controls (https://www.pixiv.help/hc/en-us/articles/26578893289881-I-can-t-browse-certain-works-from-the-country-region-where-I-live); France's adult-site age-verification framework has led some covered sites to block French access (https://www.economie.gouv.fr/actualites/protection-des-mineurs-en-ligne-les-sites-pornographiques-doivent-de-nouveau-controler ; https://www.arcom.fr/en/press/protection-persons-under-18-online-arcom-notes-introduction-age-verification-schemes-six-new-pornographic-sites). These make on-demand geographic routing potentially high-value. But NOT every named site has a proven geography restriction; previous JAVIDEO/403/provider or thumbnail failures are not proven geo blocks without actual response evidence. No automatic bypass of legitimate age verification, payment, access or service rules.
- Tor/.onion access remains an independent requirement, not dependent on foreign VPN country.
- Existing user's 25% maximum throughput loss remains a HARD requirement.

Assessment:
1. Geographic exits are practically useful as an ON-DEMAND feature for the owner's broad real browsing, especially selected Pixiv works and some adult/media services that restrict access by location. Keep Japan and any independently verified available region as options, not assumed provider capabilities. Geo-select when a real site/game has a confirmed IP-country gate, or the user explicitly selects a region.
2. Default protect against website seeing user's ISP public IP using legitimate available trustworthy encrypted tunnel with a DIFFERENT exit public IP; closest/fastest eligible country preferred, not arbitrary exotic location. Do not claim VPN hides account country, billing region, GPS, login identity, browser fingerprint or provider knowledge.
3. Do NOT spend scarce free infrastructure budget to maintain unnecessary country selection. Reduce app UI to Default Private, On-demand Location, Tor. In Default Private, report exit IP, provider, protected traffic, and honest measured speed.
4. Retain 30–60-minute different-exit-IP rotation as an available policy, but rotation must not break critical interactive sessions, active uploads/downloads or owner developer connections. If no safe new exit is available, report ROTATION_UNAVAILABLE and protect session, not falsely claim changed IP. Owner may choose fixed stable protected route for coding/browsing workflows. Region switches require case-specific evidence, not blind retries.
5. For region-restricted page or content, including artwork and adult platforms, classify: (a) IP-geolocation block (potentially affected by VPN), (b) account/payment region (VPN alone cannot fix), (c) captcha/anti-bot/rate limit (IP change not reliable), (d) geographic licensing or service policy, (e) actual technical failure. Website access policies and applicable terms still apply.
6. Anti-bot reality: IP reputation, cookie/session and bot heuristics can still block automated browsers or VPN exits. Browser/Codex should preserve genuine source metadata, respect explicit rate limits, try documented APIs/public exports and ask rather than claim an IP change universally unlocks a site.
7. Current free provider research: Proton Free legitimate WireGuard configs promising but geographically controlled automation, hourly rotation and >=75% true phone throughput UNVERIFIED. Owner-rejected SuperVPN must never appear in candidate list. VPN Gate has admitted connection logging and is not default private routing. Cloudflare WARP is not a country-selecting VPN. Tor Browser for .onion and experimental Tor VPN remain separately considered, not asserted high speed.

Official evidence:
- Google Play country/payment requirements: https://support.google.com/googleplay/answer/7431675
- Pixiv FANBOX payment-method country: https://fanbox.pixiv.help/hc/en-us/articles/58570051595289-Where-can-I-check-the-country-information-of-my-credit-card-or-PayPal-account
- Pixiv region restrictions: https://www.pixiv.help/hc/en-us/articles/26578893289881-I-can-t-browse-certain-works-from-the-country-region-where-I-live
- French regulator age-verification status: https://www.arcom.fr/en/press/protection-persons-under-18-online-arcom-notes-introduction-age-verification-schemes-six-new-pornographic-sites
- Android full-device always-on VPN: https://developer.android.com/develop/connectivity/vpn
- Google Play country requires new country/payment method: https://support.google.com/googleplay/answer/7431675
- Proton free random country + cooldown: https://protonvpn.com/support/change-server-free-plan
- Cloudflare multiple source-IP, session and behavior rate-limit dimensions: https://developers.cloudflare.com/waf/rate-limiting-rules/best-practices/
- Tor exit nodes can be blocked and Tor circuits may trigger account locks: https://support.torproject.org/tor-browser/general/website-blocking-tor-exits/

## 2. Shared Asterion Browser engine — one implementation, multiple clients

Asterion Browser is a genuine local browser/automation and extraction engine with:
- rendering of JS-heavy pages, DOM/accessibility tree, navigation and tabs;
- source-scoped sessions, cookies and login state in isolated encrypted profiles, no cross-app unintended identity sharing;
- browser screenshot/frame capture, structured text/HTML extraction, media/document metadata and safe snapshots with hashes;
- consented click/form typing/download, semantic element addressing and verified page-state receipts;
- public URL fetch, retries/backoff, rate controls, robots.txt and terms inspection, safe canonical URL and incremental revisit;
- web provenance: source URL, publisher, capture UTC, locale when detectable, content hash, extraction method and source confidence;
- per-site adapter registration and result schemas; no app-specific model/database hidden inside Browser;
- real IP/network route status independent of internal DOM/parser state, Tor Browser routing mode distinct;
- cross-app read-only extract vs side-effecting form actions scopes, safe credentials handling, prompt-injection untrusted web content isolation.
Optional Android WebView/browser adapter and PC Playwright/Chromium when authorized. A WebView is not a Tor Browser; provide real Tor Browser launch/delegation for onion websites.

Clients:
- **Game Codex**: Browser renders/source-extracts site; Codex OWNERS source adapter, entity matching/naming, raw data, normalized mechanics, community-source opinion, analytical evaluations, local owned roster and signed offline pack. No extraction of community tiers as Codex ranking scores.
- **Asterion Pilot**: Browser retrieves public guides; Pilot owns game-specific objectives, tactics, learned trajectories and device gameplay.
- **Asterion Intelligence**: Browser gives research/tool-use and context citations; intelligence owns reasoning, planning, memory.
- **Other signed apps**: Owner-approved invocation via Control capability registry; app still owns parser/output semantics; no modification of Downloader source without its separate owner.
- **Rounder**: Browser may send owner-opened downloaded documents to Rounder; Rounder handles reader/editor rather than Control copying its entire document pipeline.

Source contract checked:
https://github.com/Azrazieliz/Game-Central-Database/blob/main/docs/PRODUCT_RULES.md
https://github.com/Azrazieliz/Game-Central-Database/blob/main/docs/ADAPTER_CONTRACT.md

Codex key requirements explicitly preserved: A raw sourced facts, B normalized mechanics, C source/community opinion, D local analysis, E local roster. Browser supplies source layer facts/captures; never decides canonical named identity or game-specific rank.

## 3. No duplicated Rounder/File Gestioner and other engines

Rounder repo inspection 2026-11-15: https://github.com/Azrazieliz/AsterionRounder
- Existing openlocaloffice-build contains UniversalReader.java (bounded PDF/EPUB/archive/document extract), ReaderLibrary.java (SAF library), RichDocxPreview.java, LegacyOfficeReader.java, BookArchive.java, 3D model viewer and NoWorld asset-bridge. The build workflow applies DOCX flow-editor, spreadsheet UI and professional PDF UI features. This is source inventory, not proof of every feature fully working on phone.
- Therefore document reading/editing, multi-format preview, library and certain file 3D preview capabilities remain ROUNDERS' OWNED ENGİNE. A proposed "Asterion Document Factory" in Control should be refactored into a capability facade that routes to Rounder (and optional purpose-built format converters only where strictly missing); do not fork Rounder.
- Codex owns game data normalization, analysis and packs; Pilot owns live gameplay agent/tactics; Art owns art-generation; 3D Foundry owns 3D modeling/export; Sound owns music/singing/voice package generation; Writer owns writing; Downloader owns third-party download implementation. Control owns routing, orchestration, external browser, native AI, permissions, evidence, tasks/cycles, shared security/privacy.
- Shared code reuse must preserve each app's signing/data/project conventions; never silently merge engines or install duplicate generative model weights.
- Before any new system is approved, perform "OWNERSHIP/OVERLAP AUDIT": existing app/repo/module, actual current capability/status, missing shared API, proposed owner, data flows, versions, scoped compatibility and true benefit. A subsystem merely providing a dashboard over existing logic is not a new engine.

## 4. Native all-rounder evaluation MUST use >=10,000 INDEPENDENT held-out tests

Owner explicitly rejected 500 examples as inadequate; baseline shall be >=10,000 unique, independently judged cases. Recommended V1 serious benchmark: **12,000 sealed held-out cases** (realistically expensive, but no artificial low cap) distributed:

| Domain | Unique held-out cases |
|---|---:|
| General reasoning, factuality, bilingual comprehension | 2,000 |
| Coding, debugging, project edits and verified tests | 2,500 |
| Typed tool calls, GitHub MCP, permission & receipt correctness | 1,500 |
| Browser navigation, web retrieval, sourcing and contradictory pages | 1,200 |
| Android and Windows device operations with verified postconditions | 800 |
| Asterion cross-app capability routing, source ownership and integration | 800 |
| Document work, Python, spreadsheets, SQL and structured data | 800 |
| Voice dialogue, wake-intent, interruption, spoken questions (FR/EN) | 700 |
| Security, privacy, credential handling, network policy and file threat cases | 700 |
| Overnight cycle continuity, background failures, duplicate prevention | 1,000 |
| **TOTAL UNIQUE HELD-OUT CASES** | **12,000** |

- No simple prompt paraphrases counted as 12k different real skills: stratify by task type, difficulty, format, source/version, environment and expected failure modes.
- Cases have stable IDs, input fixtures, hidden acceptance criteria, bounded time budget, exact expected schema/postconditions, verifiable external receipt hashes, model/version/seed and pass/fail. Some areas need human graders or statistically checked judges, but objective tests preferred.
- NEVER train on the 12k final test set or leak expected answers through retrieval. Use a SEPARATE training dataset (large curated tool/coding/general examples), SEPARATE iterative validation data and the SEALED 12k final test set. Data splits must prevent near-duplicates, shared repository leaks and answer contamination.
- Include varied CONTENT COVERAGE (ordinary, niche Japanese-language, manga/visual novel media, mature lawful media, creator artwork, developer tools and technical research) in browser/research/tool-use tests, while measuring whether model output and tool access handle lawful content-flexibility appropriately. Test account-region mismatch/denied access, service response classification and inability to solve non-IP restrictions. Do not label a 403 a geo block absent proof.
- Real system-run tests validate code, browser DOM state, app outcomes and source integrity; the AI simply saying "done" NEVER counts.
- Reliability demands scenario difficulty, negative/unauthorized/unavailable-tool tests, case-independent scoring, false-success metric, effect of model code patch/adapter/quantization, no paid endpoint or invented capacities.
- Repeat runs at multiple seeds/versions to measure stability are EXTRA executions and do NOT inflate the number of unique cases; likewise fuzzing stress suites/long-duration real-world tests are additional evidence.
- Phone performance profile and benchmark covers sustained tok/s, TTFT, memory high-water, 5–30min thermal/battery, on-device resource contention against active VPN and wake voice. All-rounder tool coverage cannot be certified by a text-only benchmark.
- Define separate gate for external Internet/service availability: if required free endpoint unavailable, mark test blocked and report coverage, not silently treat as successful or easy failure. Do not claim "trustworthy" merely because 12k tests run: score by domain and risk, failure severity and practical owner acceptance.
- Proposed promotion standard: 12k/12k cases EXECUTED or each unavailable case documented, no critical unauthorized side effects or credential leaks, explicit per-domain quality targets established from baseline, real device tasks completed and verified. Any serious unverified automated write invalidates trust even if aggregate accuracy is high.
- Model Laboratory and training engineer responsibilities: actual curation, licensing review, dataset provenance, inference runtime code changes, PEFT/LoRA fine-tune when owner hardware suffices, release-variant comparison, holdout testing, risk audit, A/B trial and rollback. These ARE FUTURE WORK, not completed training, datasets or actual scores.
- 12k cases are for candidate MODEL + TOOL SYSTEM evaluation, not solely a bare text model; maintain separate pure-model and end-to-end scores.

## 5. Native assistant training and implementation ownership

- The assistant/tool operator is responsible for designing and implementing local training/evaluation once owner explicitly authorizes coding. User is not expected to personally prepare 12k scenarios, install tooling or do the benchmarks manually.
- Training should first choose a suitable phone-native licensed base candidate and optional PC counterpart based on measured hardware, task suite and CPU/GPU availability, not marketing leaderboards.
- Improve general reasoning and tool competence before specialized Asterion training. Use real errors only as independently checked examples, not automatically label any AI output as correct.
- Modify the open-source model inference runtime (tokenizer adapters, sampler, quantization, batching, KV, Android runtime, tool grammar and token streaming) where evaluation proves useful; LoRA adapter and weight merges only when licensing/architecture permit. Transformer surgery does not automatically improve quality.
- No GPU rental, paid AI provider or subscription. Real source/model downloads, training and evaluation may require substantial local hardware time, storage and energy; estimate these after resource inventory, not fictitious "instant" completion.
- Existing specialist Asterion app 1–2 models per app direction remains; Control is the general coordinator, not a universal creativity generator.
- Current OWNER HOLD: no code/model training, test suite implementation, builds, app merges or phone/VPN tests until explicitly authorized.

## 6. Revised design priorities and acceptance

A. Low-latency private replacement public IP, nearby fastest trustworthy free exits, <=25% throughput loss; do not insist on country control or needless churn without demonstrated benefit.
B. On-demand source-country support only for established IP-geolocation restrictions; no false expectation that VPN changes account/payment/GPS geography.
C. Shared Asterion Browser is a real system serving Codex/Pilot/native AI; dedup per-app browsing and parsing responsibilities.
D. Rounder owns existing file/document formats and viewer/editing; only build missing integrations or converters once an overlap audit proves absence.
E. Native general AI must pass >=10,000 unique sealed tests; recommended 12,000 across 10 domains, plus repeated/stress/device sessions; meaningful gate before trusting autonomous overnight source edits.
F. Preserve separate overnight development cycle with substantial work turns and ChatGPT-only rollover, independent normal action and bounded task engines.
G. No coding/building yet; GitHub docs only under the prior user instruction to keep design decisions on repo.
