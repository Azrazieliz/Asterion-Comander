# Asterion Control native cross-app bridge — protocol v1

**Status (2026-11-07):** Control-side implementation is in the Android development branch. Other Asterion apps have received **requests only**, not source changes. The partner-provider handshake, actual actions, and recovery are unverified on a device until at least one app implements the protocol.

## Principle

Asterion Control is the owner's phone-control, transport, and authenticated MCP operator. It never replaces an application engine. Project-specific capabilities remain in that app. No unrestricted shell, cross-app logcat, shared secrets, root access, or automatic cross-app approvals.

## Discovery and local consent

The partner app must be visible as an installed launchable package and register a ContentProvider with **exact authority** `<partnerPackage>.asterion.bridge`, exported only with independent caller identity and owner authorization checks. Control checks `ProviderInfo.packageName` against that exact package, verifies the app's **APK signing certificate SHA-256**, and requires the owner to explicitly approve it from Control's **Asterion app integrations → Manage app access** screen. Approval is pinned to that certificate. A changed signer invalidates consent.

Remote clients **cannot approve, change or bypass app permissions**. Partners must independently verify the caller UID/package/signature and implement their own owner authorization, allowlisted operations, limits, and privacy rules.

For Android 11+ package visibility, Control discovers apps through the existing Launcher catalog and resolves their declared providers. Providers not visible to the OS will not appear. The partner team must verify actual discovery on the target Android version.

## Android IPC contract

For Android ContentResolver on `content://<partnerPackage>.asterion.bridge`:

| `ContentResolver.call` method | Bundle input | Bundle output |
|---|---|---|
| `asterion.v1.invoke` | `protocol_version=1`, `request_id`, `action`, `payload_json` | `result_json` (JSON string, maximum 8 KB) |
| `asterion.v1.status` | `protocol_version=1`, `request_id` | `result_json` |
| `asterion.v1.cancel` | `protocol_version=1`, `request_id` | `result_json` |

The partner's `result_json` is a JSON object with `ok` (boolean), `status` (lowercase snake_case; e.g. `accepted`, `running`, `completed`, `failed`, `cancel_requested`), and optional bounded `result` or `reason`. The partner must idempotently key operations by `request_id`, maintain meaningful progress, and never claim cancellation was completed just because a cancel request was received.

Control persists an operation receipt **before** dispatch. If Binder fails or times out, it returns `outcome_unknown` / `retry_safe=false` and forbids replay with that ID. Duplicate request IDs are rejected, including when sent for a different app/action. Control's binder wait is bounded (7 s invoke, 6 s operation); this does not guarantee the remote action stopped. Only the partner owns completion and cancellation semantics.

Input restrictions: package must match an installed launcher app's exact name; action ID lower-case dot/hyphen/underscore, max 80; request IDs 8–100 safe characters; JSON payload max 4096 characters; partner result max 8192 characters. No arbitrary shell commands, intents, URIs or arbitrary file paths are exposed by this bridge.

## Authenticated transport interfaces

- `GET /app-bridge/apps` — list partner-provider availability and locally approved state.
- `POST /app-bridge/invoke` — `{"package":"...","action":"...","request_id":"...","payload":{}}`.
- `POST /app-bridge/operation` — `{"package":"...","request_id":"...","cancel":false}` (or `cancel:true`).
- Native MCP: `control_phone_app_bridges`, `control_phone_app_invoke`, `control_phone_app_operation`.
- Optional authenticated Windows proxy: `/phone/app-bridge/apps`, `/phone/app-bridge/invoke`, `/phone/app-bridge/operation`.

These endpoints remain subject to the existing paired bearer, private-LAN/VPN, authenticated MCP gateway, and on-device per-partner approval. Do not expose the raw Android HTTP service publicly.

## Partner repository requests (requests ONLY)

Created issues:
- [Asterion Core #42](https://github.com/Azrazieliz/Asterion-Core/issues/42)
- [Downloader #20](https://github.com/Azrazieliz/AsterionDownloader/issues/20)
- [Art #12](https://github.com/Azrazieliz/AsterionArt/issues/12)
- [Adaptive Study #1](https://github.com/Azrazieliz/Adaptive-Study/issues/1)
- [Game Central Database #1](https://github.com/Azrazieliz/Game-Central-Database/issues/1)
- [Cosplay Download #16](https://github.com/Azrazieliz/Cosplay-Download/issues/16)
- [NoWorld #90](https://github.com/Azrazieliz/NoWorld-False-Horizon/issues/90)
- [Rounder #15](https://github.com/Azrazieliz/AsterionRounder/issues/15)
- [Games #2](https://github.com/Azrazieliz/Asterion-Games/issues/2)
- [3D #1](https://github.com/Azrazieliz/Asterion-3d/issues/1)
- [KK #1](https://github.com/Azrazieliz/Asterion-kk/issues/1)
- [Sound #1](https://github.com/Azrazieliz/Asterion-Sound/issues/1)

## Required device acceptance

1. Install an opted-in partner app with the proper provider. Discover it through the Control UI and native MCP.
2. Verify **unapproved invocation is rejected**.
3. Authorize locally and verify one non-destructive native partner operation completes with structured result.
4. Repeat the same request ID: **no second execution**.
5. Verify running, cancellation, failure, timeout, app update/signature change, lost connection, owner revocation.
6. Check unchanged project-specific engine, assets, signing, data, and performance.

**Do not report cross-app integration as fully working until these are observed on the real phone.**
