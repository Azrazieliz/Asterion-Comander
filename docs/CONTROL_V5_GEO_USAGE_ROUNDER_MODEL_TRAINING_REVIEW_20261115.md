# ASTERION CONTROL V5 — Usage-based VPN geography, non-duplicating integrations and rigorous local-AI training
Date: 2026-11-15
Status: RESEARCH + DESIGN ONLY / STRICT NO-CODING HOLD.
Parent: docs/CONTROL_V4_VPN_EVIDENCE_AI_TRAINING_SYSTEMS_RESEARCH_20261115.md, docs/CONTROL_V3_COMPLETE_DESIGN_NO_CODE_20261115.md; historical contracts retained.
Owner correction: "investigate whether specific location access would be profitable to me relatively to my usage/preferences. If it's not, just something that modified and hide my IP so as not to have location restricted access. Include the scope of content I browse/meddle in, not just asterion apps. ... Asterion browser could be useful but some things overlap ... Rounder ... 500 tests is underwhelming. ... You're the one to train it anyway."
Do not code, test phone, build, install, change any existing Control/Downloader/Rounder sources, create provider accounts, download models or activate a VPN.

## 1. USER ACTIVITY PROFILES — ACTUAL PRIOR WORKFLOWS, NOT PERSONAL ASSUMPTIONS

Known project/browsing categories explicitly discussed with owner:
A. Japanese and international artwork/artists/Pixiv, anime/manga/novels, age-restricted illustrations as part of content browsing/acquisition.
B. Videos and adult-oriented media sources, including general videos and galleries, cosplay, comics, novels and archives; different sites may implement geographic access restrictions, age checks or provider anti-automation protections.
C. Koikatsu characters/cards, mods, games and game asset resources; Japanese and international source ecosystems.
D. Large independent parallel file downloads, 3D assets, EPUB, ZIP/archives, thumbnails, site extraction and file integrity/dedup.
E. Research, development, open-source repositories/GitHub, local AI models/model hubs, Asterion applications and tools.

Do NOT infer user's age, identity, actual sexual behavior, paid content subscriptions, exact real-time browsing history, account settings or purchased media from these project categories. Site-specific network status must be independently checked before labeling a URL geo-blocked.

## 2. GEOLOCATION UTILITY — DECISION BY TASK AND EVIDENCE

Default recommendation: SPECIFIC COUNTRY SELECTION IS AN OPTIONAL ADVANCED ABILITY, NOT ESSENTIAL FOR THE OWNER'S EVERYDAY BROWSING. More valuable baseline: encrypted full-device traffic, reputable free no-logs provider, verified external IP replacement/rotation, real geographic access where supported, <=25% throughput loss, preservation of long downloads and sessions, Tor/.onion separate.

Evidence-backed conditionals:
- Pixiv: its own Help Center confirms location/region-specific work availability and permits changing account location via web settings, so a Japan exit is not inherently required for every Pixiv task. R-18/R-18G requires account age settings where eligible, independent of IP. https://www.pixiv.help/hc/en-us/articles/26578893289881-I-can-t-browse-certain-works-from-the-country-region-where-I-live and https://www.pixiv.help/hc/en-us/articles/235585288-I-would-like-to-view-age-restricted-contents-R-18-R-18G
- France adult websites: Arcom reported several pornography sites introduced mandatory age verification or voluntarily ceased France access during 2025. This is a content access consideration, but using another IP does not guarantee legal access, bypass all age verification or make a site's own policy disappear. https://www.arcom.fr/en/press/protection-persons-under-18-online-arcom-notes-introduction-age-verification-schemes-six-new-pornographic-sites
- Japan-only DMM/DMM TV/FANZA: DMM official guidance says some services cannot be used outside Japan, and that VPN/proxy detection itself can cause access errors. This is an example of when exact Japanese location could matter if the owner actually elects to use those services; no evidence confirms that owner currently uses them. https://support.dmm.com/accounts/article/45604 ; https://support.dmm.com/dmm-tv/article/48250
- Global streaming: Netflix states connecting with VPN can restrict which titles can be shown; changed country is not a guarantee of broader catalog and might degrade supported use. https://help.netflix.com/en/node/114701/
- Open repositories, coding, general web research, ordinary downloads: public-IP masking generally more useful than forcing one foreign country. An HTTP 403, missing public media or extractor failure does NOT by itself demonstrate a region block.
- Video/bulk archive downloads: sustained throughput and stable session exceed the value of frequent country switches. Public exit IP changes during active HTTP/TLS connections may interrupt downloads, trigger anti-fraud reauth or break streaming; mitigate with explicit user-configurable managed handover policy, not a false guarantee.

