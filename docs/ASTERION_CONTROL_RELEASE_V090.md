# Asterion Control v0.9.0 — owner-signed update

This release upgrades the pre-existing Android application in place. It is not a new
app, replacement engine or fresh installation.

## Implemented in source

- Owner-started speaker/microphone interaction with idempotent question IDs,
  on-device speech recognition, bounded microphone timeout, transcript
  acknowledgment and explicit STOP.
- Phone-resident persisted ChatGPT continuation cycles: start, status,
  pause, resume, stop, checkpoint history, response acknowledgment,
  new-chat guard, and crash-aware non-replay behavior.
- Terminal response recognition: a unique assistant ACK marker advances
  the next cycle; a DONE marker ends it. A spoken-question marker asks
  the owner over the phone and carries the spoken answer into the next
  checkpoint after it was received.
- Private HTTPS outbound phone relay on Wi-Fi, cellular or VPN. Stale
  commands expire, uncertain results are not replayed, old completed
  commands are archived, and pending IDs remain inspectable.
- Direct MCP tools for voice, cycles, device health, app observation
  and remote status; catalog discovery remains available when the
  Windows worker is not running.
- Original compatible Android signing certificate stored as protected
  GitHub Actions secret, without requiring the Windows PC for builds.

## Deployment and limitations

- Android package installation still requires owner confirmation from the
  system installer. This is an Android platform rule.
- Live phone-only connectivity needs the existing Control bridge to be
  configured with its private repository credential and an authorized
  ChatGPT/Control connector. Source compilation alone cannot grant either.
- Speech recognition requires on-device recognition availability and an
  owner-authorized foreground microphone service.
- The foreground ChatGPT app can be observed through consented
  Accessibility; background ChatGPT reasoning is not independently
  executed by Asterion and model/usage limits still apply.
- Repeated cycles using the existing conversation can advance on distinct
  visible ACK/DONE markers. New-chat transitions conservatively require
  verified navigation to avoid overwriting existing drafts.
- The canonical update feed verifies the APK's SHA-256 and requests
  in-place installation without removing app data.
- The actual Samsung install and cellular/voice acceptance have not been
  observed from this CI environment, so they must not be marked verified.

Canonical frozen 7-star requirements, original project IDs and prior app
data are preserved.
