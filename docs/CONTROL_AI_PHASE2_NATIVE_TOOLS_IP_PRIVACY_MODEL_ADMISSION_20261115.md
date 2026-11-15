# ASTERION CONTROL — Phase 2: Native AI tools, IP privacy and actual device-aware model selection

Date: 2026-11-15.
Branch: work/control-ai-core-20261115.
Implementation status: GITHUB SOURCE COMMITTED, ISOLATED PYTHON + JVM TESTS PASS. Android APK NOT built, installed or device tested. Production Windows worker not modified.

Owner's latest VPN instruction supersedes previous strict country choice: fast free IP replacement/hiding to access region-restricted general browsing is primary; Japan is a NICE-TO-HAVE, never a blocker. Tor/onion and prior <25% speed-loss ceiling remain in scope. SuperVPN remains excluded. No legitimate free exit provider was installed or proven.

## Committed features

1. Private IP exit selection, no mandatory country
- Updated asterion_remote/vpn_route_policy.py. Free/privacy-reviewed owner-authorized exit, measured download and upload >=75% comparable direct throughput, no detected DNS/IP leak, preserved native Control connectivity and actual public IP observations required to qualify a route.
- Country may be unknown or non-Japanese. Optional Japan request prefers available JP but correctly falls back to a verified fast exit elsewhere. Never claims mere selection is an active tunnel.
- Scheduled verified rotation remains an advanced provider-dependent ability, not a prerequisite for a working basic IP hider.

2. Real Android public-exit observation
- New android/app/src/main/java/com/asterion/control/PublicExitIp.java: fixed HTTPS observer, redirects refused, bounded response/timeouts, literal-only public IPv4/IPv6 validation. It sends no owner credentials, files or prompts; the third-party observer necessarily sees connection source IP. Only used on explicitly owner-initiated VPN connect or recheck, never at startup.
- Updated ControlPrivateVpn.java: public IP before and after WireGuard GoBackend activation, separate observed exit versus original baseline, honest result states public_ip_changed / public_ip_unchanged / baseline_unavailable / exit_probe_failed. Explicit owner-initiated recheck; never labels DNS or entire-device leak protection as verified.
- Updated MainActivity.java: displays actual exit IP, changed status and errors, owner button Check exit IP while tunnel active. No provider was bundled, logged in or connected by this source change.
- Added tests/java/PublicExitIpCheck.java in Android test tree and scripts/verify_java_public_exit_isolated.py. Windows actual javac + java compiled and ran 27 public/private/changed-IP assertions. Bridge receipt results/ctl-source-20261115-2047-agentvpn-java-e2.json. The original Android app has NOT been compiled, signed or installed.

3. Finite native-AI real tool executor, DISTINCT from overnight development cycles
- New asterion_remote/native_assistant.py. Durable SQLite request-id before inference or tool actions, no raw user prompt/answer stored, bounded JSON-only local-model tool loop, replay fail-closed, explicit server tool scopes, verified/native receipts distinct from model claims.
- Real existing Control functions bound: Windows host health, session history/status, true overnight cycle status (read-only), Skill Studio list, Model Laboratory list, owner-approved scoped file hash and limited source text inspection.
- Mutations require separate owner approval, allowlist and server flag: deterministic native PC/phone session, previously SHA-approved Skill Studio workflow, approved official GitHub MCP tool. Request IDs are fixed by Control so model cannot force duplicate side effects. Queued jobs are NOT reported completed.
- New asterion_remote/assistant_routes.py mounted in existing app.py. General-purpose owner-local model adapter from local_model_provider.py now has a distinct instruction from overnight developer model; no paid cloud and no topic-category filter imposed at this layer. The local inference server and model still need actual deployment.
- New real tool and API tests test_native_assistant.py and test_assistant_routes.py. Includes actual wait-only PC session and approved skill running against source-only isolated test journals; all owner data preserved.

4. Actual hardware-gated candidate model selection
- Read-only Control phone status proved Samsung SM-S948B Android 17 with 11,623,395,328 bytes total and 3,656,753,152 bytes available memory in sampled state, 68,251,230,208 bytes free storage, battery 48% while charging, temperature ~42.4C, moderate Android thermal status=2. Bridge receipt results/ctl-observe-20261115-model-phone-r1.json.
- Windows read-only inspection: ~8.19 GB RAM total, 2.62 GB free, 2 physical/4 logical Intel cores, Intel UHD integrated GPU. results/ctl-observe-20261115-model-pc-hardware-r2.json. No discrete model-training GPU observed.
- New asterion_remote/model_admission.py and model_capacity_routes.py connected to existing paired native phone-status API. Admission enforces memory reserve >=1 GB, thermal/storage/battery constraints, author/license/hash verification, real peak-memory estimate before even scheduling a benchmark. Explicitly reports NOT LOADED / NOT TRAINED / NOT DEVICE BENCHMARKED. Runtime fit is not quality.
- Provisional licensed candidates for real later benchmark: official Qwen/Qwen3.5-2B Apache-2.0; smaller Qwen3-1.7B and 3B SmolLM3 alternatives depending actual tokenizer/runtime compatibility, accuracy and phone performance. No weights downloaded, no model SHA known, no real inference measured.
  https://huggingface.co/Qwen/Qwen3.5-2B
  https://huggingface.co/Qwen/Qwen3-1.7B
  https://huggingface.co/HuggingFaceTB/SmolLM3-3B

## Exact source-only verification

- Latest isolated source on Windows: 85 Python files, zero syntax errors, 105 Python tests passed, zero failures/errors. Bridge result results/ctl-source-20261115-2146-modelgate-g1.json.
- Earlier after native assistant source reading and approved Skill Studio execution: 93/93 Python tests passed, results/ctl-source-20261115-2115-skills-agent-f1.json.
- Android-independent Java parser test: javac compile success, Java unit 27/27, results/ctl-source-20261115-2047-agentvpn-java-e2.json.
- All tests read exact code from isolated GitHub branch into throwaway Windows temp folders. No Android APK compilation, no installed model, no real VPN/tunnel test, no working general AI claim or production deployment.

## Remaining release gates

1. Actual phone-native local inference engine + correct quantized model weights, speed/thermal/RAM benchmarks and useful general assistant quality, optional PC only if hardware sufficient.
2. Train/adapt model where realistically possible using owner-licensed data, versioned LoRA and large independent held-out tool/coding/research/integration evaluations; synthetic tests are not proof of model intelligence.
3. Connect real tool-runner to actual phone UI, full audio assistant, verified repeated overnight project work and cross-app signed providers.
4. A legitimate trustworthy free public VPN exit with measured changed external IP, full-device privacy, throughput >=75% direct baseline and active Control connectivity; Tor/onion separate. Japan optional.
5. Full cybersecurity/privacy scanning, quarantine/recovery, reverse-engineering laboratory, live GitHub MCP tool acceptance, Skill Studio/Model Lab UI, premium UI and all approved integrations.
6. Once separately authorized: compile Android, keep ORIGINAL owner signer/package and all data, test on actual phone and Windows, full regression, long-duration thermal/performance acceptance, safe APK upgrade.

Scope boundaries: No modification of Downloader or other Asterion specialist apps, no replacement of native WSS/pairing/Windows worker, no paid dependency, no silent VPN setup. Current user authorized implementation; original no-build/no-install hold remains unless explicitly changed.
