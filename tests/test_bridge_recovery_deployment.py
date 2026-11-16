"""Owner production relay repair must preserve signer, pairing and current app data."""
from pathlib import Path
import ast
from asterion_remote import github_bridge_git
from scripts import deploy_private_bridge_recovery_20261116 as repair

ROOT=Path(__file__).resolve().parents[1]

def test_repair_scope_is_three_known_existing_windows_source_files():
    assert repair.FILES==(
        "asterion_remote/github_bridge.py",
        "asterion_remote/github_bridge_git.py",
        "scripts/control_repair_watchdog.ps1",
    )
    forbidden=("control-token","keystore","signing","android/",
               "phone_bridge.py","native_phone_relay.py",
               "cert","wss","session_journal","app.py")
    assert all(all(v not in path.lower() for v in forbidden)
               for path in repair.FILES)

def test_repair_defaults_to_dry_run_and_is_atomic_with_backup():
    source=(ROOT/"scripts/deploy_private_bridge_recovery_20261116.py").read_text("utf8")
    ast.parse(source)
    assert "parser.add_argument(\"--apply\",action=\"store_true\")" in source
    assert 'if not apply:' in source
    assert 'deployment-backups' in source
    assert 'with backup.open("xb")' in source
    assert "os.replace(tmp,target)" in source
    assert 'for rel in reversed(installed):' in source
    assert 'report["pending_supervised_reload"]' in source
    assert "restarted" not in "\n".join(
        x for x in source.splitlines() if "subprocess." in x and "powershell" not in x)

def test_repair_requires_exact_source_and_owner_production():
    source=(ROOT/"scripts/deploy_private_bridge_recovery_20261116.py").read_text("utf8")
    for required in ("EXPECTED_ORIGIN","EXPECTED_BRANCH",
                     "Unexpected production directory",
                     "Source checkout contains uncommitted tracked changes",
                     "Expected existing source/production file missing",
                     "Watchdog PowerShell syntax invalid",
                     "Git relay safety contract not present",
                     "Idle-only watchdog recovery contract missing"):
        assert required in source

def test_watchdog_never_interrupts_uncertain_phone_action():
    source=(ROOT/"scripts/control_repair_watchdog.ps1").read_text("utf8")
    assert "$bridge.Count -eq 1" in source
    assert "IsNullOrWhiteSpace($inflight)" in source
    assert "$jobsKnown -and -not $activeJobs -and $cooldown" in source
    assert "control-git-bridge-last-recovery.txt" in source
    assert "Stop-Process -Id $current.ProcessId -Force" in source
    assert "Stop-Process -Id $bridge[0].ProcessId -Force" not in source
    assert "Remove-Item $key" not in source