Destination and site-specific geo-policy should only trigger when (1) source explicitly says region unavailable or a reliable test isolates actual region as cause, (2) owner has rights and accessible provider route, (3) route is compatible with 75% speed budget and ongoing task identity, (4) risk from account flag/terms is shown. Do not blindly country-hop for every 403.

## 3. REVISED VPN NETWORK POLICY

Required: default full-phone protected egress on successful first-time Android consent/provisioning; audited/trustworthy free provider; owner has no foreign servers; SuperVPN excluded; privacy and throughput >=75% baseline; verify actual public IP (IPv4 and IPv6), DNS, provider fingerprint/exit and native Control network still works.

Routing modes:
1. AUTO FAST PRIVATE (default): choose closest available, best privacy + measured throughput and low latency; actual exit country can be anywhere eligible, no geographical assertion when unknown.
2. GEO ON DEMAND: attach owner-selected *target site/session* to a legitimate verified available country's exit IF it exists. UI shows reason, expected speed impact, provider limits and account restrictions. No imaginary free exit or unverified provider switching.
3. ROTATION: 30–60-minute configurable cadence initially ~45 minutes. Public IP must ACTUALLY differ, not merely tunnel reconnect. Long-running transfer work requires explicit configurable session continuity with a bounded deferral/manual preference if immediate rotation would abort data; otherwise report disrupted flows and retry-safe handling. Do NOT silently break user's strict rotation expectation: owner must approve rotation deferral policy before adopting it.
4. TOR MODE: Tor Browser for .onion; optional Tor VPN Beta evaluated as experimental full/app routing with Tor Project warnings; not simultaneously prepared with Android WireGuard VpnService, not advertised at normal <25% VPN loss.
5. NO ACCEPTABLE FREE EXIT: explicit BLOCKED. No invisible direct bypass and no gratuitous use of untrusted public proxy networks. User may choose which tradeoff to accept; Control cannot create foreign public IP infrastructure from code.

Cost/geo tradeoff: exact geolocation is not worth sacrificing more than 25% normal sustained speed for low/medium-priority use cases. Zero-cost foreign egress + automatic rotation is not currently proven by any public candidate provider under every condition. Proton Free standard WG config import is promising but number of free permitted distinct-IP switches/explicit region availability remains UNVERIFIED. VPN Gate explicitly logs metadata, prohibited as default privacy exit.

## 4. ROUND​ER AND RELATED APP OVERLAP: EVIDENCE FROM REPOSITORY

Owner repository Azrazieliz/AsterionRounder default branch main contains openlocaloffice-build/additions:
- UniversalReader.java supports bounded offline reading for PDF, EPUB, DOCX, PPTX, image/text and other formats;
- ReaderLibrary.java lists EPUB/PDF/Office/archive/image/3D files from owner-selected SAF folders;
- KoikatsuCards.java inspects Koikatsu PNG card metadata;
- additional epub-reader.js, model-viewer.entry.js, rich docx preview, premium-library UI, etc.;
- noworld-bridge/README.md describes mobile GLB/3D preview and source provenance.
The source shows existing developed features; it does NOT establish that all are functional in the installed Rounder app. Verify runtime only once explicit permission/testing allowed.

Therefore DO NOT build an independent Asterion Control PDF/EPUB/manga/3D viewer/file library or competing organizer if Rounder already covers that function. Route typed authorized tasks to Rounder via signed partner provider; use a narrowly scoped external document conversion/editing library only when Rounder cannot perform an essential authoring operation and cannot be extended by its own maintainer.

