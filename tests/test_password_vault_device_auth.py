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

def test_device_screen_off_invalidates_lease_and_provider_settings_are_honest():
    source=(SRC/"ControlPasswordVault.java").read_text(encoding="utf-8")
    browser=(SRC/"BrowserActivity.java").read_text(encoding="utf-8")
    assert 'Intent.ACTION_SCREEN_OFF.equals(intent.getAction()))lock()' in source
    assert 'manager.isInteractive()' in source
    assert 'Context.RECEIVER_NOT_EXPORTED' in source
    assert 'watchScreen(c)' in source
    assert 'android.settings.CREDENTIAL_PROVIDER' in browser
    assert 'third-party website passkeys require provider approval' in browser


def test_portable_vault_archive_authenticated_encryption(tmp_path):
    import shutil,subprocess,pytest
    javac,java=shutil.which("javac"),shutil.which("java")
    if not javac or not java:pytest.skip("JDK required")
    subprocess.run([javac,"-encoding","UTF-8","-d",str(tmp_path),str(SRC/"VaultArchive.java"),
        str(ROOT/"tests/java/com/asterion/control/VaultArchiveTest.java")],check=True,capture_output=True,text=True)
    result=subprocess.run([java,"-cp",str(tmp_path),"com.asterion.control.VaultArchiveTest"],
        check=True,capture_output=True,text=True,timeout=60)
    assert "Vault archive authenticated encryption passed" in result.stdout

def test_archive_is_local_fresh_confirmed_and_no_overwrite():
    vault=(SRC/"ControlPasswordVault.java").read_text(encoding="utf-8")
    browser=(SRC/"BrowserActivity.java").read_text(encoding="utf-8")
    assert 'if(prefs.contains(id)){skipped++;continue;}' in vault
    assert 'if(!seen.add(id))throw' in vault
    assert 'additions.put(id,encrypt(item.toString()))' in vault
    assert 'VAULT_ARCHIVE_AUTH' in browser and 'createConfirmDeviceCredentialIntent' in browser
    assert 'Intent.ACTION_CREATE_DOCUMENT' in browser and 'Intent.ACTION_OPEN_DOCUMENT' in browser
    assert 'MessageDigest.isEqual(sealed,in.readNBytes(sealed.length+1))' in browser
    assert 'FLAG_SECURE' in browser
