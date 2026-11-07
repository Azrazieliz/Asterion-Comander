# Asterion Control v0.9.10 — owner-signed Android update

- Adds authenticated **own-process** Android logcat (/diagnostics/logcat) with bounded, redacted output; no ADB and no privileged system logs.
- Holds exclusive transient Android audio focus during spoken prompts and speech recognition, releasing it after an answer, failure, or stop so compliant music players resume.
- Preserves high-quality locally installed English TTS voice and existing configurable rate/pitch API.
- Preserves native 65ms capture interval, cellular/direct WSS transport and checkpoint queue/ack/cancel contracts.
- No uninstall; preserve com.asterion.control signing identity, existing device pairing, credentials, app files and permissions.
- Requires native Android device acceptance tests after in-place installation.
