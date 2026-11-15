"""Real bytes, no code execution: inspect external APK, DEX, PE and ELF."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from asterion_remote import reverse_lab as lab


def dex_bytes():
    data=bytearray(112)
    data[:8]=b"dex\n035\0"
    struct.pack_into("<III",data,32,112,112,0x12345678)
    for p,n in [(56,12),(64,10),(72,5),(80,7),(88,6),(96,3)]:
        struct.pack_into("<I",data,p,n)
    return bytes(data)


class ReverseLabTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()

    def file(self,name,content):
        dest=self.root/name
        dest.write_bytes(content)
        return dest

    def test_pe_binary_real_structure_without_running_it(self):
        image=bytearray(512)
        image[:2]=b"MZ"
        struct.pack_into("<I",image,0x3c,128)
        image[128:132]=b"PE\0\0"
        struct.pack_into("<HHIIIHH",image,132,
                         0x8664,4,123456,0,0,240,0x0022)
        struct.pack_into("<H",image,152,0x20b)
        path=self.file("app.exe",image)
        original=path.read_bytes()
        outcome=lab.inspect(path)
        self.assertTrue(outcome["ok"])
        self.assertEqual(outcome["format"]["architecture"],"x86_64")
        self.assertEqual(outcome["format"]["sections"],4)
        self.assertEqual(outcome["format"]["format"],"PE32+")
        self.assertEqual(path.read_bytes(),original)
        self.assertFalse(outcome["full_source_decompiled"])
        self.assertEqual(outcome["sha256"],hashlib.sha256(original).hexdigest())

    def test_elf_binary_real_structure(self):
        image=bytearray(64)
        image[:6]=b"\x7fELF\x02\x01"
        struct.pack_into("<HH",image,16,3,183)
        out=lab.inspect(self.file("library.so",image))
        self.assertEqual(out["format"]["type"],"elf")
        self.assertEqual(out["format"]["bitness"],64)
        self.assertEqual(out["format"]["architecture"],"aarch64")

    def test_dex_binary_real_table_counts(self):
        out=lab.inspect(self.file("classes.dex",dex_bytes()))
        self.assertEqual(out["format"]["method_ids"],6)
        self.assertEqual(out["format"]["class_definitions"],3)
        self.assertEqual(out["format"]["dex_version"],"035")

    def test_external_apk_has_real_manifest_and_dex(self):
        path=self.root/"third-party.apk"
        with zipfile.ZipFile(path,"w") as z:
            z.writestr("AndroidManifest.xml",b"\x03\x00binaryxml")
            z.writestr("classes.dex",dex_bytes())
            z.writestr("META-INF/CERT.RSA",b"signature")
        out=lab.inspect(path)
        self.assertEqual(out["format"]["type"],"android_apk")
        self.assertEqual(out["format"]["android_dex"][0]["method_ids"],6)
        self.assertTrue(out["format"]["v1_certificate_container_present"])
        self.assertFalse(out["format"]["apk_signing_fully_verified"])
        self.assertFalse(out["input_file_modified"])

    def test_large_archive_requires_bounded_inspection(self):
        path=self.root/"many.zip"
        with zipfile.ZipFile(path,"w") as z:
            for i in range(lab._MAX_ARCHIVE+1):
                z.writestr(str(i)+".txt","")
        with self.assertRaises(ValueError):
            lab.inspect(path)

    def test_broken_dex_or_apk_not_fabricated(self):
        bad=self.file("broken.dex",b"dex\n035\0"+b"\0"*105)
        with self.assertRaises(ValueError):
            lab.inspect(bad)
        path=self.root/"wrong.apk"
        with zipfile.ZipFile(path,"w") as z:z.writestr("bad.txt","no manifest")
        with self.assertRaises(ValueError):
            lab.inspect(path)

    def test_unsupported_bytes_produce_honest_report(self):
        out=lab.inspect(self.file("unknown.bin",b"opaque binary content"))
        self.assertEqual(out["format"]["type"],"unrecognized")
        self.assertFalse(out["full_source_decompiled"])

    def test_inspection_never_claims_dynamic_instrumentation(self):
        out=lab.inspect(self.file("new.elf",b"\x7fELF\x02\x01"+
              b"\0"*10+struct.pack("<HH",3,62)+b"\0"*44))
        self.assertTrue(out["static_analysis_only"])
        self.assertFalse(out["live_process_instrumented"])
        self.assertFalse(out["source_path_disclosed"])


if __name__=="__main__":
    unittest.main()