Functional ownership matrix:
- Control: assistant reasoning, browser/DOM automation with owner permission, task/cycle scheduling, task memory, GitHub tools, evidence, routing, signed app adapters, artifact creation requests.
- Downloader (separate owner/developer): media site discovery/acquisition/extraction/parallel downloads and provider-specific behavior. Do not reimplement Downloader or patch it in Control.
- Rounder: general user-selected file browsing, reading, previewing, common office/docs/EPUB, archives, model preview, file management where actually supported. Do not copy Rounder's UI/data wholesale.
- Core/Nexus: content knowledge, library tagging/classification, metadata recognition where defined; source/app agreements required.
- Art: image/generation/visual editing; Sound: audio/voice content; 3D Foundry: geometry/render and export; Writer: prose; Game: game generation/execution per owned app.
- AI browser engine is useful ONLY as a general computer-use facility: interact with existing installed browsers through accessibility/native APIs or PC Playwright where authorized; logins/forms/pages/research/test flows. It is NOT another permanent user-facing browser product, Downloader media extractor or Rounder reader. New custom browser shell requires a distinct proven need/approval.

When a capability is already present in another Asterion app, use the existing engine through the signed provider contract, preserving its identity, performance and data. If provider absent, mark UNAVAILABLE and do not fake Control implementation.

## 5. MODEL TRAINING: 500 CASES WERE ONLY AN INADEQUATE INITIAL SMOKE SET

Revised enterprise-scale proposed standard, all future and contingent on measured local/PC hardware and cost-free data rights:

A. PRETRAINED OPEN MODEL (not training from scratch): test several candidates on actual phone memory/TTFT/tokens/s/thermal and tool schemas; optional larger local Windows model.
B. TRAINING DATA != EVALUATION DATA. Maintain distinct legally reusable licensed/public corpora, validated Asterion project/code/test examples with owner permission, tool-call traces and synthesized problems with objective verification. Never automatically ingest private tokens/passwords/proprietary unknown sources into training.
C. TRAINING:
  - Phase 1: system/tool instruction tuning, retrieval, behavior conditioning and high-quality verified agent tool use.
  - Phase 2: LoRA/QLoRA parameter-efficient SFT on general questions, cross-domain planning, FR/EN, coding and OS/MCP tool use, evidence-based research.
  - Phase 3: error-recovery/reflection, preference training/contrastive ranking as available hardware and license permit; use actual tool receipts.
  - Phase 4: evaluate source patches of llama.cpp or compatible open runtime (context packing, tokenizer, KV cache, decoding/sampling, ARM/GPU use, tool grammar, streaming, power governor), benchmark against unchanged baseline. Modifying inference code is NOT equivalent to training weights; pretrained architecture surgery can require major retraining.
  - Phase 5: versioned release train/rollback, no arbitrary production auto-replacement without owner approval.
D. TESTING — INDEPENDENT, LOCKED:
  1. Minimum 50,000 task-level distinct HOLDOUT evaluation cases before claiming a mature all-rounder, stratified by real task and difficulty (20% short, 40% multi-step, 30% tools/cross-app, 10% adversarial/edge).
  2. Additional >=200,000 generated/scenario mutation STRESS/ROBUSTNESS cases, clearly reported separately and NOT treated as independent holdout accuracy evidence.
  3. >=2,000 true multi-step integration/workflow tests across Android/Windows/app adapters with real state assertions and durable receipts, staged and expensive only after core capability works.
  4. Human or expert-adjudicated sample >=1,000 cases for quality, ambiguity, creativity, tool usefulness and safe-but-not-overrestrictive prompts.
  5. Continuous regression after every model or inference code update: selected passing and failing variants, project-specific tasks and model release baseline.
  6. Additional sensitivity suite for owner-configurable unrestricted local content generation independent of OS authorization, secret leakage and paid API/irreversible operation barriers.
  7. Record p50/p95, first token, sustained tokens/s, RAM/storage, 5–30 min thermal/battery, network vs offline and actual verified outcomes.
  8. Create formal task taxonomy/benchmark before collecting training examples, avoid contaminated holdout, require multiple independent evidence sources.
