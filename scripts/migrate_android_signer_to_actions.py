"""One-time migration of the original Android debug signing identity to GitHub Actions.

Runs ONLY on the authorized owner's Windows PC. The original keystore and
Git credential remain in local process memory, never printed, committed or
included in the result receipt. GitHub receives only its own public-key sealed
encrypted Actions secret. No local key is deleted until a verified CI replacement
and a separate backup exist; other Android apps may share this signing identity.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "Azrazieliz/Asterion-Comander"
SECRET_NAME = "ASTERION_ANDROID_DEBUG_KEYSTORE_B64"
EXPECTED_CERT = "9bc439712a0a460cc4703ebf254aaaf9bf3cc6e67b0ced6fc12162ed3ca3b9ad"
API = f"https://api.github.com/repos/{REPO}/actions/secrets/"
KEYSTORE = pathlib.Path.home() / ".android" / "debug.keystore"
RECEIPT = pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) / "AsterionControl" / "ci-signer-provisioned.json"


def verify_original_cert() -> None:
    java = pathlib.Path(os.environ.get("JAVA_HOME", r"C:\Program Files\Android\Android Studio\jbr"))
    keytool = java / "bin" / "keytool.exe"
    if not keytool.exists():
        raise RuntimeError("Owner keytool unavailable")
    result = subprocess.run([
        str(keytool), "-list", "-keystore", str(KEYSTORE),
        "-storepass", "android", "-alias", "androiddebugkey",
    ], text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError("Owner signing identity unreadable")
    match = re.search(r"SHA-256\):\s*([A-Fa-f0-9:]{64,100})",
                      result.stdout + result.stderr)
    if not match:
        raise RuntimeError("Cannot verify original owner signer")
    actual = match.group(1).replace(":", "").lower()
    if actual != EXPECTED_CERT:
        raise RuntimeError("Owner signing identity differs from existing installed apps")


def github_credential() -> str:
    process = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n", text=True,
        capture_output=True, timeout=20, check=False,
    )
    if process.returncode:
        raise RuntimeError("Existing GitHub authorization unavailable")
    # Never log either the username or the sensitive credential.
    items = dict(line.split("=", 1) for line in process.stdout.splitlines() if "=" in line)
    token = items.get("password", "")
    if len(token) < 20:
        raise RuntimeError("Existing GitHub authorization unavailable")
    return token


def github_request(method: str, url: str, token: str, payload: dict | None = None):
    if not url.startswith(API):
        raise RuntimeError("Non-canonical GitHub secrets target refused")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Asterion-Control-OwnerSignerMigration",
    }
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            output = response.read(8192)
            return response.status, json.loads(output) if output else {}
    except urllib.error.HTTPError as exc:
        # The remote response might echo sensitive data; never print it.
        raise RuntimeError(f"GitHub secrets endpoint denied HTTP {exc.code}") from None


def migrate() -> None:
    if not KEYSTORE.is_file() or KEYSTORE.stat().st_size > 1_000_000:
        raise RuntimeError("Original Android signing keystore missing or oversized")
    verify_original_cert()
    try:
        from nacl.public import PublicKey, SealedBox
    except ImportError as exc:
        raise RuntimeError("PyNaCl not installed in native Control Python environment") from exc
    token = github_credential()
    status, public = github_request("GET", API + "public-key", token)
    if status != 200 or not isinstance(public.get("key_id"), str):
        raise RuntimeError("GitHub Actions encryption key unavailable")
    recipient = PublicKey(base64.b64decode(public["key"], validate=True))
    secret_value = base64.b64encode(KEYSTORE.read_bytes())
    sealed = SealedBox(recipient).encrypt(secret_value)
    encrypted = base64.b64encode(sealed).decode("ascii")
    status, _ = github_request("PUT", API + SECRET_NAME, token,
                                {"encrypted_value": encrypted, "key_id": public["key_id"]})
    if status not in (201, 204):
        raise RuntimeError("GitHub Actions secret not accepted")
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps({
        "repository": REPO, "secret": SECRET_NAME,
        "owner_signer_sha256": EXPECTED_CERT,
        "uploaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "ci_signature_verified": False,
        "original_keystore_retained": True,
    }, indent=2), encoding="utf8")
    print("ASTERION_OWNER_SIGNER_ACTIONS_SECRET_PROVISIONED")
    print("Original Windows signing key retained pending CI verification; no secrets printed.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as error:
        print("Signer migration blocked:", type(error).__name__, str(error)[:180])
        sys.exit(1)
