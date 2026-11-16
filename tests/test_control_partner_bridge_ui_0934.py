"""Regression: partner UI actions are real, owner-gated, and never fake engine health.

The generic Accessibility control fallback must remain usable without a bridge.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/"android/app/src/main/java/com/asterion/control/MainActivity.java"
BRIDGE=ROOT/"android/app/src/main/java/com/asterion/control/AppBridge.java"

class PartnerOwnerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main=MAIN.read_text("utf8")
        cls.bridge=BRIDGE.read_text("utf8")

    def test_owner_can_get_actual_bridge_evidence(self):
        s=self.main
        self.assertIn('private void showPartnerEvidence(',s)
        self.assertIn('AppBridge.invoke(this,request)',s)
        self.assertIn('"diagnostics.summary"',s)
        self.assertIn('"models.status"',s)
        self.assertIn('process_pss_kb',s)
        self.assertIn('android_historical_exits',s)
        self.assertIn('installed_gguf_count',s)
        self.assertIn('engine_telemetry_available',s)
        self.assertIn('Control has not loaded or',s)
        self.assertIn('No result is fabricated',s)

    def test_bridge_requires_local_owner_approval_and_signer_pinning(self):
        s=self.bridge
        self.assertIn('MainActivity.foregroundActivity()==null',s)
        self.assertIn('"approved:"+pkg',s)
        self.assertIn('signer(ctx,pkg)',s)
        self.assertIn('request_id_collision',s)
        self.assertIn('outcome_unknown',s)
        self.assertIn('AppBridge.invoke', self.main)

    def test_plain_ui_control_does_not_require_native_provider(self):
        s=self.main
        self.assertIn('generic Accessibility control',s)
        self.assertIn('without a native bridge',s)
        self.assertIn('AppCatalog.requestLaunch(this,pkg)',s)
        self.assertIn('this::showAppBridgeApprovals',s)

    def test_free_vpn_setup_is_explicit_and_nonautomatic(self):
        s=self.main
        snippet=s.split('private void showFreeVpnConfigSetup()',1)[1].split(
            'private void showVpnImportType()',1)[0]
        self.assertIn('https://account.protonvpn.com',snippet)
        self.assertIn('Import WireGuard profile',snippet)
        self.assertIn('Android must separately approve the VPN',snippet)
        self.assertNotIn('ControlPrivateVpn.connect(',snippet)
        self.assertNotIn('ControlPrivateVpn.importLocally(',snippet)


if __name__=="__main__":unittest.main()
