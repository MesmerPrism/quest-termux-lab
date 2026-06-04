#!/usr/bin/env python3
"""Public-safe peer gossip simulator.

This tool prepares a future Termux peer mesh by merging status observations.
It does not open sockets, discover devices, relay commands, use ADB, or run
shell commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GOSSIP_SCHEMA = "quest-termux-lab.peer-gossip-envelope.v1"
SUMMARY_SCHEMA = "quest-termux-lab.peer-mesh-summary.v1"
HEARTBEAT_SCHEMA = "quest-termux-lab.fleet-agent-heartbeat.v1"
FORBIDDEN_KEYS = {
    "adb_command",
    "adb_target",
    "apk_path",
    "command",
    "command_id",
    "install_request",
    "launch_request",
    "pairing_code",
    "payload",
    "shell",
    "shell_command",
    "token",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def write_json(path_text: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if path_text == "-":
        print(text)
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                return True
            if contains_forbidden_key(child):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_key(child) for child in value)
    return False


def validate_envelope(payload: dict[str, Any]) -> None:
    if payload.get("schema") != GOSSIP_SCHEMA:
        raise ValueError("unsupported gossip schema")
    if contains_forbidden_key(payload):
        raise ValueError("gossip envelope contains command-like or credential-like fields")
    if not isinstance(payload.get("fleet_id"), str):
        raise ValueError("missing fleet_id")
    if not isinstance(payload.get("sender_agent_id"), str):
        raise ValueError("missing sender_agent_id")
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("missing observations")
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError("observation must be an object")
        for key in [
            "agent_id",
            "observed_at",
            "heard_from_agent_id",
            "heartbeat_sequence",
            "agent_alive",
            "central_reachable",
            "local_adb_available",
            "stale_after_seconds",
        ]:
            if key not in observation:
                raise ValueError(f"observation missing {key}")


def validate_heartbeat(payload: dict[str, Any]) -> None:
    if payload.get("schema") != HEARTBEAT_SCHEMA:
        raise ValueError("unsupported heartbeat schema")
    for key in ["fleet_id", "agent_id", "sequence", "observed_at", "central_reachable", "local_adb"]:
        if key not in payload:
            raise ValueError(f"heartbeat missing {key}")
    if contains_forbidden_key(payload):
        # Heartbeats may contain last_command_id or adb_target in the full fleet
        # schema, so do not reject the heartbeat itself. The conversion below
        # intentionally strips those fields from gossip.
        return


@dataclass
class GossipState:
    fleet_id: str
    observer_agent_id: str
    observations: dict[str, dict[str, Any]] = field(default_factory=dict)
    forbidden_message_count: int = 0

    def merge_envelope(self, envelope: dict[str, Any]) -> None:
        try:
            validate_envelope(envelope)
        except ValueError:
            self.forbidden_message_count += 1
            raise
        if envelope["fleet_id"] != self.fleet_id:
            raise ValueError("fleet_id mismatch")
        for observation in envelope["observations"]:
            agent_id = str(observation["agent_id"])
            previous = self.observations.get(agent_id)
            if previous is None or is_newer(observation, previous):
                self.observations[agent_id] = dict(observation)

    def summary(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        peers = []
        for agent_id in sorted(self.observations):
            observation = self.observations[agent_id]
            peers.append(
                {
                    "agent_id": agent_id,
                    "status": status_for(observation, current),
                    "observed_at": observation["observed_at"],
                    "heard_from_agent_id": observation["heard_from_agent_id"],
                    "central_reachable": bool(observation["central_reachable"]),
                    "local_adb_available": bool(observation["local_adb_available"]),
                    "battery_percent": observation.get("battery_percent"),
                    "last_command_status": observation.get("last_command_status"),
                }
            )
        return {
            "schema": SUMMARY_SCHEMA,
            "fleet_id": self.fleet_id,
            "observer_agent_id": self.observer_agent_id,
            "observed_at": current.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "known_peer_count": len(peers),
            "forbidden_message_count": self.forbidden_message_count,
            "peers": peers,
        }


def observation_from_heartbeat(
    heartbeat: dict[str, Any],
    heard_from_agent_id: str | None = None,
    stale_after_seconds: int = 30,
    summary_hash: str | None = None,
) -> dict[str, Any]:
    validate_heartbeat(heartbeat)
    local_adb = heartbeat.get("local_adb")
    if not isinstance(local_adb, dict):
        raise ValueError("heartbeat local_adb must be an object")
    agent_id = str(heartbeat["agent_id"])
    return {
        "agent_id": agent_id,
        "observed_at": str(heartbeat["observed_at"]),
        "heard_from_agent_id": heard_from_agent_id or agent_id,
        "heartbeat_sequence": int(heartbeat["sequence"]),
        "agent_alive": True,
        "central_reachable": bool(heartbeat["central_reachable"]),
        "local_adb_available": bool(local_adb.get("available", False)),
        "local_adb_shell_uid": local_adb.get("shell_uid") if isinstance(local_adb.get("shell_uid"), str) else None,
        "battery_percent": heartbeat.get("battery_percent") if isinstance(heartbeat.get("battery_percent"), int) else None,
        "last_command_status": heartbeat.get("last_command_status")
        if isinstance(heartbeat.get("last_command_status"), str)
        else None,
        "stale_after_seconds": stale_after_seconds,
        "summary_hash": summary_hash,
    }


def envelope_from_heartbeat(
    heartbeat: dict[str, Any],
    sender_agent_id: str,
    message_id: str,
    hop_ttl: int,
    stale_after_seconds: int,
) -> dict[str, Any]:
    observation = observation_from_heartbeat(
        heartbeat,
        heard_from_agent_id=sender_agent_id,
        stale_after_seconds=stale_after_seconds,
    )
    envelope = {
        "schema": GOSSIP_SCHEMA,
        "fleet_id": str(heartbeat["fleet_id"]),
        "message_id": message_id,
        "sender_agent_id": sender_agent_id,
        "created_at": utc_now(),
        "hop_ttl": hop_ttl,
        "observations": [observation],
        "authority_boundary": [
            "Peer gossip carries status observations only.",
            "Peer gossip does not carry commands, shell text, ADB targets, pairing material, or install/launch authority.",
            "Central direct ADB remains the recovery and privileged truth-check route.",
        ],
    }
    validate_envelope(envelope)
    return envelope


def relay_envelope(envelope: dict[str, Any], sender_agent_id: str, message_id: str) -> dict[str, Any]:
    validate_envelope(envelope)
    hop_ttl = int(envelope["hop_ttl"])
    if hop_ttl <= 0:
        raise ValueError("cannot relay envelope with hop_ttl <= 0")
    observations = []
    for observation in envelope["observations"]:
        updated = dict(observation)
        updated["heard_from_agent_id"] = sender_agent_id
        observations.append(updated)
    relayed = {
        "schema": GOSSIP_SCHEMA,
        "fleet_id": envelope["fleet_id"],
        "message_id": message_id,
        "sender_agent_id": sender_agent_id,
        "created_at": utc_now(),
        "hop_ttl": hop_ttl - 1,
        "observations": observations,
        "authority_boundary": list(envelope["authority_boundary"]),
    }
    validate_envelope(relayed)
    return relayed


def is_newer(candidate: dict[str, Any], previous: dict[str, Any]) -> bool:
    candidate_time = parse_time(str(candidate["observed_at"]))
    previous_time = parse_time(str(previous["observed_at"]))
    if candidate_time != previous_time:
        return candidate_time > previous_time
    return int(candidate.get("heartbeat_sequence", 0)) > int(previous.get("heartbeat_sequence", 0))


def status_for(observation: dict[str, Any], now: datetime) -> str:
    if not observation.get("agent_alive"):
        return "unknown"
    observed_at = parse_time(str(observation["observed_at"]))
    stale_after = int(observation["stale_after_seconds"])
    age_seconds = (now - observed_at).total_seconds()
    if age_seconds > stale_after:
        return "stale"
    return "alive"


def run_summarize(args: argparse.Namespace) -> int:
    if not args.input:
        raise SystemExit("at least one input envelope is required")
    first = load_json(Path(args.input[0]))
    validate_envelope(first)
    state = GossipState(fleet_id=str(first["fleet_id"]), observer_agent_id=args.observer)
    state.merge_envelope(first)
    for path_text in args.input[1:]:
        state.merge_envelope(load_json(Path(path_text)))
    print(json.dumps(state.summary(), indent=2, sort_keys=True))
    return 0


def run_summarize_dir(args: argparse.Namespace) -> int:
    directory = Path(args.directory)
    state = GossipState(fleet_id=args.fleet_id, observer_agent_id=args.observer)
    for path in sorted(directory.glob("*.json")):
        try:
            state.merge_envelope(load_json(path))
        except ValueError:
            if not args.skip_invalid:
                raise
    print(json.dumps(state.summary(), indent=2, sort_keys=True))
    return 0


def run_from_heartbeat(args: argparse.Namespace) -> int:
    heartbeat = load_json(Path(args.heartbeat))
    envelope = envelope_from_heartbeat(
        heartbeat,
        sender_agent_id=args.sender,
        message_id=args.message_id,
        hop_ttl=args.hop_ttl,
        stale_after_seconds=args.stale_after_seconds,
    )
    write_json(args.output, envelope)
    return 0


def run_relay(args: argparse.Namespace) -> int:
    envelope = relay_envelope(
        load_json(Path(args.envelope)),
        sender_agent_id=args.sender,
        message_id=args.message_id,
    )
    write_json(args.output, envelope)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge peer gossip status envelopes.")
    sub = parser.add_subparsers(dest="command", required=True)

    summarize = sub.add_parser("summarize")
    summarize.add_argument("--observer", required=True)
    summarize.add_argument("input", nargs="+")
    summarize.set_defaults(func=run_summarize)

    summarize_dir = sub.add_parser("summarize-dir")
    summarize_dir.add_argument("--observer", required=True)
    summarize_dir.add_argument("--fleet-id", required=True)
    summarize_dir.add_argument("--skip-invalid", action="store_true")
    summarize_dir.add_argument("directory")
    summarize_dir.set_defaults(func=run_summarize_dir)

    from_heartbeat = sub.add_parser("from-heartbeat")
    from_heartbeat.add_argument("--sender", required=True)
    from_heartbeat.add_argument("--message-id", required=True)
    from_heartbeat.add_argument("--hop-ttl", type=int, default=2)
    from_heartbeat.add_argument("--stale-after-seconds", type=int, default=30)
    from_heartbeat.add_argument("--output", default="-")
    from_heartbeat.add_argument("heartbeat")
    from_heartbeat.set_defaults(func=run_from_heartbeat)

    relay = sub.add_parser("relay")
    relay.add_argument("--sender", required=True)
    relay.add_argument("--message-id", required=True)
    relay.add_argument("--output", default="-")
    relay.add_argument("envelope")
    relay.set_defaults(func=run_relay)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
