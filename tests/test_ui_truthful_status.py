"""Regression checks: Control never turns a partial receipt into a false green status.

Source-level verification complements, not replaces, Android on-device UI
acceptance and actual delivery verification.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"android/app/src/main/java/com/asterion/control/MainActivity.java").read_text(encoding="utf-8")

def test_screen_not_labeled_streaming_without_fresh_frames():
    assert 'captureConnection.setText(!CaptureService.active?"Off":fresh?' in MAIN
    assert '"Fresh frames on phone"' in MAIN
    assert '"Capture active · frames stale"' in MAIN
    assert 'captureConnection.setText(CaptureService.active?"Streaming":"Off")' not in MAIN

def test_phone_service_not_labeled_full_remote_connection():
    assert '"Phone listener active · Windows link checked separately"' in MAIN
    assert '"Phone agent starting · listener unverified"' in MAIN
    assert '"LOCAL CAPTURE LIVE"' in MAIN
    assert 'headerStatus.setText(AgentService.running?"SHARING ON"' not in MAIN

def test_private_relay_recent_receipts_not_historical_connected_claim():
    assert '"Enabled · historical success only"' in MAIN
    assert '"Recently active · live connection not guaranteed"' in MAIN
    assert '"Connected to private queue"' not in MAIN

def test_pairing_and_transfer_do_not_promise_unverified_delivery():
    assert '"Windows paired; checking device registration"' in MAIN
    assert '"Phone registration accepted by Windows · testing live reachability"' in MAIN
    assert '"Transfer request accepted · awaiting first progress · "' in MAIN
    assert 'Reported SHA-256: ' in MAIN
    assert '"Windows reported transfer completion without an independently checkable phone receipt"' in MAIN
    assert '"Saved to "+receipt.optString("location")' not in MAIN

def test_checkpoint_open_preserves_existing_chat():
    checkpoint=MAIN.split("private void openChatGptCheckpoint(){",1)[1].split("private void showBatterySetup(){",1)[0]
    assert "access.requestChatForeground()" in checkpoint
    assert "getLaunchIntentForPackage" not in checkpoint
    assert "startActivity(launch)" not in checkpoint

def test_static_success_claims_removed():
    assert "The app teams have been asked to add it" not in MAIN
    assert 'healthActionStatus=t("Automatic management is active"' not in MAIN
    assert 'Action performance targets (not verified measurements): ' in MAIN
    assert '"Current turn number: "' in MAIN
