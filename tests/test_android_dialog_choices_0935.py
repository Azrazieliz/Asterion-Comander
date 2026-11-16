"""The owner must actually see native action rows, not a message-only dialog.

On Android, AlertDialog.Builder.setMessage() and setItems() compete for the
same content panel; the former hid app approvals and permission shortcuts.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=(ROOT/"android/app/src/main/java/com/asterion/control/MainActivity.java")

class VisibleNativeChoices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s=JAVA.read_text("utf8")
        cls.app=s.split("private void showAppIntegrationActions(",1)[1].split(
            "private void showPartnerEvidence(",1)[0]
        cls.permissions=s.split("private void showPermissionsHub()",1)[1].split(
            "private void openPermissionStep(",1)[0]

    def test_app_approval_rows_are_not_replaced_by_message(self):
        first=self.app.split(".setItems(actions,",1)[0].split(
            "new AlertDialog.Builder(this)")[-1]
        self.assertNotIn(".setMessage(",first)
        self.assertIn(".setTitle(",first)
        self.assertIn("Authorize native bridge",self.app)
        self.assertIn("AppBridge.approveLocally(this,pkg,!approved)",self.app)
        self.assertIn(".setItems(actions,",self.app)

    def test_permission_items_are_displayed_not_hidden(self):
        first=self.permissions.split(".setItems(rows,",1)[0].split(
            "new AlertDialog.Builder(this)")[-1]
        self.assertNotIn(".setMessage(",first)
        self.assertIn("Permissions",first)
        self.assertIn(".setItems(rows,(dlg,item)->openPermissionStep(item))",self.permissions)
        for expected in ("Remote touch","Screen sharing","Microphone",
                         "Usage access","Install APK updates","WireGuard VPN"):
            self.assertIn(expected,self.permissions)

    def test_approval_confirmation_remains_owner_local(self):
        self.assertIn("if(!bridge)",self.app)
        self.assertIn("AppBridge.approveLocally(this,pkg,!approved)",self.app)
        self.assertIn("Authorize native bridge",self.app)
        self.assertIn("Android app settings",self.app)

if __name__=="__main__":
    unittest.main()
