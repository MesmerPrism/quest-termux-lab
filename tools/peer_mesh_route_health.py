#!/usr/bin/env python3
"""Public-safe peer route-health inference.

The route-health report combines configured routes with synthetic send dry-run
and retry-plan evidence. It does not probe peers, open sockets, copy files,
discover devices, use ADB, or send gossip.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_dispatch_plan
import peer_mesh_gossip
import peer_mesh_retry_plan
import peer_mesh_send_dry_run


ROUTE_HEALTH_REPORT_SCHEMA = "quest-termux-lab.peer-route-health-report.v1"
ROUTE_STATUSES = {"healthy", "degraded", "unavailable", "disabled", "unknown"}
ACTION_OUTCOMES = {"accepted", "duplicate", "rejected", "no_response", "not_sent"}
RETRY_DECISIONS = {
    "due_now",
    "waiting_backoff",
    "max_attempts_reached",
    "non_retryable_error",
    "expired",
    "terminal",
}


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


def validate_send_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_send_dry_run.REPORT_SCHEMA:
        raise ValueError("unsupported send dry-run report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("send dry-run report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "actions"]:
        if key not in report:
            raise ValueError(f"send dry-run report missing {key}")
    if not isinstance(report["actions"], list):
        raise ValueError("send dry-run actions must be an array")
    for action in report["actions"]:
        if not isinstance(action, dict):
            raise ValueError("send dry-run action must be an object")
        for key in ["target_agent_id", "message_id", "simulated_outcome", "dispatch_decision"]:
            if not isinstance(action.get(key), str) or not action[key]:
                raise ValueError(f"send dry-run action missing {key}")
        if action["simulated_outcome"] not in ACTION_OUTCOMES:
            raise ValueError("unsupported simulated outcome")


def validate_retry_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema") != peer_mesh_retry_plan.RETRY_PLAN_SCHEMA:
        raise ValueError("unsupported retry plan schema")
    if peer_mesh_gossip.contains_forbidden_key(plan):
        raise ValueError("retry plan contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "retries"]:
        if key not in plan:
            raise ValueError(f"retry plan missing {key}")
    if not isinstance(plan["retries"], list):
        raise ValueError("retry entries must be an array")
    for retry in plan["retries"]:
        if not isinstance(retry, dict):
            raise ValueError("retry entry must be an object")
        for key in ["target_agent_id", "message_id", "delivery_state", "decision"]:
            if not isinstance(retry.get(key), str) or not retry[key]:
                raise ValueError(f"retry entry missing {key}")
        if retry["decision"] not in RETRY_DECISIONS:
            raise ValueError("unsupported retry decision")


def latest_by_target(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        latest[str(entry["target_agent_id"])] = dict(entry)
    return latest


def status_from_action(action: dict[str, Any], retry: dict[str, Any] | None) -> tuple[str, str]:
    outcome = str(action["simulated_outcome"])
    delivery_state = str(action.get("delivery_state_after", "pending"))
    dispatch_decision = str(action["dispatch_decision"])
    if outcome in {"accepted", "duplicate"}:
        return "healthy", f"synthetic delivery {outcome}"
    if outcome == "no_response":
        if retry is not None and retry["decision"] in {
            "max_attempts_reached",
            "non_retryable_error",
            "expired",
        }:
            return "unavailable", f"no response and retry decision {retry['decision']}"
        return "degraded", "synthetic no response"
    if outcome == "rejected":
        if retry is not None and retry["decision"] in {"due_now", "waiting_backoff"}:
            return "degraded", "synthetic rejection with retry still allowed"
        return "unavailable", "synthetic rejection"
    if outcome == "not_sent":
        if dispatch_decision == "route_disabled":
            return "disabled", "route disabled"
        if delivery_state in {"accepted", "duplicate"}:
            return "healthy", f"delivery already terminal {delivery_state}"
        if delivery_state in {"rejected", "expired"}:
            return "unavailable", f"delivery already terminal {delivery_state}"
        return "unknown", f"not sent because {dispatch_decision}"
    return "unknown", "no recognized synthetic outcome"


def status_from_retry(retry: dict[str, Any] | None) -> tuple[str, str]:
    if retry is None:
        return "unknown", "no send or retry evidence for route"
    decision = str(retry["decision"])
    delivery_state = str(retry["delivery_state"])
    if decision in {"due_now", "waiting_backoff"}:
        return "degraded", f"pending delivery {decision}"
    if decision in {"max_attempts_reached", "non_retryable_error", "expired"}:
        return "unavailable", f"retry decision {decision}"
    if decision == "terminal":
        if delivery_state in {"accepted", "duplicate"}:
            return "healthy", f"delivery already terminal {delivery_state}"
        return "unavailable", f"delivery already terminal {delivery_state}"
    return "unknown", "no recognized retry decision"


def route_entry(
    route: dict[str, Any],
    action: dict[str, Any] | None,
    retry: dict[str, Any] | None,
) -> dict[str, Any]:
    if route["transport_mode"] == "disabled":
        status = "disabled"
        reason = "route disabled"
    elif action is not None:
        status, reason = status_from_action(action, retry)
    else:
        status, reason = status_from_retry(retry)
    if status not in ROUTE_STATUSES:
        raise ValueError("unsupported route status")
    return {
        "target_agent_id": route["target_agent_id"],
        "transport_mode": route["transport_mode"],
        "status": status,
        "latest_simulated_outcome": action.get("simulated_outcome") if action is not None else None,
        "retry_decision": retry.get("decision") if retry is not None else None,
        "retry_next_attempt_at": retry.get("next_attempt_at") if retry is not None else None,
        "message_id": action.get("message_id") if action is not None else retry.get("message_id") if retry is not None else None,
        "last_error": retry.get("last_error") if retry is not None else None,
        "reason": reason,
    }


def summarize(routes: list[dict[str, Any]], unconfigured_actions: int, unconfigured_retries: int) -> dict[str, Any]:
    counts = {status: 0 for status in ROUTE_STATUSES}
    for route in routes:
        counts[str(route["status"])] += 1
    return {
        "route_count": len(routes),
        "healthy_count": counts["healthy"],
        "degraded_count": counts["degraded"],
        "unavailable_count": counts["unavailable"],
        "disabled_count": counts["disabled"],
        "unknown_count": counts["unknown"],
        "unconfigured_action_count": unconfigured_actions,
        "unconfigured_retry_count": unconfigured_retries,
    }


def build_route_health_report(
    route_config: dict[str, Any],
    send_report: dict[str, Any] | None = None,
    retry_plan: dict[str, Any] | None = None,
    now_text: str | None = None,
) -> dict[str, Any]:
    peer_mesh_dispatch_plan.validate_route_config(route_config)
    if send_report is not None:
        validate_send_report(send_report)
    if retry_plan is not None:
        validate_retry_plan(retry_plan)
    for evidence in [send_report, retry_plan]:
        if evidence is None:
            continue
        if evidence["fleet_id"] != route_config["fleet_id"]:
            raise ValueError("route health evidence fleet_id mismatch")
        if evidence["source_agent_id"] != route_config["source_agent_id"]:
            raise ValueError("route health evidence source_agent_id mismatch")

    observed_at = (
        now_text
        or (send_report.get("observed_at") if send_report is not None else None)
        or (retry_plan.get("observed_at") if retry_plan is not None else None)
        or peer_mesh_gossip.utc_now()
    )
    actions = latest_by_target(send_report["actions"]) if send_report is not None else {}
    retries = latest_by_target(retry_plan["retries"]) if retry_plan is not None else {}
    configured_targets = {str(route["target_agent_id"]) for route in route_config["routes"]}
    routes = [
        route_entry(route, actions.get(str(route["target_agent_id"])), retries.get(str(route["target_agent_id"])))
        for route in route_config["routes"]
    ]
    unconfigured_actions = len(set(actions) - configured_targets)
    unconfigured_retries = len(set(retries) - configured_targets)
    return {
        "schema": ROUTE_HEALTH_REPORT_SCHEMA,
        "fleet_id": route_config["fleet_id"],
        "source_agent_id": route_config["source_agent_id"],
        "observed_at": observed_at,
        "routes": routes,
        "summary": summarize(routes, unconfigured_actions, unconfigured_retries),
        "authority_boundary": [
            "Route-health reports infer configured gossip route status from synthetic dry-run evidence only.",
            "Route-health reports do not probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Route-health reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    route_config = load_json(Path(args.route_config))
    send_report = load_json(Path(args.send_report)) if args.send_report else None
    retry_plan = load_json(Path(args.retry_plan)) if args.retry_plan else None
    write_json(
        args.output,
        build_route_health_report(
            route_config,
            send_report=send_report,
            retry_plan=retry_plan,
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer route-health report.")
    parser.add_argument("--route-config", required=True)
    parser.add_argument("--send-report", default="")
    parser.add_argument("--retry-plan", default="")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
