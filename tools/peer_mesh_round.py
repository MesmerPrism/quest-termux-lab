#!/usr/bin/env python3
"""Public-safe file-drop round simulator for peer mesh preparation.

The simulator writes synthetic gossip envelopes into per-peer inbox/outbox
folders. It does not open sockets, discover peers, run shell commands, use
ADB, or relay central commands.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import peer_mesh_gossip


SCENARIO_SCHEMA = "quest-termux-lab.peer-mesh-round-scenario.v1"
REPORT_SCHEMA = "quest-termux-lab.peer-mesh-round-report.v1"
SAFE_FILE_PART = re.compile(r"[^a-zA-Z0-9_.-]+")


@dataclass(frozen=True)
class NodeDirs:
    agent_id: str
    inbox: Path
    outbox: Path


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def safe_file_part(value: str) -> str:
    cleaned = SAFE_FILE_PART.sub("-", value).strip(".-")
    if not cleaned:
        raise ValueError("empty file-safe identifier")
    return cleaned[:120]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_agent_list(scenario: dict[str, Any]) -> list[str]:
    nodes = scenario.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("scenario nodes must be a non-empty array")
    agent_ids: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("agent_id"), str):
            raise ValueError("each node must include agent_id")
        agent_ids.append(node["agent_id"])
    if len(set(agent_ids)) != len(agent_ids):
        raise ValueError("node agent_id values must be unique")
    return agent_ids


def validate_scenario(scenario: dict[str, Any]) -> None:
    if scenario.get("schema") != SCENARIO_SCHEMA:
        raise ValueError("unsupported peer mesh round scenario schema")
    if peer_mesh_gossip.contains_forbidden_key(scenario):
        raise ValueError("scenario contains command-like or credential-like fields")
    for key in ["fleet_id", "round_id", "nodes", "heartbeats", "gossip_links"]:
        if key not in scenario:
            raise ValueError(f"scenario missing {key}")
    if not isinstance(scenario["fleet_id"], str) or not scenario["fleet_id"]:
        raise ValueError("scenario fleet_id must be a string")
    if not isinstance(scenario["round_id"], str) or not scenario["round_id"]:
        raise ValueError("scenario round_id must be a string")

    agent_ids = set(require_agent_list(scenario))
    heartbeats = scenario["heartbeats"]
    if not isinstance(heartbeats, list) or not heartbeats:
        raise ValueError("scenario heartbeats must be a non-empty array")
    heartbeat_agents: set[str] = set()
    for heartbeat in heartbeats:
        if not isinstance(heartbeat, dict):
            raise ValueError("heartbeat entry must be an object")
        agent_id = heartbeat.get("agent_id")
        path_text = heartbeat.get("path")
        if not isinstance(agent_id, str) or agent_id not in agent_ids:
            raise ValueError("heartbeat agent_id must reference a node")
        if agent_id in heartbeat_agents:
            raise ValueError("heartbeat agent_id values must be unique")
        heartbeat_agents.add(agent_id)
        if not isinstance(path_text, str) or not path_text:
            raise ValueError("heartbeat path must be a relative string")
        path = Path(path_text)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("heartbeat path must be relative and stay inside the repository")

    links = scenario["gossip_links"]
    if not isinstance(links, list):
        raise ValueError("scenario gossip_links must be an array")
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("gossip link must be an object")
        if link.get("from_agent_id") not in agent_ids or link.get("to_agent_id") not in agent_ids:
            raise ValueError("gossip link endpoints must reference nodes")
        if link["from_agent_id"] == link["to_agent_id"]:
            raise ValueError("gossip link endpoints must be distinct")

    max_hop_ttl = int(scenario.get("max_hop_ttl", 2))
    relay_passes = int(scenario.get("relay_passes", 0))
    stale_after_seconds = int(scenario.get("stale_after_seconds", 30))
    if max_hop_ttl < 0 or max_hop_ttl > 8:
        raise ValueError("max_hop_ttl must be between 0 and 8")
    if relay_passes < 0 or relay_passes > 4:
        raise ValueError("relay_passes must be between 0 and 4")
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be positive")


def node_dirs_for(round_dir: Path, agent_ids: list[str]) -> dict[str, NodeDirs]:
    nodes: dict[str, NodeDirs] = {}
    for agent_id in agent_ids:
        root = round_dir / safe_file_part(agent_id)
        nodes[agent_id] = NodeDirs(agent_id=agent_id, inbox=root / "inbox", outbox=root / "outbox")
        nodes[agent_id].inbox.mkdir(parents=True, exist_ok=True)
        nodes[agent_id].outbox.mkdir(parents=True, exist_ok=True)
    return nodes


def envelope_file(prefix: str, envelope: dict[str, Any], source: str | None = None, target: str | None = None) -> str:
    parts = [prefix]
    if source:
        parts.append(source)
    if target:
        parts.append("to")
        parts.append(target)
    parts.append(str(envelope["message_id"]))
    return "-".join(safe_file_part(part) for part in parts) + ".json"


def inbox_envelopes(node: NodeDirs) -> list[dict[str, Any]]:
    envelopes: list[dict[str, Any]] = []
    for path in sorted(node.inbox.glob("*.json")):
        envelopes.append(load_json(path))
    return envelopes


def summarize_node(fleet_id: str, node: NodeDirs) -> dict[str, Any]:
    state = peer_mesh_gossip.GossipState(fleet_id=fleet_id, observer_agent_id=node.agent_id)
    for envelope in inbox_envelopes(node):
        try:
            state.merge_envelope(envelope)
        except ValueError:
            continue
    return state.summary()


def simulate_round(scenario: dict[str, Any], repo_root: Path, output_root: Path) -> dict[str, Any]:
    validate_scenario(scenario)
    repo_root = repo_root.resolve()
    round_id = str(scenario["round_id"])
    fleet_id = str(scenario["fleet_id"])
    round_dir = output_root / safe_file_part(round_id)
    if round_dir.exists() and any(round_dir.iterdir()):
        raise ValueError("round output directory already exists and is not empty")
    round_dir.mkdir(parents=True, exist_ok=True)

    agent_ids = require_agent_list(scenario)
    nodes = node_dirs_for(round_dir, agent_ids)
    max_hop_ttl = int(scenario.get("max_hop_ttl", 2))
    relay_passes = int(scenario.get("relay_passes", 0))
    stale_after_seconds = int(scenario.get("stale_after_seconds", 30))

    initial_envelope_count = 0
    direct_delivery_count = 0
    relayed_envelope_count = 0

    base_envelopes: dict[str, dict[str, Any]] = {}
    for heartbeat_entry in scenario["heartbeats"]:
        agent_id = str(heartbeat_entry["agent_id"])
        heartbeat_path = (repo_root / str(heartbeat_entry["path"])).resolve()
        try:
            heartbeat_path.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError("heartbeat path resolved outside the repository") from exc
        heartbeat = load_json(heartbeat_path)
        if heartbeat.get("fleet_id") != fleet_id or heartbeat.get("agent_id") != agent_id:
            raise ValueError("heartbeat fixture does not match scenario fleet or agent")
        envelope = peer_mesh_gossip.envelope_from_heartbeat(
            heartbeat,
            sender_agent_id=agent_id,
            message_id=f"{round_id}-{agent_id}-heartbeat",
            hop_ttl=max_hop_ttl,
            stale_after_seconds=stale_after_seconds,
        )
        base_envelopes[agent_id] = envelope
        write_json(nodes[agent_id].outbox / envelope_file("outbox", envelope, agent_id), envelope)
        write_json(nodes[agent_id].inbox / envelope_file("self", envelope, agent_id), envelope)
        initial_envelope_count += 1

    for link in scenario["gossip_links"]:
        source = str(link["from_agent_id"])
        target = str(link["to_agent_id"])
        envelope = base_envelopes.get(source)
        if envelope is None:
            continue
        write_json(nodes[target].inbox / envelope_file("direct", envelope, source, target), envelope)
        direct_delivery_count += 1

    for pass_index in range(1, relay_passes + 1):
        inbox_snapshot = {agent_id: inbox_envelopes(node) for agent_id, node in nodes.items()}
        for link in scenario["gossip_links"]:
            source = str(link["from_agent_id"])
            target = str(link["to_agent_id"])
            for envelope in inbox_snapshot[source]:
                if envelope.get("sender_agent_id") == source:
                    continue
                if int(envelope.get("hop_ttl", 0)) <= 0:
                    continue
                relayed = peer_mesh_gossip.relay_envelope(
                    envelope,
                    sender_agent_id=source,
                    message_id=f"{round_id}-{source}-relay-{pass_index}-{envelope['message_id']}",
                )
                write_json(nodes[source].outbox / envelope_file(f"relay-pass-{pass_index}", relayed, source), relayed)
                write_json(
                    nodes[target].inbox / envelope_file(f"relay-pass-{pass_index}", relayed, source, target),
                    relayed,
                )
                relayed_envelope_count += 1

    node_reports = []
    for agent_id in agent_ids:
        node = nodes[agent_id]
        summary = summarize_node(fleet_id, node)
        write_json(node.inbox.parent / "summary.json", summary)
        node_reports.append(
            {
                "agent_id": agent_id,
                "inbox_envelope_count": len(list(node.inbox.glob("*.json"))),
                "outbox_envelope_count": len(list(node.outbox.glob("*.json"))),
                "known_peer_count": summary["known_peer_count"],
                "forbidden_message_count": summary["forbidden_message_count"],
                "summary_file": f"{safe_file_part(agent_id)}/summary.json",
            }
        )

    report = {
        "schema": REPORT_SCHEMA,
        "fleet_id": fleet_id,
        "round_id": round_id,
        "node_count": len(agent_ids),
        "initial_envelope_count": initial_envelope_count,
        "direct_delivery_count": direct_delivery_count,
        "relayed_envelope_count": relayed_envelope_count,
        "relay_passes": relay_passes,
        "nodes": node_reports,
        "authority_boundary": [
            "Round simulation writes synthetic status envelopes only.",
            "It does not open peer sockets, discover devices, run shell commands, use ADB, or relay central commands.",
            "Central direct ADB remains the recovery and privileged truth-check route.",
        ],
    }
    write_json(round_dir / "round-report.json", report)
    return report


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    scenario = load_json(Path(args.scenario))
    report = simulate_round(scenario, repo_root=repo_root, output_root=Path(args.output))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a synthetic peer mesh file-drop round.")
    parser.add_argument("--repo-root", default=".", help="base for scenario-relative fixture paths")
    parser.add_argument("--output", required=True, help="output root; the round_id subdirectory is created below it")
    parser.add_argument("scenario", help="peer mesh round scenario JSON")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
