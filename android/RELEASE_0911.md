# ASTERION Control v0.9.11 — Android native keyboard action path
- Preserve original app signer, all app data, existing signed updates, private relay, screen and voice APIs.
- Enable Android AccessibilityService native IME editor integration (Android 13+) for Compose ChatGPT message fields that lack editable accessibility nodes.
- Commit an operator-queued checkpoint only into an empty ChatGPT text field; never replace user drafts.
- Send only with the editor's IME_ACTION_SEND or an accessible Send control; no blind Enter presses.
- Require draft clearance before a sent-unverified receipt; require an observed reply for acknowledgment.
- Include foreground package and IME action in authenticated native UI status.
- Other Asterion apps require authorized action APIs before workflows may be triggered by voice.
