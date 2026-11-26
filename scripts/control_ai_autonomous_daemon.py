"""Real local autonomous cycle daemon wrapper, no ChatGPT or cloud dependency.

Uses existing Control overnight SQLite state, exact owner-reviewed tasks and
isolated Git candidate executor. Idle BLOCKED when model/sandbox unavailable,
never starts a second relay, calls Android, signs APKs or edits production.
Install a supervised OS startup service ONLY after live independent acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import sys
import time
from urllib.parse import urlsplit

from asterion_remote import overnight_supervisor
from asterion_remote.isolated_test_runner import IsolatedContainerTests
from asterion_remote.local_model_provider import LocalModelConfig
from scripts.control_ai_independent_dev import attempt_once, initialize

_STOP=False


def request_stop(*_):
    global _STOP
    _STOP=True


def preflight(config: dict) -> tuple[bool, str]:
    """All checked BEFORE task claim. A missing tool is not model failure."""
    endpoint=LocalModelConfig(endpoint=config["endpoint"],model=config["model"])
    IsolatedContainerTests(config["pinned_test_image"],
                           config["reviewed_test_map"])
    parsed=urlsplit(endpoint.endpoint)
    with socket.create_connection(("127.0.0.1",parsed.port),timeout=3):
        return True,"local_model_listener_and_verified_sandbox_configured"


def publish(path: Path,status: dict):
    """Atomic no-secrets heartbeat, not a self-issued success certificate."""
    allowed={key:status[key] for key in (
        "state","cycle_id","reason","updated_ms","task","verified_turns")
        if key in status}
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".pending")
    with temp.open("w",encoding="utf-8") as f:
        json.dump(allowed,f,sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp,path)


def run(config: dict, *, once=False, pause_s=45, pause=time.sleep):
    if not 5<=pause_s<=3600:
        raise ValueError("invalid_supervisor_idle_interval")
    home=Path(config["repo"]).resolve(strict=True)
    if not (home/".git").exists():
        raise ValueError("verified_control_repository_required")
    manifest=home/config["tasks"]
    expected_test_map=json.loads(manifest.read_text(encoding="utf-8"))["trusted_tests"]
    if config["reviewed_test_map"]!=expected_test_map:
        raise ValueError("trusted_test_map_changed_without_versioned_review")
    cycle=config["cycle"]
    initialize(cycle,manifest)
    heartbeat=Path(config["status_file"]).resolve()
    source_root=Path(config["isolated_root"]).resolve()
    if heartbeat==home or home in heartbeat.parents or source_root==home or home in source_root.parents:
        raise ValueError("autonomy_state_must_not_write_canonical_source")
    while not _STOP:
        state=overnight_supervisor.status(cycle)
        status={"state":state["state"],"cycle_id":cycle,
                "verified_turns":state["verified_turns"],
                "updated_ms":time.time_ns()//1_000_000}
        if state["state"]!="ready":
            status["reason"]="incomplete_or_uncertain_cycle_waits_for_independent_reconciliation"
            publish(heartbeat,status)
            if once or state["state"] in ("needs_review","finished","stopped",
                                         "dispatch_uncertain","awaiting_verification"):
                return status
            pause(pause_s)
            continue
        try:
            preflight(config)
        except (OSError,RuntimeError,ValueError) as error:
            status["state"]="blocked_prerequisites"
            status["reason"]=type(error).__name__
            publish(heartbeat,status)
            if once:return status
            pause(pause_s)
            continue
        try:
            result=attempt_once(cycle=cycle,canonical_root=home,
                isolated_root=source_root,
                model_endpoint=config["endpoint"],
                model_name=config["model"],
                pinned_test_image=config["pinned_test_image"],
                reviewed_test_map=config["reviewed_test_map"])
            actual=overnight_supervisor.status(cycle)
            status.update({"state":actual["state"],
                "verified_turns":actual["verified_turns"]})
            if "task" in result:status["task"]=result["task"]
        except Exception as error:
            # Task & cycle are durable; never retry a possibly dispatched turn.
            status["state"]="needs_review"
            status["reason"]=type(error).__name__
            publish(heartbeat,status)
            return status
        publish(heartbeat,status)
        if once or status["state"]!="ready" or result.get("status"):
            return status
        pause(1)
    publish(heartbeat,{"state":"stopped","cycle_id":cycle,
                        "updated_ms":time.time_ns()//1_000_000})
    return {"state":"stopped","cycle_id":cycle}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--idle-seconds",type=int,default=45)
    args=parser.parse_args(argv)
    config=json.loads(args.config.read_text(encoding="utf-8"))
    required={"repo","tasks","cycle","isolated_root","endpoint",
              "model","pinned_test_image","reviewed_test_map","status_file"}
    if set(config)!=required:
        raise ValueError("owner_run_config_schema_mismatch")
    signal.signal(signal.SIGTERM,request_stop)
    signal.signal(signal.SIGINT,request_stop)
    result=run(config,once=args.once,pause_s=args.idle_seconds)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["state"] in ("ready","finished","stopped") else 2


if __name__=="__main__":
    sys.exit(main())
