# ASTERION — 7* FROZEN MASTER v1
Date: 2026-11-05
Status: FROZEN — changes require explicit user authorization.
Canonical repositories: Azrazieliz/Asterion-Comander (app name **Asterion Control**) and Azrazieliz/Asterion-Sound (**Asterion Sound**).
This is a baseline/continuation contract, NOT authorization to alter any existing Asterion or NoWorld engine.

## I. Asterion Control — the control tool
**Purpose:** Give the user, primarily from Android, and ChatGPT (as the remote operator) effective control over the user's authorized Windows PC and Android devices. Replace Desktop Commander entirely with an independent, free/self-hosted implementation, not a wrapper or paid subscription.

**Core requirements**
- Android is the main, potentially sole visible interface; independent Windows and Android agents; wireless encrypted access locally and across networks, without permanent USB/ADB tether.
- Low-latency live screen/video for both sides; native APIs / UI accessibility first for clicks, gestures, state inspection, app automation; live visual frames only where necessary, avoiding repeated screenshot/click cycles.
- Remote PC and phone files, apps, terminals, processes, input, screenshots/recording when permitted, audio/video streams, builds, APK installation, logcat and diagnostics.
- ChatGPT operates Control like Desktop Commander via authenticated API + MCP; Control has **NO embedded AI, agent, inference, self-learning, or autonomous decision making**.
- ChatGPT-only hidden: terminal/commands, logcat, script library and script internals. User-facing UI: remote-control panels, device connectivity, resource/performance and health.
- Saved parameterized Python/PowerShell/shell/ADB routines for rapid direct and parallel execution, dependency-aware batching, job status/logs, cancellation, resumability and robust error reporting. Scripts are authored/changed externally (e.g. by ChatGPT); there is NO on-device "learning".
- Health: CPU, GPU, RAM/storage pressure, device battery/charging, temperature/thermal throttling where OS exposes them, IO/network, process load and safe control of jobs. Monitor accurately; do not invent inaccessible sensors or claim magical cleaning/acceleration.
- Minimal, efficient runtime for limited PC resources; persistent automation jobs across client disconnections; provenance and observable evidence, distinguishing written/built/installed/tested.
- No mandatory cloud, no recurring subscription; authenticate and encrypt remote access; least privilege, auditable operations and clear device authorization. Android capture permissions and OS secure-surface restrictions remain respected.
- Do not duplicate functions of NoWorld, Art, Core, Downloader, Rounder, 3D, KK or Adaptive Study. Control invokes those apps' existing tools / asset pipelines / scripts ONLY when authorized; it does not become their engine.

## II. Asterion Sound — the creation tool
**Purpose:** Original music, singing songs, character voice/dialogue/nonverbal vocal performance, and sound effects for NoWorld and other Asterion creations. Independent Android-first creative app with editing and ChatGPT API/MCP.

**Main user-facing sections**
1. Music: instrumentals without lyrics; songs with vocals; lyric generation/editing; artist choice, duets, separate featured artists, and blended profiles.
2. Voice: speech/dialogue, narration and nonverbal vocalizations (e.g. breaths, gasps, laughter, crying, moaning), SFW/NSFW options affecting available specific controls. **Singing belongs to Music, NOT Voice**.
3. SFX: environmental, physical, mechanical, fantasy, creature and scene sound effects (not singing and not a general voice studio).
4. Artists & Voices: persistent reusable individual profiles, imported reference tracks/isolated vocal samples, artist merging vs featuring, character assignments, locked voice identity/versioning.
5. Library/projects: reusable models/profiles/references/lyrics/versions and output assets.

**Specific behavior**
- Produce genuinely NEW music/voices/effects as well as reconstruct/import, not only clone or resample.
- Music/voice-to-code means import MP3/WAV/etc., infer editable structural or acoustic representation (notes, timing, instrumentation; speech/lyrics/phonemes, pitch/timbre/expression) and resynthesize modified or original audio. Preserve residual acoustics when symbolic transcription is insufficient; reconstruction fidelity must be measured, never guaranteed without validation.
- Artist profile: import e.g. 15 reference songs and lyrics, derive relevant musical/vocal/lyric characteristics, persist and reuse. Separate singing identity, musical style, lyric style and performance.
- Character voice identity must be stable across multiple renders, scenes and supported languages; Japanese first; English, Korean, Chinese also desired; **no French UI or French language generation**.
- Voice controls should be meaningful and audible: actual preview and compare of differences, explicit vocal action, duration, timing, inflection, breath/noise, voice profile; do not give blind generic pitch/brightness/expressiveness sliders.
- Lyrics generation using reference lyrics and persistent editing preferences; Japanese lyrics/mora/phoneme alignment prioritized.
- Distinct mode-specific SFW/NSFW options; user-facing explicit vocal and scene effects choices rather than generic labels. All outputs subject to applicable laws, rights and platform constraints.
- Sound cooperates with Asterion Art on video via timing/cues/lip-sync, and exports original media to NoWorld. Sound does not become a video editor or Unreal/game runtime. Control may run NoWorld's own import/build/test scripts externally.

## III. Separation and delivery
- Two independent repos, separate apps, shared only small versioned communication schemas where useful.
- Both expose authenticated API/MCP for ChatGPT, but API existence is NOT the same as a connected ChatGPT app.
- Prioritize real installed/tested Android workflows over demos; no invented install/test results.
- Preserve prior accepted source/architecture and avoid unrelated changes. Document every implemented step in PROGRESS.md, separating implemented, verified, blocked and next.
- These decisions supersede earlier suggestions of Control embedded AI, duplicate app engines, voice singing tab, or code-only music synthesis.
