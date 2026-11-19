"""Regression locks for the *original* native WSS-only owner relay recovery.

These tests validate preservation contracts; physical recovery still requires
independent same-signer Windows/phone execution and an authenticated RPC receipt.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHDOG = (ROOT / "scripts/control_repair_watchdog.ps1").read_text("utf8")
RELOAD = (ROOT / "scripts/reload_native_wss_after_idle_20261119.ps1").read_text("utf8")


def test_wss_health_cannot_hide_an_old_rpc_route():
    assert "$nativeRelayOk" in WATCHDOG
    assert "http://127.0.0.1:8995/phone/rpc" in WATCHDOG
    assert "if($rpcStatus -eq 404)" in WATCHDOG
    assert "reload_native_wss_after_idle_20261119.ps1" in WATCHDOG
    assert "TotalMinutes -ge 10" in WATCHDOG
    assert "$already.Count -eq 0" in WATCHDOG
    assert "v6-native-route-recovery-attempt.txt" in WATCHDOG


def test_recovery_script_refuses_wrong_process_and_busy_jobs():
    assert "Get-NetTCPConnection -LocalPort 8995" in RELOAD
    assert "asterion_remote\\.native_phone_relay:app" in RELOAD
    assert "Original watchdog disabled" in RELOAD
    assert "Where-Object{$_.status -eq 'running'}" in RELOAD
    assert "deferred_busy" in RELOAD
    assert "if(-not $Apply)" in RELOAD
    assert "roundtrip_verified" in RELOAD
    assert "cellular_verified" in RELOAD
    assert "phone-pairing.json" in RELOAD


def test_existing_pairing_and_gateway_retirement_are_preserved():
    for source in (WATCHDOG, RELOAD):
        for forbidden in ("adb shell", "Remove-Item $state",
                          "Remove-Item $key", "mcp_gateway:app",
                          "oauth_bridge:app", "New-SelfSignedCertificate"):
            assert forbidden not in source
    assert "Stop-Process -Id $pidBefore" in RELOAD
    assert "asterion_remote.native_phone_relay:app" in RELOAD
