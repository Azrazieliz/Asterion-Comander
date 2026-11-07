# Asterion Control v0.9.8 – original-owner-signed Android update

- Preserve installed `com.asterion.control` identity and original signer.
- Direct owner-authenticated phone voice lifecycle POST `/voice/enable` and `/voice/stop` with Android microphone and foreground restrictions intact.
- Existing `/voice/question`, `/voice/status`, and `/voice/ack` remain backward compatible.
- Capture interval 65 ms in automatic/full when thermal and memory safeguards permit.
- Native MJPEG stream sends only newly encoded frames instead of repeating JPEGs at a hard-coded 125 ms interval.
- Windows authenticated WebSocket consumes the persistent Android MJPEG stream rather than creating one new HTTP request per frame.
- Existing ChatGPT-owned checkpoint queue/dispatch/ack/cancel remain the supported cycle APIs; Android-autonomous loops remain disabled.
- Runtime confirmation of 14 FPS requires the new APK installed and live measurement on phone.
