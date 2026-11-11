"""Start one owner-authorized, short 2-turn REAL ChatGPT UI cycle.

NO model call or faux receipt. Android Control sends actual prompts into the
real ChatGPT composer and awaits matching visible reply ACK/DONE tokens.
This is a test-only exception to the 30-minute substantive-turn target.
"""
import json,os,time
from pathlib import Path
import httpx
state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
host=(state/"agent-host.txt").read_text(encoding="utf-8").strip()
token=(state/"control-token.txt").read_text(encoding="utf-8").strip()
cycle_id="control-abridged-appswitch-20261111"
headers={"Authorization":"Bearer "+token}
c=httpx.Client(base_url=host,headers=headers,timeout=6,trust_env=False)
cycle=c.get("/api/v1/phone/cycles/status").json().get("cycle",{})
if cycle.get("active"):raise SystemExit("ACTIVE_CYCLE_EXISTS_NO_NEW_START")
ledger=c.get("/api/v1/phone/continuation/status").json()
if ledger.get("state") not in ("cancelled","acknowledged","idle","failed"):
    raise SystemExit("UNSAFE_OLD_CHECKPOINT_"+str(ledger.get("state")))
ui=c.get("/api/v1/phone/ui").json()
if ui.get("foreground_package")!="com.openai.chatgpt":
    raise SystemExit("CHATGPT_NOT_FOREGROUND")
keyboard=ui.get("keyboard",{})
if not keyboard.get("active") or keyboard.get("editor_package")!="com.openai.chatgpt" or keyboard.get("draft_empty") is not True:
    raise SystemExit("CHATGPT_COMPOSER_NOT_PROVEN_EMPTY")
message=(
  "OWNER-APPROVED BRIEF CYCLE ACCEPTANCE, two turns ONLY. The owner expressly "
  "authorizes abbreviated turns for this test instead of the normal 25–30-minute "
  "production development turns. No filler. Test real operation, not a simulated cycle. "
  "In the FIRST turn, use existing Asterion Control Windows/Android worker tools to "
  "leave ChatGPT, open the Asterion Control app via Android Recents/launcher, confirm "
  "live phone frame capture, and RETURN TO CHATGPT using Control's foreground "
  "application launcher. If capture is OFF, use the visible Start screen sharing "
  "control and actual Android system prompt; never bypass Android consent. "
  "Record measured tool receipts in a real canonical progress log, identify any "
  "defect, and conclude with your exact checkpoint ACK marker. "
  "In the SECOND turn, inspect the phone's cycle state and prior real receipts, "
  "verify two-turn continuation without duplicate sends, update the canonical "
  "test report, and only issue the DONE marker when the two-step acceptance "
  "has truly passed. If not, ACK with a precise blocker, never fake completion. "
  "Use source branch work/control-0927-overnight-cycles-20261111 and current "
  "published Asterion Control v0.9.28. The ordinary unlimited overnight cycle "
  "requirements are NOT changed by this short test."
)
body={"cycle_id":cycle_id,"project":"Asterion-Control",
      "spec_reference":"docs/CYCLE_EXECUTION_CONTRACT.md",
      "priority_tier":"7*","conversation":"same",
      "max_cycles":2,"voice_locale":"en-US","message":message}
r=c.post("/api/v1/phone/cycles/start",json=body);r.raise_for_status()
initial=r.json()
print(json.dumps({"test":"real-android-chatgpt-two-turn",
                  "cycle_id":cycle_id,
                  "start_state":initial.get("state"),
                  "active":initial.get("active"),
                  "max_cycles":initial.get("max_cycles"),
                  "current_chat":ui.get("foreground_package"),
                  "keyboard_empty":keyboard.get("draft_empty")},separators=(",",":")))
# Observe the first dispatch read-only, without stimulating duplicate sends.
for _ in range(12):
    time.sleep(1)
    state=c.get("/api/v1/phone/cycles/status").json().get("cycle",{})
    ledger=c.get("/api/v1/phone/continuation/status").json()
    if ledger.get("state") in ("submitted_unverified","requires_manual_review","acknowledged"):
        print(json.dumps({"cycle_state":state.get("state"),
          "checkpoint":state.get("checkpoint"),
          "ledger_state":ledger.get("state"),
          "submission_attempts":ledger.get("attempt_count"),
          "last_error":ledger.get("last_error")},separators=(",",":")))
        break
else:
    print(json.dumps({"phase":"awaiting_real_composer",
      "cycle_state":state.get("state"),
      "ledger_state":ledger.get("state"),
      "last_error":ledger.get("last_error")},separators=(",",":")))
