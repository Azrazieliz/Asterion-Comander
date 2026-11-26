# Asterion Control neural training and Samsung qualification

Implement and train the independent phone-first Control intelligence specified
in the [owner directive](CONTROL_AI_OWNER_DIRECTIVE_PRIORITY_20261126.md),
[owner follow-up](CONTROL_AI_OWNER_FOLLOWUP_20261126.md) and
[approved scope index](CONTROL_AI_REQUIREMENT_ANCHORS_20261126.json).
Read the existing Model Laboratory and Skill Studio contracts, Phone-First V2,
the December Nexus merge requirements and the reconciliation register.
Preserve the original Control worker, signer, paired Android installation and
specialist ownership. Do not build or install an intermediate APK. Use only the
existing authenticated Control bridge for the owner's devices.

## Architecture and acceptance

Use an original Asterion neural candidate derived under a verified foundation
license, with real owner-specific SFT followed by preference learning. Retain
native tokenization, chat formatting and learned weights until measured
comparisons justify architecture changes. Evaluate dense GQA and long-context
hybrid attention for the phone, and larger dense or MoE checkpoints for stronger
comparison and legally permitted offline teaching. Track stored and active
parameters separately. Keep one primary general model resident during ordinary
phone use. Treat the optional Windows worker as an aid for heavy computation.
The prior Qwen, Gemma and Smol trials are controls and diagnostics. Avoid setting
a production model by checkpoint name, benchmark aggregate, or parameter count.

The central model handles language, reasoning, interpretation and action proposals.
Trusted Control code supplies exact source passages, current permissions, typed
capabilities, independent execution evidence, completion checks and durable task
state. Nexus/Core own taxonomy and libraries. Downloader owns acquisition.
Rounder owns document workflows. Art, Sound, Game/Pilot/Codex, KK, Elysium and
other specialist apps retain their own engines and data. If signed discovery
returns no advertised action, the assistant must report the missing interface.
The current phone receipt showed exactly two Rounder inventory read actions and
no capability packs for the approved KK and Downloader acceptance installs.
Do not infer any other installed capabilities from project documents or names.

Construct owner cases across difficult reasoning and coding; project and
requirements recovery; research and citations; reading and creating editable
artifacts; multilingual and multimodal understanding; authorized specialist
operations; voice; long-running development and recovery; and content behavior.
Measure legitimate adult, creative, academic, political, technical and
controversial requests for factual accuracy and unnecessary refusals.
Device operation permissions and credentials stay outside the model.

## Device and precision

Samsung documents the SM-S948B Galaxy S26 Ultra with Snapdragon 8 Elite Gen 5
for Galaxy. Qualcomm specifies Oryon CPU, Adreno GPU and Hexagon NPU. An actual
authenticated Control health receipt on Android 17 reported 11,623,395,328 total
bytes, 3,733,700,608 available bytes, nominal thermal status, and 35% battery at
28.1 °C, unplugged. These are point-in-time measurements. Probe the actual
registered backend and successful offload before attributing speed to a GPU/NPU.
CPU is the reference. Compare Adreno Vulkan/OpenCL and Hexagon HTP or compatible
LiteRT/QNN with the same architecture, inputs and configuration. Separate weights,
KV cache, activation/output precision, shared memory, and working buffers.

1. Record BF16 and FP16 workstation references with unchanged weights.
2. Evaluate 8-bit weight quantization first, for example GGUF Q8_0 at the pinned
   llama.cpp revision. Hold KV precision and prompts constant. Then separately
   compare FP16 versus Q8 KV with the same weight file. Q8_0 includes block overhead.
3. Treat 12-bit as a weight-memory estimate until there is a concrete runnable
   mixed-precision or packed artifact. The pinned llama.cpp has no standard
   Q12 profile. For a mixed 8/16-bit experiment publish the actual byte-weighted
   precision, sensitive layers held at 16 bits, and backend compatibility.
4. At 7B, lower bounds are 7/10.5/14 GB at 8/12/16 bits before context or compute
   memory. At 12B, those bounds are 12/18/24 GB. The phone snapshot cannot admit
   those profiles fully resident. Use the workstation/reference tier or evaluate
   a demonstrated storage/offload scheme with measured sustained bandwidth.
   Accelerators and TeraBox do not add device RAM.
5. Lower weight precision or change the architecture only after the reference
   comparison quantifies which costs and quality losses motivate the change.
   Record cold/warm time to first answer, prompt processing, token rate, model
   and context PSS/peak, energy, thermal throttling, failures, and CPU fallback.

