"""Evidence-gated zero-cost VPN exit selection for Asterion Control.

POLICY ONLY: no tunnel, no provider key, no connection claim, no VPN service
startup. The native Android VpnService remains the actual data-plane owner.
Only real owner-authorized, free, eligible and device-measured routes can be
selected. A route *selection* is never a claim of established protection.

Default preference: trustworthy high-throughput IP replacement regardless
of country. Japan is ONLY an optional soft preference; lack of a Japanese
exit MUST NOT block a working privacy route.
Tor onion access is a distinct mode and must not be reported as fast VPN.
"""
from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass
from typing import Iterable

SPEED_FLOOR = 0.75
RTT_TARGET = 1.25
MIN_SAMPLES = 3
MIN_ROTATION_SECONDS = 30 * 60
MAX_ROTATION_SECONDS = 60 * 60
_BLOCKED_PROVIDERS = {"supervpn", "com.jrzheng.supervpnfree", "vpn-gate",
                      "vpngate", "vpngate.net"}


@dataclass(frozen=True)
class ExitCandidate:
    provider: str
    endpoint_id: str
    country: str
    exit_ip: str
    free: bool
    compatible_config: bool
    owner_authorized: bool
    privacy_checked: bool
    direct_down_mbps: float
    vpn_down_mbps: float
    direct_up_mbps: float
    vpn_up_mbps: float
    direct_p95_ms: float
    vpn_p95_ms: float
    samples: int
    dns_leak_detected: bool = False
    ip_leak_detected: bool = False
    native_control_reachable: bool = False


def _global_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def assess(candidate: ExitCandidate) -> dict:
    """No assumptions about provider availability or actually active tunnels."""
    if not isinstance(candidate,ExitCandidate):
        raise TypeError("exit_candidate_required")
    reasons=[]
    name=candidate.provider.strip().lower()
    if name in _BLOCKED_PROVIDERS:
        reasons.append("provider_rejected")
    if not candidate.free:
        reasons.append("paid_provider_forbidden")
    if not candidate.compatible_config:
        reasons.append("no_owner_authorized_tunnel_config")
    if not candidate.owner_authorized:
        reasons.append("owner_authorization_missing")
    if not candidate.privacy_checked:
        reasons.append("privacy_not_verified")
    if not _global_ip(candidate.exit_ip):
        reasons.append("exit_ip_not_publicly_verified")
    # Country verification is not a privacy prerequisite. Some free VPNs
    # deliberately obscure exit geography; the owner prioritizes a different
    # working public IP, not a paid country-picker.
    if candidate.country and not (
        isinstance(candidate.country, str) and
        len(candidate.country.strip()) == 2 and
        candidate.country.strip().isalpha()
    ):
        reasons.append("invalid_optional_country_label")
    if candidate.samples < MIN_SAMPLES:
        reasons.append("insufficient_real_speed_samples")
    numbers=(candidate.direct_down_mbps,candidate.vpn_down_mbps,
             candidate.direct_up_mbps,candidate.vpn_up_mbps,
             candidate.direct_p95_ms,candidate.vpn_p95_ms)
    if not all(isinstance(x,(int,float)) and
               math.isfinite(x) and x>0 for x in numbers):
        reasons.append("invalid_network_measurements")
        down=up=None
        rtt=None
    else:
        down=candidate.vpn_down_mbps/candidate.direct_down_mbps
        up=candidate.vpn_up_mbps/candidate.direct_up_mbps
        rtt=candidate.vpn_p95_ms/candidate.direct_p95_ms
        if down<SPEED_FLOOR or up<SPEED_FLOOR:
            reasons.append("fails_25_percent_throughput_budget")
    if candidate.dns_leak_detected or candidate.ip_leak_detected:
        reasons.append("privacy_leak_detected")
    if not candidate.native_control_reachable:
        reasons.append("native_control_route_not_verified")
    eligible=not reasons
    return {
        "provider":candidate.provider,
        "endpoint_id":candidate.endpoint_id,
        "country":candidate.country.strip().upper() if isinstance(candidate.country,str) else "",
        "exit_ip":candidate.exit_ip if _global_ip(candidate.exit_ip) else "",
        "eligible":eligible,
        "reject_reasons":reasons,
        "download_ratio":round(down,4) if down is not None else None,
        "upload_ratio":round(up,4) if up is not None else None,
        "p95_rtt_ratio":round(rtt,4) if rtt is not None else None,
        "latency_25_percent_target_met":rtt is not None and rtt<=RTT_TARGET,
        "actual_tunnel_connected":False,
        "actually_rotated":False,
    }


