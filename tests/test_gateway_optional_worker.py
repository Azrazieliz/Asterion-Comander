"""Asterion Control gateway must never require Windows when Android is principal."""
import pytest
from asterion_remote import mcp_gateway
from asterion_remote import github_bridge_git


@pytest.mark.parametrize("url", [
    "http://192.168.4.5:8911/mcp", "http://127.0.0.1:8911/mcp",
    "http://10.0.0.4:8911/mcp",
])
def test_private_dynamic_windows_routes(url):
    assert mcp_gateway._validate_windows_route(url) == url


@pytest.mark.parametrize("url", [
    "http://0.0.0.0:8911/mcp", "http://8.8.8.8:8911/mcp",
    "https://192.168.1.2:8911/mcp", "http://192.168.1.2:4444/mcp",
    "http://169.254.1.2:8911/mcp", "http://192.168.1.2:8911/other",
])
def test_invalid_windows_routes_rejected(url):
    with pytest.raises(RuntimeError):
        mcp_gateway._validate_windows_route(url)


def test_optional_windows_agent_not_needed_for_gateway(monkeypatch):
    monkeypatch.setattr(mcp_gateway,"WINDOWS_UPSTREAM","")
    monkeypatch.setattr(github_bridge_git,"agent_host",
                        lambda: (_ for _ in ()).throw(RuntimeError("PC offline")))
    assert mcp_gateway._windows_route() is None
