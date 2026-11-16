"""Owner-requested Android authorizations and one-tap installed-app onboarding.

Source contract supplements a real Java compilation and Samsung acceptance;
no test pretends to grant Android permissions or install partner components.
"""
from pathlib import Path
import unittest

JAVA = (Path(__file__).resolve().parents[1]/
    "android/app/src/main/java/com/asterion/control/MainActivity.java")


class OwnerOnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=JAVA.read_text("utf8")

    def test_home_has_direct_routes_without_duplicated_web_tabs(self):
        s=self.source
        for direct in (
            '"Add app","devices",this::showAppBridgeApprovals',
            '"Diagnose","activity",this::showCrossAppDiagnostics',
            '"Permissions","shield",this::showPermissionsHub',
            '"Tools","settings",()->show(4)',
        ):
            self.assertIn(direct,s)
        self.assertIn('showRemoteSection("diagnostics")',s)

    def test_installed_apps_are_searchable_and_tappable(self):
        s=self.source
        for required in ("AppCatalog.launchable(this)","new ListView(this)",
            "search.addTextChangedListener(", "list.setOnItemClickListener(",
            "showAppIntegrationActions(pkg,label,provider,approved)",
            '"tracked_apps_v1"', "markTrackedApp(",
            '"Add to my Control apps"', "this::showMyAddedApps",
            "AppBridge.approveLocally(this,pkg,!approved)"):
            self.assertIn(required,s)
        self.assertIn("No Asterion native bridge provided",s)
        self.assertIn("cannot be remotely controlled or diagnosed automatically",s)
        self.assertIn("requires local approval",s.lower())

    def test_app_launch_and_system_settings_are_real_actions(self):
        s=self.source
        self.assertIn("AppCatalog.requestLaunch(this,pkg)",s)
        self.assertIn("Settings.ACTION_APPLICATION_DETAILS_SETTINGS",s)
        self.assertIn("Uri.parse(\"package:\"+pkg)",s)

    def test_all_permission_paths_are_real_and_no_silent_voice(self):
        s=self.source
        permissions=s.split("private void showPermissionsHub()",1)[1].split(
            "private void showVpnDetails()",1)[0]
        for label in ("Remote touch", "Screen sharing", "Notifications",
                      "Microphone", "Usage access", "Battery restrictions",
                      "Install APK updates", "WireGuard VPN", "Developer options"):
            self.assertIn(label,permissions)
        for route in ("Settings.ACTION_ACCESSIBILITY_SETTINGS",
                      "Settings.ACTION_USAGE_ACCESS_SETTINGS",
                      "Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES",
                      "Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS"):
            self.assertIn(route,permissions)
        self.assertIn("openOwnAppSettings();break;",permissions)
        self.assertIn("Settings.ACTION_APPLICATION_DETAILS_SETTINGS",s)
        self.assertIn("HUB_MICROPHONE_REQUEST",permissions)
        self.assertIn("HUB_NOTIFICATION_REQUEST",permissions)
        self.assertIn("if(request==HUB_MICROPHONE_REQUEST||request==HUB_NOTIFICATION_REQUEST)",s)
        no_automatic=s.split(
            "if(request==HUB_MICROPHONE_REQUEST||request==HUB_NOTIFICATION_REQUEST)",1
            )[1].split("return;",1)[0]
        self.assertNotIn("startVoiceQuestions()",no_automatic)
        self.assertNotIn("startAgent()",no_automatic)

    def test_crash_reasons_explained_and_old_dialog_removed(self):
        s=self.source
        self.assertIn('"Java crash"',s)
        self.assertIn('"Native-code crash"',s)
        self.assertIn('"App not responding (ANR)"',s)
        self.assertIn('"Owner requested exit"',s)
        self.assertNotIn("Recorded in last 24 hours: ",s)
        self.assertNotIn('reason_code","unknown"',s)


if __name__ == "__main__":
    unittest.main()
