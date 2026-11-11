"""Regression for Windows PowerShell 5.1's legacy script codepage.

The CI pwsh parser accepts Unicode UTF-8 without BOM, but Windows PowerShell
5.1 on the owner's original signing machine may misparse non-ASCII characters.
Only source checks run here; never invoke an owner signing key in CI.
"""
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_owner_signed_control_088.ps1"


def test_owner_signing_script_is_powershell_51_codepage_safe():
    data = SCRIPT.read_bytes()
    assert all(byte < 0x80 for byte in data), (
        "Windows PowerShell 5.1 expects ASCII or UTF-8 with BOM; "
        "keep this deployment script ASCII-only"
    )
    text = data.decode("ascii")
    assert "Get-SignerDigest $baseline" in text
    assert "if($new -ne $original)" in text
    assert "throw \"CERTIFICATE_MISMATCH:" in text
    assert "git ls-remote origin" in text
    assert "git push origin" in text
    assert "OWNER_SIGNED_BUILD_OK" in text
    assert "Remove-Item $target" not in text
