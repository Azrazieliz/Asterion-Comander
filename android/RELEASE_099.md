# Asterion Control v0.9.9 — owner-signed native update

- Eliminates obsolete one-time ChatGPT authorization/key-copy UI and duplicate checkpoint and direct-MCP cards; keeps the authenticated transport and existing pairing.
- Preserves original Android package `com.asterion.control`, signer, permissions, settings, files and device data through an in-place update.
- Defaults to 0.96 speech rate and neutral pitch, Android assistant speech channel, installed high-quality offline voice matching the requested locale; never forces a different accent or a network voice.
- Owner-token API `GET/POST /voice/settings` provides bounded voice rate/pitch and reports selected native voice; voice question/status/ack and consented enable/stop remain supported.
- Existing 65ms screen frame budget, fresh-frame native MJPEG and persistent private WebSocket preserved; actual on-device FPS depends on screen motion and resource/thermal state.
- ChatGPT-operated checkpoint queue, status, dispatch, acknowledge, cancel and replay protections retained. No unsanctioned autonomous model turns.
- CI source tests and native release Java compilation must succeed before publishing; use ORIGINAL signer only.