def choose(candidates: Iterable[ExitCandidate], *,
           country: str | None = None, mode: str = "private") -> dict:
    """Return the best *eligible*, NOT CONNECTED, private IP replacement.

    "geo_on_demand" is retained for older clients, but any Japan request
    is a soft preference. No free/country-specific exit? Fall back to any
    verified privacy route that meets cost, privacy and 25% speed rules.
    """
    if mode not in {"private","geo_on_demand","japan_preferred"}:
        raise ValueError("invalid_routing_mode")
    if country not in {None,"JP"}:
        raise ValueError("country_selection_not_supported")
    prefer_japan=(mode=="japan_preferred" or
                  mode=="geo_on_demand" or country=="JP")
    examined=[]
    eligible=[]
    for candidate in candidates:
        assessment=assess(candidate)
        examined.append(assessment)
        if assessment["eligible"]:
            eligible.append(assessment)
    if not eligible:
        return {"ok":False,"state":"VPN_UNAVAILABLE_NO_ELIGIBLE_FREE_EXIT",
                "mode":mode,"selected":None,
                "examined":examined,"direct_fallback_enabled":False,
                "japan_preference_satisfied":False,
                "unverified_connected_claim":False}
    # Throughput is hard gate, RTT target is a preference, not fake hard proof.
    best=max(eligible,key=lambda e:(
        bool(prefer_japan and e["country"]=="JP"),
        bool(e["latency_25_percent_target_met"]),
        min(e["download_ratio"],e["upload_ratio"]),
        -e["p95_rtt_ratio"]))
    return {"ok":True,"state":"ROUTE_ELIGIBLE_NOT_CONNECTED",
            "mode":mode,"selected":best,
            "examined":examined,"direct_fallback_enabled":False,
            "japan_preference_satisfied":bool(prefer_japan and best["country"]=="JP"),
            "unverified_connected_claim":False}


def check_rotation(old_ip:str,new_ip:str,elapsed_seconds:float, *,
                   old_probe_from_phone:bool,new_probe_from_phone:bool)->dict:
    """Accept only distinct, real PUBLIC IP evidence collected from the phone."""
    if not isinstance(elapsed_seconds,(int,float)) or not math.isfinite(
            elapsed_seconds) or elapsed_seconds<0:
        raise ValueError("invalid_elapsed_time")
    valid=_global_ip(old_ip) and _global_ip(new_ip)
    changed=valid and old_ip!=new_ip
    within=MIN_ROTATION_SECONDS<=elapsed_seconds<=MAX_ROTATION_SECONDS
    observed=old_probe_from_phone and new_probe_from_phone
    success=bool(changed and within and observed)
    return {"rotated":success,"different_public_ips":changed,
            "within_30_to_60_minutes":within,
            "phone_external_probe_evidence":bool(observed),
            "verified_tunnel_active":False,
            "state":"ROTATION_OBSERVED" if success else "ROTATION_UNVERIFIED"}


def tor_mode() -> dict:
    """Tor is a separate optional privacy mode, NOT normal VPN compliance."""
    return {"mode":"tor_onion","provider":"Tor Project",
            "status":"requires_explicit_tor_runtime",
            "full_phone_vpn_speed_budget_applicable":False,
            "may_be_slow":True,"supports_onion_when_tor_configured":True,
            "tor_runtime_installed_or_active":False,
            "vpn_interface_claimed":False}
