"""No-provider VPN policy unit tests; these are NOT physical tunnel tests."""
import unittest
from dataclasses import replace

from asterion_remote import vpn_route_policy as policy


def candidate(**kw):
    valid=dict(
        provider="owner-approved-free-provider",endpoint_id="legal-wg-exit-001",
        country="NL",exit_ip="8.8.8.8",free=True,compatible_config=True,
        owner_authorized=True,privacy_checked=True,direct_down_mbps=100,
        vpn_down_mbps=83,direct_up_mbps=35,vpn_up_mbps=31,
        direct_p95_ms=30,vpn_p95_ms=35,samples=4,
        dns_leak_detected=False,ip_leak_detected=False,
        native_control_reachable=True)
    valid.update(kw)
    return policy.ExitCandidate(**valid)


class VpnPolicyTests(unittest.TestCase):
    def test_default_no_exit_fails_closed(self):
        choice=policy.choose([])
        self.assertFalse(choice["ok"])
        self.assertFalse(choice["direct_fallback_enabled"])
        self.assertEqual(choice["state"],"VPN_UNAVAILABLE_NO_ELIGIBLE_FREE_EXIT")

    def test_fast_trusted_owner_route_can_be_eligible_but_not_connected(self):
        result=policy.choose([candidate()])
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"],"ROUTE_ELIGIBLE_NOT_CONNECTED")
        self.assertFalse(result["selected"]["actual_tunnel_connected"])

    def test_never_uses_rejected_supervpn_or_volunteer_vpngate(self):
        for name in ("supervpn","com.jrzheng.supervpnfree","vpn-gate"):
            with self.subTest(name=name):
                result=policy.choose([candidate(provider=name)])
                self.assertFalse(result["ok"])
                self.assertIn("provider_rejected",
                    result["examined"][0]["reject_reasons"])

    def test_refuses_paid_untrusted_and_unauthorized_config(self):
        for attrs,expected in [
            ({"free":False},"paid_provider_forbidden"),
            ({"privacy_checked":False},"privacy_not_verified"),
            ({"compatible_config":False},"no_owner_authorized_tunnel_config"),
            ({"owner_authorized":False},"owner_authorization_missing"),
            ({"native_control_reachable":False},
             "native_control_route_not_verified"),
        ]:
            with self.subTest(attrs=attrs):
                p=policy.assess(candidate(**attrs))
                self.assertFalse(p["eligible"])
                self.assertIn(expected,p["reject_reasons"])

    def test_hard_25_percent_speed_limit_both_directions(self):
        for changes in ({"vpn_down_mbps":74.99},
                        {"vpn_up_mbps":26.24}):
            result=policy.assess(candidate(**changes))
            self.assertFalse(result["eligible"])
            self.assertIn("fails_25_percent_throughput_budget",
                          result["reject_reasons"])
        self.assertTrue(policy.assess(candidate(
            vpn_down_mbps=75,vpn_up_mbps=26.25))["eligible"])

    def test_latencies_are_independently_reported(self):
        result=policy.assess(candidate(vpn_p95_ms=50))
        self.assertTrue(result["eligible"])
        self.assertFalse(result["latency_25_percent_target_met"])

    def test_optional_japan_not_required_for_secure_ip_masking(self):
        available=[candidate(),candidate(
            endpoint_id="japan",country="JP",exit_ip="1.1.1.1",
            vpn_down_mbps=80)]
        default=policy.choose(available)
        self.assertEqual(default["mode"],"private")
        self.assertTrue(default["ok"])
        japan=policy.choose(available,mode="japan_preferred")
        self.assertEqual(japan["selected"]["country"],"JP")
        self.assertTrue(japan["japan_preference_satisfied"])
        with self.assertRaises(ValueError):
            policy.choose(available,country="US")

    def test_unavailable_japan_uses_fast_private_exit_instead(self):
        route=policy.choose([candidate()],mode="geo_on_demand",country="JP")
        self.assertTrue(route["ok"])
        self.assertEqual(route["selected"]["country"],"NL")
        self.assertFalse(route["japan_preference_satisfied"])
        self.assertFalse(route["selected"]["actual_tunnel_connected"])

    def test_unknown_country_does_not_block_verified_ip_hider(self):
        route=policy.choose([candidate(country="")])
        self.assertTrue(route["ok"])
        self.assertEqual(route["selected"]["country"],"")

    def test_cheap_route_with_leaks_or_too_few_samples_fails(self):
        a=policy.assess(candidate(ip_leak_detected=True))
        self.assertIn("privacy_leak_detected",a["reject_reasons"])
        b=policy.assess(candidate(samples=2))
        self.assertIn("insufficient_real_speed_samples",b["reject_reasons"])

    def test_rotation_requires_distinct_global_ip_and_phone_probes(self):
        legit=policy.check_rotation("8.8.8.8","1.1.1.1",2700,
                                   old_probe_from_phone=True,
                                   new_probe_from_phone=True)
        self.assertTrue(legit["rotated"])
        self.assertFalse(legit["verified_tunnel_active"])
        same=policy.check_rotation("8.8.8.8","8.8.8.8",2700,
                                  old_probe_from_phone=True,
                                  new_probe_from_phone=True)
        self.assertFalse(same["rotated"])
        private=policy.check_rotation("192.168.1.2","8.8.8.8",2700,
                                  old_probe_from_phone=True,
                                  new_probe_from_phone=True)
        self.assertFalse(private["rotated"])
        no_phone=policy.check_rotation("8.8.8.8","1.1.1.1",2700,
                                      old_probe_from_phone=False,
                                      new_probe_from_phone=True)
        self.assertFalse(no_phone["rotated"])

    def test_tor_does_not_pretend_to_be_normal_fast_vpn(self):
        result=policy.tor_mode()
        self.assertTrue(result["supports_onion_when_tor_configured"])
        self.assertFalse(result["tor_runtime_installed_or_active"])
        self.assertFalse(result["full_phone_vpn_speed_budget_applicable"])


if __name__ == "__main__":
    unittest.main()
