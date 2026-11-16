"""Phone-head source contract. A server-side status is not a phone model."""
from pathlib import Path
import re, unittest

ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"android/app/src/main/java/com/asterion/control/MainActivity.java").read_text("utf8")
LOCAL=(ROOT/"android/app/src/main/java/com/asterion/control/OnDeviceLlm.java").read_text("utf8")
NATIVE=(ROOT/"android/app/src/main/cpp/on_device_llm.cpp").read_text("utf8")
CMAKE=(ROOT/"android/app/src/main/cpp/CMakeLists.txt").read_text("utf8")
GRADLE=(ROOT/"android/app/build.gradle").read_text("utf8")

class PhoneHeadTests(unittest.TestCase):
    def test_model_runs_only_in_phone(self):
        self.assertIn('OnDeviceLlm.generate(getApplicationContext(),prompt)',MAIN)
        self.assertIn("System.loadLibrary(\"asterion_llm\")",LOCAL)
        self.assertIn('nativeGenerate(prompt,192)',LOCAL)
        self.assertIn("llama_model_load_from_file",NATIVE)
        self.assertIn("llama_process",NATIVE)
        self.assertIn("LLAMA_SOURCE_DIR",CMAKE)
        self.assertIn("MODEL_BYTES=484220288L",LOCAL)
        self.assertIn("MODEL_SHA256=",LOCAL)
        self.assertIn("373db06783953f0981572d008f183eb2167b93304f5adbf7c4ce6ed6a91ee437",LOCAL)
        self.assertIn("external_server_required",LOCAL)
        self.assertIn('"paid_cloud_api_required",false',LOCAL)
        self.assertNotIn('http://',LOCAL)
        self.assertNotIn('https://',LOCAL)
        self.assertIn("androidResources { noCompress += ['gguf'] }",GRADLE)
    def test_native_diagnostics_do_not_require_windows(self):
        block=MAIN.split("private void showCrossAppDiagnostics()",1)[1].split(
           "private void showPermissionDetails()",1)[0]
        self.assertIn("AppBridge.list(this)",block)
        self.assertIn("AppCatalog.launchable(this)",block)
        self.assertIn("showAppIntegrationActions(pkg,installed.get(pkg)",block)
        self.assertNotIn('prefs.getString("url"',block)
        self.assertNotIn('prefs.getString("token"',block)
        self.assertIn('showRemoteSection("diagnostics")',block)
    def test_real_model_hard_release_gate(self):
        build=(ROOT/"scripts/build_owner_signed_control_0935.ps1").read_text("utf8")
        for required in ("actual bundled GGUF is missing","actual bundled GGUF SHA mismatch",
                         "native inference library not compiled"):
            self.assertIn(required,build)
        self.assertIn("versionCode 935",GRADLE)
        self.assertIn("versionName '0.9.35'",GRADLE)
    def test_new_native_ui_choices_visible(self):
        app=MAIN.split("private void showAppIntegrationActions(",1)[1].split(
            "private void showPartnerEvidence(",1)[0]
        part=app.split(".setItems(actions,",1)[0].split(
            "new AlertDialog.Builder(this)")[-1]
        self.assertNotIn(".setMessage(",part)
        permissions=MAIN.split("private void showPermissionsHub()",1)[1].split(
            "private void openPermissionStep(",1)[0]
        chooser=permissions.split(".setItems(rows,",1)[0].split(
            "new AlertDialog.Builder(this)")[-1]
        self.assertNotIn(".setMessage(",chooser)

if __name__ == "__main__":
    unittest.main()
