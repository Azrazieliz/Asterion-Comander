"""Asterion Control performance: verify operational, scoped actions and no APK release."""
from pathlib import Path

from fastapi.testclient import TestClient

from asterion_remote import mcp_protocol, app as app_module

ROOT=Path(__file__).resolve().parents[1]
NATIVE=ROOT/"android/app/src/main/java/com/asterion/control"


def source(name: str) -> str:
    return (NATIVE/name).read_text(encoding="utf-8")


def test_health_actions_modify_real_capture_workload():
    manager=source("PerformanceManager.java")
    capture=source("CaptureService.java")
    observation=source("AppObservation.java")
    activity=source("MainActivity.java")
    assert 'Math.max(MIN_FRAME_MS,PerformanceManager.observationIntervalMs())' in observation
    assert "PerformanceManager.captureIntervalMs()" in capture
    assert "PerformanceManager.jpegQuality()" in capture
    assert "framesEncoded++" in capture and "framesSkipped++" in capture
    assert '"thermal_severe"' in manager and '"memory_pressure"' in manager
    assert '"prioritize_foreground_app"' in manager
    assert 'BOOST_DURATION_MS=20*60*1000L' in manager
    assert '"mode","automatic"' in manager
    assert "PerformanceManager.prioritizeForegroundNow(this)" in activity
    assert "PerformanceManager.setMode(this,mode)" in activity


def test_thermal_safety_overrides_manual_full_mode():
    manager=source("PerformanceManager.java")
    severe=manager.index("if(thermal>=PowerManager.THERMAL_STATUS_SEVERE)")
    full=manager.index('}else if("full".equals(mode))')
    assert severe<full
    assert "tune(950,43,18000,mode,\"thermal_severe\")" in manager


def test_governor_never_force_stops_unrelated_apps_or_disables_cycles():
    manager=source("PerformanceManager.java")
    agent=source("AgentService.java")
    assert "killBackgroundProcesses" not in manager
    assert "setprop" not in manager
    assert "forceStopPackage" not in manager
    assert "PhoneDirectMcp.start(this)" in agent
    assert "cycles.tick()" in agent
    assert '"system_clock_control",false' in manager
    assert '"other_app_process_control",false' in manager


def test_phoneside_mcp_and_authenticated_lan_reach_performance_actions():
    agent=source("AgentService.java")
    mcp=source("AndroidMcp.java")
    allowed=(ROOT/"asterion_remote/phone_bridge.py").read_text()
    names={x["name"] for x in mcp_protocol.TOOLS}
    for name in (
        "control_phone_performance_status",
        "control_phone_performance_mode",
        "control_phone_performance_optimize",
        "control_pc_performance_status",
        "control_pc_performance_mode"
    ):
        assert name in names
    for path in ("/performance/status","/performance/mode","/performance/optimize"):
        assert path in agent and path in allowed
    for name in ("performance_status","performance_mode","performance_optimize"):
        assert "control_phone_"+name in mcp


def test_windows_process_changes_are_only_for_managed_jobs():
    module=(ROOT/"asterion_remote/app.py").read_text()
    assert "for key, item in COMMANDS.items()" in module
    assert "psutil.BELOW_NORMAL_PRIORITY_CLASS" in module
    assert "'unrelated_apps_changed': False" in module
    assert "target.nice(item['_perf_saved_priority'])" in module
    assert "priority_changed_elsewhere" in module
    assert "ManagedJobPriority" in module


def test_non_windows_process_control_is_explicitly_unsupported():
    import pytest
    from fastapi import HTTPException
    if app_module.os.name=="nt":
        return
    with pytest.raises(HTTPException) as exc:
        app_module.manage_performance_priority(
            app_module.ManagedJobPriority(mode="favor_foreground"))
    assert exc.value.status_code==503
