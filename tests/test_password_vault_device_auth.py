"""Non-neural vault authentication guardrails; physical Android consent remains required."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"android/app/src/main/java/com/asterion/control"

def test_vault_keeps_existing_encryption_and_auth_lease_is_not_persisted():
    source=(SRC/"ControlPasswordVault.java").read_text(encoding="utf-8")
    assert '"asterion_control_vault_aes256_v1"' in source
    assert 'AES/GCM/NoPadding' in source
    assert 'SystemClock.elapsedRealtime()' in source
    assert 'manager.isDeviceLocked()' in source
    assert 'unlockedUntilElapsed>SystemClock.elapsedRealtime()' in source
    assert 'putInt(AUTH_TIMEOUT,newTimeout)' in source
    assert 'putLong("unlockedUntilElapsed"' not in source
    assert source.count('requireAccess(context);')==3
    assert 'static void lock()' in source

def test_device_confirmation_controls_unlock_and_timeout():
    source=(SRC/"BrowserActivity.java").read_text(encoding="utf-8")
    assert 'createConfirmDeviceCredentialIntent(' in source
    assert 'if(policy==null||resultCode!=RESULT_OK)' in source
    assert 'ControlPasswordVault.confirmDeviceAuth(this,policy)' in source
    assert 'ControlPasswordVault.canAccess(this)' in source
    assert 'origin.equals(verifiedActiveHttpsOrigin())' in source
    assert 'Device authentication and timeout' in source
    assert 'ControlPasswordVault.generatePassword()' in source
    assert 'password.setSaveEnabled(false)' in source

def test_autofill_still_requires_exact_origin_and_vault_gate():
    source=(SRC/"ControlAutofillService.java").read_text(encoding="utf-8")
    assert 'domains.size()!=1' in source
    assert 'origin.equals(real)' in source
    assert 'ControlPasswordVault.accounts(this,form.origin)' in source
    assert 'ControlPasswordVault.save(this,form.origin,' in source
