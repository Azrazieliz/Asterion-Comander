"""One-time owner-authorized ADB migration of the legacy Android signing identity.

No key bytes appear in shell arguments, logs, Git commits, or ChatGPT results.
Stores the original keystore with mode 0600 inside the current Samsung's
credential-encrypted app-private no_backup directory. Never deletes the PC
keystore; deletion requires CI signer and backup verification first.
ADB is only a bootstrap transport, not a normal Control runtime dependency.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys

EXPECTED = "SM-S948B"
PACKAGE = "com.asterion.control"
DESTINATION = "no_backup/asterion-original-android-signer.jks"
KEYSTORE = pathlib.Path.home() / ".android" / "debug.keystore"


def call(adb: str, args: list[str], data: bytes | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run([adb, *args], input=data, capture_output=True, timeout=50)
    if result.returncode:
        # Device output is not trusted, never echo arbitrary content.
        raise RuntimeError("Android signing backup operation failed")
    return result


def main() -> None:
    adb = shutil.which("adb")
    if adb is None or not KEYSTORE.is_file():
        raise RuntimeError("One-time authorized ADB or owner keystore unavailable")
    devices = call(adb, ["devices"]).stdout.decode("utf8", "replace").splitlines()[1:]
    online = [row.split()[0] for row in devices if len(row.split()) > 1 and row.split()[1] == "device"]
    if len(online) != 1:
        raise RuntimeError("Exactly one authorized Android device required")
    serial = online[0]
    model = call(adb, ["-s", serial, "shell", "getprop", "ro.product.model"]).stdout.decode().strip()
    if model != EXPECTED:
        raise RuntimeError("Connected Android device differs from the owner Samsung")
    data = KEYSTORE.read_bytes()
    if not 500 <= len(data) <= 100000:
        raise RuntimeError("Owner signing keystore invalid size")
    expected = hashlib.sha256(data).hexdigest()
    # 'adb shell' truncates streamed binary input on some Windows drivers.
    # Use the dedicated raw exec-in channel and prove it using harmless random
    # bytes before ever transferring the original signer.
    preflight = os.urandom(3072)
    test_dest = "no_backup/asterion-transfer-check.bin"
    try:
        call(adb, ["-s", serial, "exec-in", "run-as", PACKAGE,
                   "dd", "of=" + test_dest, "bs=4096"], preflight)
        check = call(adb, ["-s", serial, "shell", "-T", "run-as",
                          PACKAGE, "sha256sum", test_dest])
        observed = check.stdout.decode("utf8", "replace").split()
        if not observed or observed[0] != hashlib.sha256(preflight).hexdigest():
            raise RuntimeError("Binary-safe Android transfer failed preflight checksum")
    finally:
        subprocess.run([adb, "-s", serial, "shell", "-T", "run-as",
                        PACKAGE, "rm", "-f", test_dest],
                       capture_output=True, timeout=20, check=False)
    call(adb, ["-s", serial, "exec-in", "run-as", PACKAGE,
               "dd", "of=" + DESTINATION, "bs=4096"], data)
    call(adb, ["-s", serial, "shell", "-T", "run-as",
               PACKAGE, "chmod", "600", DESTINATION])
    verified = call(adb, ["-s", serial, "shell", "-T", "run-as",
                          PACKAGE, "sha256sum", DESTINATION])
    answer = verified.stdout.decode("utf8", "replace")
    digest = answer.split()[0] if answer.split() else ""
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or digest != expected:
        raise RuntimeError("Owner signer backup checksum mismatch; PC original preserved")
    print("OWNER_SIGNER_SAMSUNG_APP_PRIVATE_BACKUP_VERIFIED")
    print("Owner keystore bytes were not emitted; PC key remains until CI proof is accepted.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("SIGNER_PHONE_BACKUP_FAILED:", type(exc).__name__, str(exc)[:150])
        sys.exit(1)
