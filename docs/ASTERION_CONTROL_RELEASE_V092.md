# Asterion Control 0.9.2 — Local voice/cycle repair

This is an in-place, owner-certificate-signed, non-debuggable Android
release. Preserve existing application ID, data, and original signing identity.

**Voice:** A visible Android action runs a real local TextToSpeech spoken
question, then on-device microphone recognition and live result reporting.
A listener result, not a service-ready signal, is required for success.

**Cycles:** A visible phone action starts a bounded 2-turn ChatGPT continuation
test. The phone's own persistent cycle/Accessibility engine does the work.
No Windows agent is used for cycle scheduling or input. Each next turn
requires the previous assistant response-specific ACK, and DONE stops.

**Latency:** Phone-resident cycle scheduling now runs every two seconds
and the optional GitHub fallback checks every four seconds. A GitHub
round-trip, ChatGPT generation, or permission dialog cannot be guaranteed
to finish within five seconds. Do not claim otherwise.

**Remote cellular:** The GitHub fallback remains owner-enabled and
requires a repository-scoped token stored in Android Keystore. A published
personal plugin pointed to a temporary trycloudflare.com URL, which is
not a guaranteed persistent direct MCP endpoint. Offsite control is not
verified until the phone reports a successful independent command receipt.

**Acceptance:** CI compilation and signatures cannot substitute for a
successful audible question, actual microphone transcript, two ChatGPT
reply acknowledgments, and independent cellular relay receipt.
