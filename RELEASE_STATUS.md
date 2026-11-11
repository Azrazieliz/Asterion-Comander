# Historical release snapshot — not the live status

The original contents of this file were the Asterion Control **v0.2.0** implementation report. They described a prototype from before the native Samsung phone agent, Windows worker and private fallback were operational. Claims such as "Android APK not built", "no high-frame-rate video" and "laptop offline" must **not** be interpreted as the current device state.

For current procedures and dated evidence use [README.md](README.md) and [PROGRESS.md](PROGRESS.md). The older report remains available in Git history.

As of 2026-11-11, the existing worker has returned a successful real Android `phone_ui` receipt through the private fallback. New Android auto-repair / force-reinitialize code is committed in source, but must still be built, installed and accepted on-device before being declared delivered. Direct ChatGPT worker tool exposure and in-chat real-time stream availability must be evaluated separately from backend health.
