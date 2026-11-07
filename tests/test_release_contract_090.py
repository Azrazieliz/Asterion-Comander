"""Release gates for original-signer-compatible Asterion Control 0.9.0."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def text(path):
    return (ROOT/path).read_text(encoding="utf8")

def test_android_manifest_and_version_match_signed_update_contract():
    gradle=text("android/app/build.gradle")
    manager=text("android/app/src/main/java/com/asterion/control/UpdateManager.java")
    assert "versionCode 910" in gradle
    assert "versionName '0.9.10'" in gradle
    assert "ASTERION_OWNER_KEYSTORE_PATH" in gradle
    assert "canRequestPackageInstalls()" in manager
    assert "MessageDigest.isEqual" in manager

def test_chatgpt_controls_execution_and_android_returns_checkpoint_receipts():
    agent=text("android/app/src/main/java/com/asterion/control/AgentService.java")
    main=text("android/app/src/main/java/com/asterion/control/MainActivity.java")
    native=text("android/app/src/main/java/com/asterion/control/AndroidMcp.java")
    ledger=text("android/app/src/main/java/com/asterion/control/ContinuationLedger.java")
    assert "cycles.tick()" not in agent
    assert "ChatGPT checkpoint continuation" in main
    assert "control_phone_continuation_queue" in native
    assert "control_phone_continuation_dispatch" in native
    assert "control_phone_continuation_ack" in native
    assert "submitted_unverified" in ledger
    assert "response_receipt" in ledger

def test_phone_controls_remain_in_private_https_and_no_pc_required():
    agent=text("android/app/src/main/java/com/asterion/control/AgentService.java")
    phone=text("android/app/src/main/java/com/asterion/control/PhoneDirectMcp.java")
    transport=text("android/app/src/main/java/com/asterion/control/TransportConnectivity.java")
    gateway=text("asterion_remote/mcp_gateway.py")
    assert "PhoneDirectMcp.start(this)" in agent
    assert "phoneBridgePoller.scheduleWithFixedDelay" in agent
    assert "PhoneGitBridge.poll(this)" in agent
    assert "phoneBridgePoller.shutdownNow()" in agent
    assert "cycles.tick()" not in agent
    assert 'setEndpointIdentificationAlgorithm("HTTPS")' in phone
    assert "phone_live_invoke(message)" in gateway
    assert "phone_cloud_relay.submit" not in gateway
    for check in ("TRANSPORT_CELLULAR","TRANSPORT_VPN","https_outbound_only",
                  "requires_pc_for_phone_commands"):
        assert check in transport

def test_release_requires_exact_owner_signer_and_uses_existing_update_feed():
    workflow=text(".github/workflows/android-continuation-branch.yml")
    assert "Asterion-Control-v0.9.10-release.apk" in workflow
    assert "ASTERION_ANDROID_DEBUG_KEYSTORE_B64" in workflow
    assert "SIGNER_COMPATIBLE_WITH_V086_BASELINE=true" in workflow
    assert "dist/latest.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "workflow_dispatch:" in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "owner-signed APK release on explicit release commit or manual dispatch" in workflow
    assert ":app:assembleRelease" in workflow
    assert ":app:assembleDebug" not in workflow
    assert "app-release.apk" in workflow
    assert "application-debuggable" in workflow
    assert "dist/latest-release.json" in workflow
    assert "minifyEnabled true" in text("android/app/build.gradle")
    assert "debuggable false" in text("android/app/build.gradle")
    assert "signingConfigs.ownerRelease" in text("android/app/build.gradle")
    assert "latest-release.json" in text("android/app/src/main/java/com/asterion/control/UpdateManager.java")
    assert "Asterion-Control-v0.9.10-debug.apk" in workflow  # backwards-compatible alias only
    assert "cp \"$ROOT/dist/$PKG\" \"$ROOT/dist/Asterion-Control-v0.9.10-debug.apk\"" in workflow

def test_release_feed_version_code_matches_android_gradle():
    import re
    root=Path(__file__).resolve().parents[1]
    workflow=(root/".github/workflows/android-continuation-branch.yml").read_text()
    gradle=(root/"android/app/build.gradle").read_text()
    code=int(re.search(r"versionCode\s+(\d+)",gradle).group(1))
    feed=int(re.search(r'"version_code":(\d+)',workflow).group(1))
    assert feed==code, f"Updater feed code {feed} must match signed Android versionCode {code}"
