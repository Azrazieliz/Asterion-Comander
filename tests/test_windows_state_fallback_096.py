"""Windows gateway restart must reuse canonical Samsung pairing and not create parallel state."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_native_registry_defaults_to_existing_windows_control_folder():
    for rel in ('asterion_remote/pairing.py','asterion_remote/phone_bridge.py'):
        source=(ROOT/rel).read_text(encoding='utf-8')
        assert "os.getenv('LOCALAPPDATA'" in source
        assert "'AsterionControl' if os.name=='nt'" in source
        assert "os.getenv('ASTERION_CONTROL_STATE'" in source

def test_gateway_restart_config_sets_owner_state_before_importing_app():
    p=(ROOT/'scripts/run_gateway_096.py').read_text(encoding='utf-8')
    assert 'ASTERION_CONTROL_STATE' in p
    assert p.index('ASTERION_CONTROL_STATE') < p.index('import uvicorn')
    assert "port=8995" in p
