"""Reject a stale, signer-compatible APK whose actual dex omits advertised features."""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
apk=root/"dist/Asterion-Control-v0.9.34-release.apk"
manifest=root/"dist/SHA256SUMS-v0.9.34.txt"
if not apk.is_file() or not manifest.is_file():
    raise RuntimeError("owner_signed_0934_artifact_missing")
data=apk.read_bytes()
sha=hashlib.sha256(data).hexdigest()
if manifest.read_text("utf8").strip()!=sha+"  "+apk.name:
    raise RuntimeError("owner_signer_release_checksum_mismatch")
# Android keeps Java string constants as dex MUTF-8. If a user-facing
# capability isn't here, Gradle might have packaged an old MainActivity.
with zipfile.ZipFile(apk) as archive:
    dex=[archive.read(n) for n in archive.namelist()
         if n.startswith("classes") and n.endswith(".dex")]
if not dex:raise RuntimeError("android_dex_not_packaged")
combined=b"".join(dex)
required={
    "partner_diagnostics":b"Read live process and crash evidence",
    "writer_model_status":b"Check installed Writer models",
    "free_vpn_profile":b"Get free VPN profile",
    "app_shortcut":b"Add to my Control apps",
    "permissions_hub":b"Permissions & authorizations",
    "verified_queue_state":b"stored_queue_counts_verified",
    "universal_tools_tab":b"Tools & services.",
}
missing=[name for name,marker in required.items() if marker not in combined]
print(json.dumps({"ok":not missing,"version":"0.9.34",
                  "sha256":sha,"apk_bytes":len(data),
                  "dex_count":len(dex),"features_present":sorted(set(required)-set(missing)),
                  "features_missing":missing},sort_keys=True),flush=True)
if missing:raise SystemExit(2)