E. Suggested 50,000 held-out case breakdown:
  10,000 broad general understanding/reasoning/multilingual;
   7,000 programming and repo editing with compiling/testing;
   6,000 valid typed MCP/tool invocations, permission/identity cases;
   5,000 web retrieval, citation/date/source conflict accuracy;
   5,000 file conversion/doc/spreadsheet/data calculations via delegated/executor tools;
   5,000 Android/PC operation, recovery and evidence;
   4,000 multi-app capability routes without duplicated engines;
   3,000 voice speech intent and proactive question flows;
   3,000 failure/diagnostic/security/privilege boundary cases;
   2,000 continuous development cycle, context/rollover/checkpoint scenarios.
  TOTAL 50,000 held-out; 200,000+ separate stress, 2,000+ true integration, 1,000+ independently human-reviewed quality cases.
F. Gates: score by verified outputs per category, not averaged magic number. FAIL/ABSTAIN when tool unavailable, report uncertainty, no false "I fixed it", no regressions in identity/signer, safe task replay, voice or VPN. User expects real capability; benchmarks are a mechanism, not a milestone by themselves.
G. Feasibility: open-weight general LLM + native tools can approach some ChatGPT workflows; exact proprietary model training and product service parity cannot be guaranteed from owner's phone or public weights. Training locally on PC only if compatible GPU/memory; otherwise retrieval, skills and tuning via lower-cost methods first. No paid cloud required.
H. OWNER WILL NOT BE THE TRAINER: The future Control Model Forge and assisted development workflow should automate dataset curation (under permissions), fine-tuning, evaluation, diagnostics, adaptation and versioned model proposals after actual authorization. This document does NOT say those operations were already executed.

## 6. DISCOVERY AND EVIDENCE PLAN BEFORE CODING

- For representative services in owner's browsing categories, collect a *site-specific matrix* of known geo errors vs auth/CAPTCHA/anti-bot vs extraction/HTTP403 vs age/account flags vs provider policy. Do not conflate all HTTP403 with geo blocks. Avoid handling personal content files or sites without consent.
- Prioritize IP masking, stable secure throughput and actual VPN performance, not speculative specific countries.
- If owner repeatedly encounters a named Japan-only or US-only resource, evidence becomes a task-specific requirement for geography.
- Keep source-based distinction: provider policy, tested actual device behavior and owner's personal preferences are different evidence levels.

## 7. CURRENT STATUS AS OF DESIGN REVIEW

DOCUMENTED ONLY. No new source coding, no training run, no on-device VPN tests, no files transferred/installed, no Rounder implementation change, no Downloader implementation change. Owner's previously installed Control remains intact. Full unpaid safe exit rotation and strict <25% loss are unproven. 50k/200k evaluation is future planned benchmark, not observed test results.

## 8. SOURCES

Pixiv location: https://www.pixiv.help/hc/en-us/articles/26578893289881-I-can-t-browse-certain-works-from-the-country-region-where-I-live
Pixiv R-18 setting: https://www.pixiv.help/hc/en-us/articles/235585288-I-would-like-to-view-age-restricted-contents-R-18-R-18G
ARCOM France: https://www.arcom.fr/en/press/protection-persons-under-18-online-arcom-notes-introduction-age-verification-schemes-six-new-pornographic-sites
DMM official: https://support.dmm.com/accounts/article/45604
DMM TV official: https://support.dmm.com/dmm-tv/article/48250
Netflix official VPN: https://help.netflix.com/en/node/114701/
Proton speed: https://protonvpn.com/support/increase-vpn-speeds
Proton Free server rules: https://protonvpn.com/support/change-server-free-plan
Rounder source root: https://github.com/Azrazieliz/AsterionRounder/tree/main/openlocaloffice-build/additions
Rounder NoWorld bridge: https://github.com/Azrazieliz/AsterionRounder/blob/main/openlocaloffice-build/noworld-bridge/README.md
Android system VPN: https://developer.android.com/reference/android/net/VpnService
