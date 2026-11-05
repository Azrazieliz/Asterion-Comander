# Asterion Control 0.3.0 (baseline retained from Remote v0.2.0)

**Standalone, self-hosted desktop and Android remote control.** No Desktop Commander package, account, server, or subscription is involved. The source is included; the frontend is an installable web app. The Windows computer runs the agent, and phones can operate it from a private network connection. Android device commands are sent over an *authorized* local or wireless ADB connection.

## Windows — fastest startup

1. Extract the ZIP on the Windows computer.
2. Install [Python 3.11+](https://www.python.org/) with PATH enabled if needed, then double-click `START_ASTERION_CONTROL.bat`.
3. The launcher installs Python packages, creates a strong random API token in your Windows user profile (once), prints it in the terminal, and starts the API at `http://127.0.0.1:8911/`.
4. Open the URL, paste the token, click **Connect**. The server is deliberately bound to the PC's loopback interface by default.

If you use a virtual environment manually:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ASTERION_API_TOKEN = (& .\.venv\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(40))')
$env:ASTERION_REMOTE_ROOT = $HOME
$env:ASTERION_ALLOW_SHELL = '1'
$env:ASTERION_ALLOW_ANDROID_SHELL = '1'
.\.venv\Scripts\python.exe -m uvicorn asterion_remote.app:app --host 127.0.0.1 --port 8911
```

**Files:** `ASTERION_REMOTE_ROOT` defines the default file-tree root. For additional authorized drives use `ASTERION_ALLOWED_ROOTS` separated by your OS path separator (for example `D:\;E:\` on Windows). Shell commands can access whatever the PC user account is permitted to access. To browse an entire drive, set `ASTERION_REMOTE_ROOT` to its root (for example `C:\`). Do not run the server as administrator unless a specific task requires elevated access.

## Android control

1. Install the official [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) on your PC so `adb` is available in PATH. Set `ASTERION_ADB` to the full path of `adb.exe` if needed.
2. On your own phone, enable **Developer options → Wireless debugging**, use **Pair device with pairing code**, and enter the IP:pairing-port and code using **Pair Wi-Fi** in the Android tab. Connect to the *separate* IP:debugging-port with **Connect Wi-Fi**. Alternatively, connect via USB and authorize the PC's ADB key on the phone.
3. Press **Find devices**, select the authorized phone. Screen capture, tapping, swiping, back/home/recent apps, launching packages, UI hierarchy, file transfer and ADB shell are now available. The **Android shell** toggle uses `ASTERION_ALLOW_ANDROID_SHELL=1`.

No root or paid Android mirroring subscription is required. Android input text through ADB currently supports ASCII; extended Unicode input needs an IME or clipboard bridge. DRM-protected or system-secure windows may show as blank in screenshots. Wireless ADB depends on Android's debugging pairing and can disconnect when its settings change.

## Control from phone and other computers

The server starts on `127.0.0.1` to avoid accidentally exposing complete control of your devices. To use the web UI remotely, connect the PC and phone through an encrypted VPN/tunnel such as a self-hosted WireGuard server or a private Tailscale network, and publish the localhost service through that secure tunnel with HTTPS. **Do not port-forward HTTP port 8911 publicly.** Once reached over HTTPS, use the browser's **Add to Home Screen / Install App** option on Android.

**Important:** the current Android-control implementation requires the Windows agent to be running, paired with the phone over ADB, and reachable from your client. It is not yet an independent, native Android background service. Desktop and phone screens are captured as periodic images, not as low-latency video streams.

## Use from ChatGPT / other MCP clients

Authenticated MCP-compatible Streamable HTTP is available on the same service:

`https://your-secure-endpoint.example/mcp`

The MCP endpoint requires the same `Authorization: Bearer <API token>` as REST, plus `Accept: application/json, text/event-stream`. The connection must be explicitly added to a compatible client; **making the endpoint does not automatically give this chat access to it.** ChatGPT availability for custom MCP connections and full read/write tool support depends on your ChatGPT account/workspace. You can also use a **Secure MCP Tunnel** where supported instead of exposing a public endpoint. See [OpenAI custom MCP setup](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).

Local MCP stdio also works without any cloud or MCP SDK dependencies:

```powershell
# Start the MCP stdio bridge from the project root with ASTERION_API_TOKEN configured
.\.venv\Scripts\python.exe -m asterion_remote.mcp_protocol
```

The bridge exposes desktop screenshots, input, terminal, files, system and process lists, Android screenshots, input, ADB shell, packages and Wi-Fi pairing. Tools that modify the PC or Android device require the agent to permit the operation. Access must be limited to devices you own or are authorized to manage.

## REST endpoints (selected)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Host and capabilities |
| GET | `/api/v1/system`, `/api/v1/processes` | Host diagnostics and processes |
| GET | `/api/v1/monitors`, `/api/v1/screen` | Monitor layout and PC screenshot |
| POST | `/api/v1/input` | PC mouse, keyboard, drag, scroll |
| GET/PUT/POST/DELETE | `/api/v1/files` and `/api/v1/files/*` | List, read, write, search, upload, download, move, delete |
| POST/GET | `/api/v1/commands`, `/api/v1/commands/{id}` | PC terminal jobs and output |
| GET | `/api/v1/android/devices` | Paired ADB devices |
| POST | `/api/v1/android/pair`, `/api/v1/android/connect` | Pair and connect wireless debugging |
| GET | `/api/v1/android/{serial}/screen` | Android screenshot |
| POST | `/api/v1/android/{serial}/input` | Android tap, swipe, key, type |
| GET | `/api/v1/android/{serial}/ui` | Android UI hierarchy |
| POST | `/api/v1/android/{serial}/shell` | Authorized Android shell |
| POST | `/api/v1/android/{serial}/push`, `/pull`, `/install` | Android file transfer and APK install |
| POST | `/mcp` | Authenticated MCP JSON-RPC |

Swagger REST reference is at `/docs`.

## Security defaults

- API and MCP commands require a 32+ character bearer token and run **only** with the permissions of the logged-in OS user.
- Origin headers for MCP are rejected unless explicitly listed in `ASTERION_ALLOWED_ORIGINS` (comma-separated HTTPS origins); clients without an Origin header may connect if authenticated.
- Only paths inside `ASTERION_REMOTE_ROOT` or the explicitly listed `ASTERION_ALLOWED_ROOTS` are available through the file API. Remote terminal commands are disabled unless `ASTERION_ALLOW_SHELL=1`, and Android shell is disabled unless `ASTERION_ALLOW_ANDROID_SHELL=1`.
- Files transferred by upload stream directly to disk; use `ASTERION_UPLOAD_LIMIT_BYTES` to enforce an optional cap (0 = unrestricted).
- The browser retains the token only in the current page's memory. Closing or refreshing it disconnects the UI; the launcher keeps the secret privately in the Windows user profile.
- Windows lock screen, secure attention (Ctrl+Alt+Del), UAC prompts on the secure desktop, Android secure windows, and device permission prompts cannot be bypassed by ordinary desktop input/ADB.

## Verification performed

- FastAPI test suite: authentication, file CRUD, upload, restricted path resolution, MCP method handling, system/process APIs, mocked Android ADB commands and text validation.
- JavaScript syntax checked; responsive desktop/mobile layout loaded in headless Chromium with no runtime errors or horizontal overflow.
- **Not tested on your actual Windows PC or Android phone:** the remote Windows device was offline when this version was created; no native Windows or Android binaries were compiled in the current build environment.

## Current limitations / roadmap

This is a **working source-level beta**, not a fully installed system. It does not yet have a native Windows installer, standalone Android Accessibility/MediaProjection agent, full-motion low-latency remote video, automatic HTTPS provisioning, unattended background service, complete PDF/document support, or end-to-end device testing. Those tasks require the authorized target devices and their native build environments. ADB-based phone control works through the Windows PC, including wireless ADB pairing.


> v0.3 changes are documented in [README_CONTROL_ADDENDUM.md](README_CONTROL_ADDENDUM.md), with honest status in [PROGRESS.md](PROGRESS.md). The earlier baseline descriptions remain as evidence of inherited limitations.