References: [Samsung SM-S948B](https://www.samsung.com/de/business/smartphones/galaxy-s/galaxy-s26-ultra-black-512gb-sm-s948bzkgeub/),
[Qualcomm platform](https://www.qualcomm.com/smartphones/products/8-series/snapdragon-8-elite-gen-5),
[llama.cpp Snapdragon](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md),
[LiteRT Hexagon](https://developers.google.com/edge/litert/next/qualcomm).
A non-legacy comparison may include the MIT [Phi-4-reasoning-plus 14B](https://huggingface.co/microsoft/Phi-4-reasoning-plus)
or Apache-2.0 [Olmo-3-7B-Think](https://huggingface.co/allenai/Olmo-3-7B-Think).
These are reference candidates requiring task-suite and device evidence.

## Training execution

1. Export only rights-cleared owner instructions, corrections and actual verified
   trajectories through the established paths. Preserve exact source identity,
   workflow family, project, receipt hashes and correction origin. Keep raw
   credentials, private prompts and output archives in owner-controlled storage.
   Use actual independently confirmed outcomes to produce labels. Separate
   authored examples, real trajectories, generated examples and human judgments.
   `scripts/control_ai_workflow_corpus.py <terminal-receipt.json> --output <new-dir>`
   creates provenance-bound starter examples from signed app discovery receipts.
   These describe availability and do not count as completed workflows.
2. Freeze disjoint workflow families and temporal groups before training. Seal
   holdout material outside optimizer access. Audit near-duplicates and leakage
   between train and evaluation, including project-name substitutions. Use
   general-domain replay, multilingual and non-Asterion tasks to detect forgetting.
   Use unique cases and retain the same suites across comparison runs.
3. Stage a license-reviewed local safetensors checkpoint pinned by source revision
   and obtained file hashes. Retain tokenizer/config and native template. Build
   a high-precision standard. For larger candidates, run NF4 QLoRA only after the
   exact software stack and memory admission are established. A CPU NF4 primitive
   ran locally before this pass. It does not establish full-model training on
   the original Windows worker. Keep all paid and external private-data runs
   outside the standing authorization.
4. Use the existing local trainer with full input provenance and native
   assistant-only masking. Use learning rate, context length, rank, steps,
   memory budget and target modules measured for the selected candidate. For
   preference learning, each JSONL row carries `prompt` (role/content array
   ending in user), `chosen`, `rejected`, `source`, `workflow_family`,
   and `rights_verified: true`. Give the trainer the matching SFT train and
   held-out datasets. Their rows carry `messages`, `domain`, `source`,
   `workflow_family`, and `rights_verified`. Example invocation after
   staging, with budget arguments replaced by the measured configuration:

   ```console
   python scripts/control_ai_adaptation.py train --device cuda --precision nf4 --base /owner/model-snapshot --revision <commit> --train /owner/train.jsonl --holdout /owner/heldout-validation.jsonl --output /owner/asterion-candidate --context 2048 --rank 16 --accumulate 8 --preferences /owner/preferences.jsonl --preference-steps <steps>
   ```

   For a CPU run specify `--device cpu --memory-budget-mib <measured-budget>
   --max-steps <steps>`. Compare native-precision LoRA separately. This trainer
   retains the SFT adapter, preference run and hashes of changed weights.
   The independent sealed evaluation set stays with the evaluator.
5. Reuse Model Laboratory and the existing model evaluation ledger. Evaluate
   unadapted neural-only, SFT, preference-trained, retrieval, and integrated
   variants using the same cases. Score free generation and verified side
   effects separately from reference likelihood. Record missing tools,
   incorrect factual answers, refused legitimate queries, false completion,
   unsafe authorization, forgotten requirements and restart recovery.
   Preserve 50,000 independent held-out cases, 200,000 distinct stress cases,
   2,000 real integrated workflows and 1,000 human reviews as maturity gates.
   The exploratory recall adapter failed an unseen application-identity
   variant and remains unqualified.
6. Export authorized usable GGUF weights or a PEFT-to-GGUF LoRA bound to the
   exact base. Record tensor compatibility and any losses against the original
   precision. Package a reviewed signed Control profile with base hash/size,
   optional adapter hash/size/base hash, weight precision, distinct KV bits,
   named available backend/offload, and measured memory estimate. Set
   `allow_smaller_context` only when the experiment explicitly allows it.
   Verify sustained Samsung quality and resource use before selecting or
   promoting. Use established encrypted TeraBox storage only when its existing
   provider path can verify the archive and restore it.

Near GPT-6.2 Astra or Claude Fable 5.5 capability within the Asterion ecosystem
requires actual comparative workflow results. The reference, source integration,
training, and physical Samsung acceptance are independently measured stages.
