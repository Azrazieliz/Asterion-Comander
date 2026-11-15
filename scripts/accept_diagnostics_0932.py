"""Read-only live acceptance of the existing paired Windows Control diagnostics.

No credentials, host address, frame contents, private files, or event payloads
are printed. Does not start a new gateway, install anything or alter pairing.
"""
from __future__ import annotations
import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import httpx


def main():
    state=Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl"
    token=(state/"control-token.txt").read_text("utf8").strip()
    base=(state/"agent-host.txt").read_text("utf8").strip()
    host=urlsplit(base)
    address=ipaddress.ip_address(host.hostname or "")
    if host.scheme!="http" or host.port!=8911 or host.username or host.password or (
        not address.is_private and not address.is_loopback):
        raise RuntimeError("unexpected_nonprivate_control_host")
    if len(token)<32:
        raise RuntimeError("existing_owner_token_unavailable")
    with httpx.Client(timeout=httpx.Timeout(25,connect=4),trust_env=False,
                      follow_redirects=False,
                      headers={"Authorization":"Bearer "+token}) as client:
        health=client.get(base+"/api/v1/health")
        health.raise_for_status()
        h=health.json()
        if not h.get("ok"):
            raise RuntimeError("windows_control_not_healthy")
        triage=client.get(base+"/api/v1/diagnostics/triage",
                          params={"app":"asterion.control","limit":80})
        triage.raise_for_status()
        t=triage.json()
        if not t.get("ok") or t.get("current_runtime_state_verified") is not False:
            raise RuntimeError("inaccurate_triage_response")
        snapshot=client.get(base+"/api/v1/diagnostics/snapshot",
                            params={"app":"asterion.control","limit":80,"phone":True})
        snapshot.raise_for_status()
        s=snapshot.json()
        if not s.get("ok") or s.get("root_cause_verified") is not False:
            raise RuntimeError("inaccurate_snapshot_response")
        if s.get("side_effects_performed") is not False:
            raise RuntimeError("unexpected_snapshot_side_effect")
        phone=s.get("android") or {}
        print(json.dumps({
            "ok":True,"windows_healthy":True,
            "triage_authenticated":True,"snapshot_authenticated":True,
            "evidence_only":True,"phone_paired":phone.get("paired") is True,
            "phone_reachable":phone.get("reachable") is True,
            "phone_journal_available":isinstance(phone.get("own_process_journal"),dict)
                and "records" in phone["own_process_journal"],
            "owner_data_or_pairing_modified":False
        },sort_keys=True),flush=True)


if __name__=="__main__":
    main()
