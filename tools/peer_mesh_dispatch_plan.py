#!/usr/bin/env python3
"""Public-safe configured-peer dispatch-plan simulator.

This tool plans sender-side gossip dispatch from delivery state and route
configuration. It does not open sockets, copy files, discover peers, carry
commands, use ADB, or send gossip.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import peer_mesh_delivery
import peer_mesh_gossip


ROUTE_CONFIG_SCHEMA = "quest-termux-lab.peer-route-config.v1"
DISPATCH_PLAN_SCHEMA = "quest-termux-lab.peer-dispatch-plan.v1"
MESSAGE_SCHEMA = "quest-termux-lab.peer-gossip-envelope.v1"
TRANSPORT_MODES = {"file_drop_simulator", "loopback_http_simulator", "disabled"}
DECISIONS = {"ready", "skipped_terminal", "expired", "missing_route", "route_disabled"}


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


def validate_relative_path(value: str, label: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be relative and stay inside the run root")


def validate_route_config(config: dict[str, Any]) -> None:
    if config.get("schema") != ROUTE_CONFIG_SCHEMA:
        raise ValueError("unsupported route config schema")
    if peer_mesh_gossip.contains_forbidden_key(config):
        raise ValueError("route config contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "routes"]:
        if key not in config:
            raise ValueError(f"route config missing {key}")
    if not isinstance(config["routes"], list):
        raise ValueError("routes must be an array")
    seen_targets: set[str] = set()
    for route in config["routes"]:
        if not isinstance(route, dict):
            raise ValueError("route must be an object")
        for key in ["target_agent_id", "transport_mode"]:
            if not isinstance(route.get(key), str) or not route[key]:
                raise ValueError(f"route missing {key}")
        if route["target_agent_id"] in seen_targets:
            raise ValueError("duplicate target_agent_id in routes")
        seen_targets.add(route["target_agent_id"])
        if route["transport_mode"] not in TRANSPORT_MODES:
            raise ValueError("unsupported transport_mode")
        if route["transport_mode"] == "loopback_http_simulator":
            endpoint = route.get("gossip_endpoint")
            if not isinstance(endpoint, str) or not endpoint:
                raise ValueError("loopback route missing gossip_endpoint")
            parsed = urlparse(endpoint)
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
                raise ValueError("loopback route must use http://127.0.0.1")
        if route["transport_mode"] == "file_drop_simulator":
            drop_dir = route.get("target_inbox_dir")
            if not isinstance(drop_dir, str) or not drop_dir:
                raise ValueError("file-drop route missing target_inbox_dir")
            validate_relative_path(drop_dir, "target_inbox_dir")


def route_by_target(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(route["target_agent_id"]): dict(route) for route in config["routes"]}


def dispatch_entry(
    delivery: dict[str, Any],
    decision: str,
    route: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError("unsupported dispatch decision")
    transport_mode = "none"
    route_target = None
    method = "none"
    if route is not None:
        transport_mode = str(route["transport_mode"])
        if transport_mode == "loopback_http_simulator":
            route_target = route["gossip_endpoint"]
            method = "post_gossip"
        elif transport_mode == "file_drop_simulator":
            route_target = route["target_inbox_dir"]
            method = "copy_envelope"
        elif transport_mode == "disabled":
            method = "none"
    return {
        "delivery_id": delivery["delivery_id"],
        "target_agent_id": delivery["target_agent_id"],
        "message_id": delivery["message_id"],
        "delivery_state": delivery["state"],
        "decision": decision,
        "transport_mode": transport_mode,
        "method": method,
        "route_target": route_target,
        "message_schema": MESSAGE_SCHEMA,
        "attempt_count": delivery["attempt_count"],
        "expires_at": delivery["expires_at"],
        "reason": reason,
    }


def summarize(dispatches: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {decision: 0 for decision in DECISIONS}
    for dispatch in dispatches:
        counts[str(dispatch["decision"])] += 1
    return {
        "dispatch_count": len(dispatches),
        "ready_count": counts["ready"],
        "skipped_terminal_count": counts["skipped_terminal"],
        "expired_count": counts["expired"],
        "missing_route_count": counts["missing_route"],
        "route_disabled_count": counts["route_disabled"],
    }


def build_dispatch_plan(
    delivery_state: dict[str, Any],
    route_config: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    peer_mesh_delivery.validate_state(delivery_state)
    validate_route_config(route_config)
    if route_config["fleet_id"] != delivery_state["fleet_id"]:
        raise ValueError("route config fleet_id mismatch")
    if route_config["source_agent_id"] != delivery_state["source_agent_id"]:
        raise ValueError("route config source_agent_id mismatch")

    observed_at = now_text or peer_mesh_gossip.utc_now()
    refreshed = peer_mesh_delivery.expire_pending(delivery_state, now_text=observed_at)
    routes = route_by_target(route_config)
    dispatches: list[dict[str, Any]] = []
    for delivery in refreshed["deliveries"]:
        route = routes.get(str(delivery["target_agent_id"]))
        if delivery["state"] == "expired":
            dispatches.append(dispatch_entry(delivery, "expired", route=route, reason="delivery expired"))
            continue
        if delivery["state"] in peer_mesh_delivery.TERMINAL_STATES:
            dispatches.append(dispatch_entry(delivery, "skipped_terminal", route=route, reason="delivery already terminal"))
            continue
        if route is None:
            dispatches.append(dispatch_entry(delivery, "missing_route", reason="no configured route for target"))
            continue
        if route["transport_mode"] == "disabled":
            dispatches.append(dispatch_entry(delivery, "route_disabled", route=route, reason="route disabled"))
            continue
        dispatches.append(dispatch_entry(delivery, "ready", route=route, reason=None))

    return {
        "schema": DISPATCH_PLAN_SCHEMA,
        "fleet_id": refreshed["fleet_id"],
        "source_agent_id": refreshed["source_agent_id"],
        "observed_at": observed_at,
        "route_count": len(routes),
        "dispatches": dispatches,
        "summary": summarize(dispatches),
        "authority_boundary": [
            "Dispatch plans describe intended gossip delivery only.",
            "Dispatch plans do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
            "This simulator does not open sockets, copy files, discover peers, or send gossip.",
        ],
    }


def run_plan(args: argparse.Namespace) -> int:
    state = load_json(Path(args.delivery_state))
    config = load_json(Path(args.route_config))
    write_json(args.output, build_dispatch_plan(state, config, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer gossip dispatch plan.")
    parser.add_argument("--route-config", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    parser.add_argument("delivery_state")
    args = parser.parse_args(argv)
    return run_plan(args)


if __name__ == "__main__":
    sys.exit(main())
