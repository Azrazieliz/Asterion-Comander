# Asterion Control 0.2.0 — Implementation report

| Capability | State |
|---|---|
| Standalone self-hosted FastAPI service | Implemented, API smoke-tested |
| Responsive PC + phone PWA | Implemented, desktop/mobile Chromium render checked |
| Bearer authentication / path restriction / MCP Origin checks | Implemented, tested |
| PC file CRUD, search, upload/download | Implemented, tested |
| PC subprocess shell and job output/stop | Implemented, tested on Linux runner |
| PC process and system metrics | Implemented, tested on Linux runner |
| Windows desktop capture and input | Implemented, mocked tests; Windows hardware not accessible |
| Multiple PC monitors / touchscreen coordinate conversion | Implemented; monitor offsets mocked in tests |
| Android device discovery and USB/Wi-Fi ADB connection | Implemented; fake ADB tested, actual device absent |
| Android screenshot and tap/swipe/keys/text | Implemented; fake ADB tested, actual device absent |
| Android UI XML, package enumeration, launcher, push/pull/install/shell | Implemented; actual device absent |
| REST API and MCP stdio + HTTP bridge | Implemented and protocol smoke-tested |
| Direct ChatGPT control from this conversation | **Not connected** — requires user-enabled compatible custom MCP connection/tunnel |
| Native Windows EXE, native Android APK/background agent | **Not built** |
| High-frame-rate video streaming / unattended system-level input | **Not built** |
| Windows PC/phone live end-to-end verification | **Blocked: user's connected laptop offline** |

Validation: **10 tests passed**, JS static syntax passed, responsive headless Chromium layout loaded without JS errors or horizontal overflow. These tests do not constitute Windows/Android hardware verification.


## 0.3.0 additions
- Hidden script library, direct bounded parallel execution, device-health endpoint, renamed UI.
- 14 local tests passed. No device or remote end-to-end tests. See PROGRESS.md.
