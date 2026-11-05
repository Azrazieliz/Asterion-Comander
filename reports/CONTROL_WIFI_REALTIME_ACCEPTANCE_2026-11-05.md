# Asterion Control — native Wi-Fi real-time acceptance (2026-11-05)

## Test boundary
- Android Samsung SM-S948B, Android 17, Asterion Control native v0.8.3 installed.
- Android is the primary authorized controller; Windows is a subordinate worker on private LAN.
- Tests used **Asterion Control's native agent** and authenticated WebSocket/HTTP/MCP endpoints.
- ADB was used only in earlier installation/agent-bootstrap operations, **not for the below device-control acceptance**.
- The private GitHub bridge dispatched the benchmark script but was **not on the native WebSocket or direct HTTPS MCP data path**.
- The phone reported `charging:false` during wireless-condition health checks; this is consistent with unplugging but is not a measurement of USB data enumeration.

## Six repeated native health probes
| Metric | Observation |
|---|---|
| Paired and reachable | 6/6 |
| Accessibility | 6/6 enabled |
| MediaProjection capture | 6/6 active |
| Windows-to-native-phone probe handling time | 45–119 ms; median 79 ms |
| Android battery charging state | false for every probe |
| Native screenshot after probes | 111,351-byte JPEG; 149 ms agent-side |
| Accessibility hierarchy | Available, FrameLayout root; 199 ms |

## Initial full-duplex stream test
- 35 JPEG frames over 2.47 s, 9 distinct frame payloads.
- Delivered 13.7 FPS (18 FPS requested), 70.9 ms median frame interval, 101.2 ms p95.
- First frame 543.9 ms.
- Harmless Android HOME input acknowledged successfully; 17.9 ms end-to-end socket round trip, 17.2 ms device action time.
- No stream errors.

## Continuous 90-second live video and input soak
Source: `scripts/measure_live_control_soak.py`. Existing native route `ws://192.168.1.133:8911/api/v1/stream/phone`.

| Metric | Result |
|---|---|
| Duration | 90.01 s |
| Frame rate requested | 18 FPS |
| Frames received | 1,168 |
| Frame rate delivered | 13.0 FPS |
| Frames per successive 22.5 s block | 291 / 280 / 295 / 302 |
| Distinct JPEG frame payloads | 52 |
| Time to first frame | 221.6 ms |
| Frame interval min / median | 43.4 / 73.1 ms |
| Frame interval p95 / p99 / max | 101.7 / 137.2 / 865.3 ms |
| Median JPEG frame size | 216.2 KB |
| HOME acknowledgement RTT / device time | 18.8 / 18.1 ms, success |
| Swipe acknowledgement RTT / device time | 638.9 / 637.6 ms, success (requested gesture itself 400 ms) |
| Streaming / input errors | 0 |

Both actions were sent over the *same* authenticated WebSocket as the live frames. The swipe includes gesture execution time and is not a raw command-transport latency metric. Distinct frames are low because the scene may be static; delivered frame count measures transport, not visual change rate.

During the soak, a separate native Control health request reported paired/reachable/accessibility/capture all true, battery 93%, temperature 30.7 C, charging false, thermal status 0; UI hierarchy also remained available.

## Direct authenticated MCP HTTP under simultaneous stream load
Source: `scripts/measure_direct_control.py`. 12 trials per route, `control_phone_status` method, no GitHub polling in measured path.

| Route | Success | Median | p95 | Min–max |
|---|---|---|---|---|
| Direct Windows-local MCP gateway | 12/12 | 70.8 ms | 101.2 ms | 56.4–105.7 ms |
| Direct Cloudflare HTTPS MCP gateway | 12/12 | 173.3 ms | 214.9 ms | 145.1–250.6 ms |

These **do not include ChatGPT model deliberation or tool-loading latency**, and are not proof that direct MCP tools have been enabled in the ChatGPT app. The Cloudflare Quick Tunnel hostname is temporary.

## Acceptance verdict
**PASS (current native Wi-Fi control):** paired agent, health, screen capture, UI hierarchy, short HOME and swipe actions, full-duplex stream, concurrent HTTPS MCP gateway.

**NOT AT 18 FPS TARGET:** Delivered 13 FPS over 90 s. Median frame interval 73.1 ms with one 865.3 ms spike. Additional capture/stream optimization required before claiming stable 18+ FPS or jitter-free operation.

**UNVERIFIED:** 30+ minute screen-off/Doze/device-idle reliability; reconnection after network changes; a stable production HTTPS endpoint; ChatGPT-native direct plugin tool availability and complete cloud-to-phone latency. The plugin skill and hosted MCP reachability are different from an authenticated ChatGPT connector.

**Operational rule:** Do not use ADB or Desktop Commander to claim acceptance; keep GitHub only as fallback/source-control, and distinguish native transport from remote tool orchestration.
