# P0 execution state — 26 November 2026

Integration target: `work/control-native-ai-reconstruction-20261126`, recovered at
`01f55230fcd9b0d5facef06c2909798a8b6c6cfc`. All existing V3–V6, R01–R08/R10,
B06/B09, Nexus ownership/migration and final-release criteria remain mandatory.
This is source integration and experimental evidence, not an accepted release.

## Implemented and source-tested

- Replaced the Ask/result-dialog path with `AssistantActivity`: native transcript,
  encrypted conversation titles/history in the **existing** memory database,
  project-scoped memory, reasoning settings, editing/regeneration through
  preserved revision copies, continuation, streamed text, cancellation, native
  Markdown/code/tables/links, text attachment intake, Android speech recognition
  and speech playback. Main and Tools both open the workspace. Full multimodal
  inference, charts/questionnaires/artifacts and model switching are unfinished.
- Model-native GGUF templates/tokenization now receive role-separated multi-turn
  UTF-8 messages. Actual token counts govern complete-exchange context packing;
  omitted history remains stored and its omission is disclosed. This is **not**
  million-token retrieval or canonical-requirement integration on Android.
- Streaming filters partial reasoning delimiters and incomplete UTF-8 code
  points before display/persistence. Model text never executes commands.
  Signer-pinned AppBridge capability discovery grounds operation proposals;
  native per-action authorization, current capability validation and a separate
  provider status query reuse the original specialist bridge. A provider status
  does not certify an artifact or application-specific postcondition.
- Corrected shared theme/dialog appearance and several slogan strings; increased
  primary touch targets to at least 48dp and retained all existing navigation.
  This is **not** completion of the entire application's visual audit.
- Android API35 Java source compilation passed locally. **37 pytest cases** pass,
  including **523 executed JVM assertions** for streamed delimiter/UTF-8 handling,
  stale callbacks, interrupted conversations and regeneration state. Source tests
  are not independent model evaluations or phone acceptance.

## Real neural adaptation experiment

The original Model Laboratory now links immutable adapter lineage to a full
base-weight candidate; adapter size is never substituted for full model RAM.

A local CPU diagnostic trained attention LoRA on the pinned Apache-2.0
`Qwen/Qwen3-0.6B` snapshot `c1899de289a04d12100db370d81485cdf75e47ca`.
This inadequate legacy baseline is **not** the approved final intelligence.
The corpus contains 12 exact owner-instruction quotations and eight deterministic
arithmetic examples. Twelve optimizer steps changed **1,146,880 parameters**.
No proprietary teacher responses or private-data exports were used.

Trainable tensor SHA256 changed from
`bbd7f01e0da2e6af3cf69b5e5bde3adecb9d4ed8db73030e8c4cb472276750a1`
to `df770b17111059d60d5ec13b5e452b5baa144d33da21b681cb031c2cfa6c8960`.
Adapter file SHA256:
`a8656be539ac27cec8525b4bf3c5afc650f69e6adc81479bb597f13a9045352e`.

A separate evaluator measured 12 held-out **reference-likelihood** cases:
mean NLL **3.809297 → 2.075416**. This does not establish task accuracy,
owner-behavior adaptation, resistance to general forgetting, mature intelligence
or human acceptance. Maturity counts remain **0 certified independent holdouts,
0 certified stress cases, 0 accepted integrated workflows, 0 human reviews**.
The diagnostic package and source provenance are in
`artifacts/model-laboratory/owner-adapter-diagnostic-20261126.tar.gz`;
exact records are in `reports/control-p0-20261126/`.

## Live baseline and preservation

Original bridge receipts `control-p0-20261126-1420-phone-status-01` and
`control-p0-20261126-1420-pc-status-01` completed successfully. Samsung SM-S948B,
Android17, Control0.9.38: authenticated native WSS connected over **Wi-Fi**,
3,860,828,160 bytes available RAM, battery16%, not charging. These are snapshots,
not current guarantees or cellular/soak acceptance. Installed model inspection
`control-p0-20261126-installed-model-inspection-01` confirms loaded native library,
484,220,288-byte verified legacy model; exact installed APK bytes were not read.
The existing Windows test checkout is at `df4d9085`, separate from integration.

No APK built, signed, transferred or installed; no production worker/watchdog,
paired secrets, signer, specialist engine or owner database modified.
Windows inventory confirms no Docker/installed WSL or torch/transformers/peft.
That host's independent training/sandbox dependencies remain unresolved. Local
Linux CPU training above removes the blanket assumption that training requires
CUDA, but does not provision or certify the Windows autonomous executor.

## Recovery checkpoint

Complete actual host/device model-quality evaluation, richer rights-cleared
behavioral histories, stronger-model adaptation and real general-capability
regressions. Finish the original durable supervisor's isolated execution and
crash-resume demonstration; connect exact-source requirements/cognition and
existing TeraBox; finish all remaining UI/integration and M0–M13 gates. Preserve
the release hold until a meaningful original-owner-signed final candidate can
undergo Samsung acceptance. Do not mark this checkpoint as product completion.


## Follow-up verification and neural qualification failure

CI run **45831474974** passed for integrated source `812bd68d`: 37 tests,
Android Java/resource integration and pinned native ABI checks. A broader source
sweep found three assertions already stale at the recovered baseline (old labels,
old modal inference location and pre-WARP VPN setup); their permission/functional
requirements are retained in updated checks and the expanded suite.

Two actual installed-phone requests completed through the original native WSS.
The identity variant answered that it was not running software; both returned raw
thinking delimiters. This directly reproduces the production defects, without
installing new source. The adult-career variant returned text rather than a
blanket refusal; factual accuracy and the reported original refusal remain open.

A separate six-case base/adapter free-generation comparison (12 model runs) also
found that **both variants still deny application integration on an unseen
paraphrase**, despite supplied runtime context. The diagnostic adapter is therefore
**not accepted for owner-behavior competence**. Its reference-likelihood gain is
not sufficient. General arithmetic and non-Asterion project questions are retained
as limited transfer probes; no general-retention, human-review or maturity claim.

Read-only `/api/v1/v2/models/candidates` now exposes full candidate and adapter
lineage under the original authentication. No mutation/promotion API is added.
Windows production source has not been promoted, so this endpoint is source-only
until the existing worker's release gates are met.
