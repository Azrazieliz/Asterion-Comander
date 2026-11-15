"""Automatic owner-scoped scanning with actual reversible quarantine receipts."""
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from asterion_remote import security_guardian,security_scanner


class GuardianTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.root=self.base/"authorized-downloads"
        self.root.mkdir()
        self.state=self.base/"guardian-state"
        self.env=patch.dict(os.environ,{
            "ASTERION_SECURITY_GUARDIAN_ENABLED":"1",
            "ASTERION_SECURITY_WATCH_ROOTS":str(self.root),
            "ASTERION_SECURITY_GUARDIAN_STATE":str(self.state)
        })
        self.env.start()
        from asterion_remote import app
        self.allowed=patch.object(app,"ROOT",self.root)
        self.allowed_extra=patch.object(app,"EXTRA_ROOTS",[])
        self.allowed.start()
        self.allowed_extra.start()

    def tearDown(self):
        security_guardian.stop()
        self.allowed_extra.stop()
        self.allowed.stop()
        self.env.stop()
        self.tmp.cleanup()

    def add(self,name="notes.txt",data=b"User document"):
        file=self.root/name
        file.write_bytes(data)
        old=time.time()-15
        os.utime(file,(old,old))
        return file

    def test_no_scan_when_disabled(self):
        self.add()
        with patch.dict(os.environ,{"ASTERION_SECURITY_GUARDIAN_ENABLED":"0"}):
            self.assertFalse(security_guardian.status()["enabled"])
            with self.assertRaises(RuntimeError):
                security_guardian.scan_once()
            self.assertFalse(security_guardian.start()["worker_running"])

    def test_first_scan_and_recheck_dedup_without_file_mutation(self):
        file=self.add()
        first=security_guardian.scan_once()
        self.assertEqual(first["files_inspected"],1)
        self.assertEqual(first["auto_quarantined"],0)
        self.assertTrue(file.exists())
        # Without ClamAV, engine must not claim comprehensive safety.
        self.assertFalse(first["full_antivirus_guarantee"])
        second=security_guardian.scan_once()
        self.assertEqual(second["files_inspected"],0)
        self.assertGreaterEqual(second["unchanged_or_incomplete_files_skipped"],1)

    def test_signature_confirmed_malware_is_quarantined_reversibly(self):
        file=self.add("blocked.exe",b"MZ"+b"a"*1024)
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        real=security_scanner.quarantine
        with patch.object(security_scanner,"scan",return_value={
            "ok":True,"verdict":"malicious","file_sha256":digest,
            "antivirus":"malware_detected","findings":["antivirus_signature_match"]
        }):
            result=security_guardian.scan_once()
        self.assertEqual(result["auto_quarantined"],1)
        self.assertFalse(file.exists())
        entries=security_scanner.inventory(self.state)
        self.assertEqual(entries["count"],1)
        back=security_scanner.restore(entries["items"][0]["id"],self.state)
        self.assertEqual(back["state"],"restored")
        self.assertTrue(file.exists())
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),digest)

    def test_heuristic_suspicion_requires_review_not_auto_delete(self):
        file=self.add("suspect.apk",b"PK"+b"other")
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        with patch.object(security_scanner,"scan",return_value={
            "ok":True,"verdict":"suspicious","file_sha256":digest,
            "antivirus":"not_available",
            "findings":["archive_contains_executable"]}):
            status=security_guardian.scan_once()
        self.assertEqual(status["owner_review_needed"],1)
        self.assertEqual(status["auto_quarantined"],0)
        self.assertTrue(file.exists())

    def test_unstable_file_waits_until_complete(self):
        file=self.root/"unfinished.bin"
        file.write_bytes(b"still downloading")
        with patch.object(security_scanner,"scan") as scanner:
            out=security_guardian.scan_once()
        self.assertEqual(out["files_inspected"],0)
        scanner.assert_not_called()

    def test_root_outside_existing_control_permissions_forbidden(self):
        from asterion_remote import app
        with patch.object(app,"ROOT",self.base/"unrelated"):
            with self.assertRaises(PermissionError):
                security_guardian.scan_once()

    def test_symlink_file_not_scanned(self):
        outside=self.base/"private"
        outside.write_bytes(b"secret")
        link=self.root/"link.exe"
        try:link.symlink_to(outside)
        except (OSError,NotImplementedError):
            self.skipTest("OS policy disallows creating symlink")
        with patch.object(security_scanner,"scan") as scanner:
            outcome=security_guardian.scan_once()
        self.assertEqual(outcome["files_inspected"],0)
        scanner.assert_not_called()


if __name__=="__main__":
    unittest.main()
