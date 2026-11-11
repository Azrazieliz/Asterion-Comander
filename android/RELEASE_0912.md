# Asterion Control v0.9.12 — real ChatGPT blue-arrow send

- Preserve original `com.asterion.control` Android signing certificate, installed data, encrypted pairing and private GitHub bridge.
- Respect the user's chosen keyboard. Control types through the current editor and clicks the actual visible ChatGPT **blue Send arrow** using a bounded accessibility gesture when Compose hides the Send button from accessible nodes.
- Require ChatGPT in foreground, a genuinely visible keyboard window, a verified exact queued message, and an empty or identical existing draft.
- Never press Enter as a substitute for Send. Never overwrite a user's draft.
- Only mark sent-unverified when the typed draft has cleared; await an actual observed assistant reply before acknowledging the checkpoint.
- Keep native screen, speaker/microphone, logcat, Windows PowerShell, and previous device control APIs unchanged.
