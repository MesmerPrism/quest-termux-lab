#!/usr/bin/env python3
"""Public-safe readiness gate for a future private peer live lab.

The readiness report evaluates synthetic route-health history against a policy.
It does not probe peers, open sockets, copy files, discover devices, use ADB,
send gossip, launch apps, or approve live work by itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_gossip
import peer_mesh_route_health
import peer_mesh_route_history


READINESS_POLICY_SCHEMA = "quest-termux-lab.peer-live-lab-readiness-policy.v1"
READINESS_REPORT_SCHEMA = "quest-termux-lab.peer-live-lab-readiness-report.v1"
EXPERIMENT_SCOPES = {"private_configured_peer_gossip_only"}
CHECK_STATUSES = {"passed", "failed", "manual_review"}
OVERALL_STATUSES = {"ready", "manual_review", "not_ready"}
HISTORY_SUMMARY_FIELDS = [
    "tracked_route_count",
    "last_unavailable_count",
    "last_disabled_count",
    "last_unknown_count",
    "worsening_count",
]


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


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != READINESS_POLICY_SCHEMA:
        raise ValueError("unsupported readiness policy schema")
    if peer_mesh_gossip.contains_forbidden_key(policy):
        raise ValueError("readiness policy contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "min_history_reports",
        "min_tracked_routes",
        "allowed_last_statuses",
        "acceptable_trends",
        "require_no_unavailable_routes",
        "require_no_unknown_routes",
        "require_no_disabled_routes",
        "require_no_worsening_routes",
        "operator_approval_required",
    ]:
        if key not in policy:
            raise ValueError(f"readiness policy missing {key}")
    if policy["experiment_scope"] not in EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    for key in ["min_history_reports", "min_tracked_routes"]:
        if not isinstance(policy[key], int) or policy[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    for key in [
        "require_no_unavailable_routes",
        "require_no_unknown_routes",
        "require_no_disabled_routes",
        "require_no_worsening_routes",
        "operator_approval_required",
    ]:
        if not isinstance(policy[key], bool):
            raise ValueError(f"{key} must be boolean")
    if not isinstance(policy["allowed_last_statuses"], list) or not policy["allowed_last_statuses"]:
        raise ValueError("allowed_last_statuses must be a non-empty array")
    for status in policy["allowed_last_statuses"]:
        if status not in peer_mesh_route_health.ROUTE_STATUSES:
            raise ValueError("unsupported allowed route status")
    if not isinstance(policy["acceptable_trends"], list) or not policy["acceptable_trends"]:
        raise ValueError("acceptable_trends must be a non-empty array")
    for trend in policy["acceptable_trends"]:
        if trend not in peer_mesh_route_history.TREND_VALUES:
            raise ValueError("unsupported acceptable trend")


def validate_history(history: dict[str, Any]) -> None:
    if history.get("schema") != peer_mesh_route_history.ROUTE_HISTORY_SCHEMA:
        raise ValueError("unsupported route-health history schema")
    if peer_mesh_gossip.contains_forbidden_key(history):
        raise ValueError("route-health history contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "report_count", "routes", "summary"]:
        if key not in history:
            raise ValueError(f"route-health history missing {key}")
    if not isinstance(history["report_count"], int) or history["report_count"] < 1:
        raise ValueError("route-health history report_count must be a positive integer")
    if not isinstance(history["routes"], list):
        raise ValueError("route-health history routes must be an array")
    summary = history["summary"]
    if not isinstance(summary, dict):
        raise ValueError("route-health history summary must be an object")
    for key in HISTORY_SUMMARY_FIELDS:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"route-health history summary missing non-negative {key}")
    for route in history["routes"]:
        if not isinstance(route, dict):
            raise ValueError("route-health history route must be an object")
        for key in ["target_agent_id", "last_status", "trend", "sample_count", "last_reason"]:
            if key not in route:
                raise ValueError(f"route-health history route missing {key}")
        if route["last_status"] not in peer_mesh_route_health.ROUTE_STATUSES:
            raise ValueError("unsupported route last_status")
        if route["trend"] not in peer_mesh_route_history.TREND_VALUES:
            raise ValueError("unsupported route trend")
        if not isinstance(route["sample_count"], int) or route["sample_count"] < 1:
            raise ValueError("route-health history route sample_count must be a positive integer")


def check_entry(check_id: str, passed: bool, expected: str, observed: str, reason: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "passed" if passed else "failed",
        "expected": expected,
        "observed": observed,
        "reason": reason,
    }


def manual_check(check_id: str, expected: str, observed: str, reason: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "manual_review",
        "expected": expected,
        "observed": observed,
        "reason": reason,
    }


def route_review(route: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    status = "ready"
    last_status = str(route["last_status"])
    trend = str(route["trend"])
    if last_status not in policy["allowed_last_statuses"]:
        status = "not_ready"
        reasons.append(f"last status {last_status} is not allowed")
    if trend not in policy["acceptable_trends"]:
        status = "not_ready"
        reasons.append(f"trend {trend} is not acceptable")
    if policy["require_no_worsening_routes"] and trend == "worsening":
        status = "not_ready"
        reasons.append("worsening routes are disallowed")
    if not reasons:
        reasons.append("route satisfies synthetic readiness policy")
    return {
        "target_agent_id": route["target_agent_id"],
        "last_status": last_status,
        "trend": trend,
        "sample_count": int(route["sample_count"]),
        "readiness_status": status,
        "reason": "; ".join(reasons),
    }


def summarize(checks: list[dict[str, Any]], routes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "route_count": len(routes),
        "ready_route_count": sum(1 for route in routes if route["readiness_status"] == "ready"),
        "not_ready_route_count": sum(1 for route in routes if route["readiness_status"] == "not_ready"),
    }


def overall_status(checks: list[dict[str, Any]], routes: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "not_ready"
    if any(route["readiness_status"] == "not_ready" for route in routes):
        return "not_ready"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "ready"


def build_readiness_report(
    policy: dict[str, Any],
    history: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    validate_history(history)
    if policy["fleet_id"] != history["fleet_id"]:
        raise ValueError("readiness fleet_id mismatch")
    if policy["source_agent_id"] != history["source_agent_id"]:
        raise ValueError("readiness source_agent_id mismatch")

    summary = history["summary"]
    checks = [
        check_entry(
            "history_report_count",
            int(history["report_count"]) >= int(policy["min_history_reports"]),
            f">= {policy['min_history_reports']} route-health reports",
            str(history["report_count"]),
            "route-health history sample count",
        ),
        check_entry(
            "tracked_route_count",
            int(summary["tracked_route_count"]) >= int(policy["min_tracked_routes"]),
            f">= {policy['min_tracked_routes']} tracked routes",
            str(summary["tracked_route_count"]),
            "tracked configured route count",
        ),
    ]
    if policy["require_no_unavailable_routes"]:
        checks.append(
            check_entry(
                "no_unavailable_routes",
                int(summary["last_unavailable_count"]) == 0,
                "0 unavailable routes",
                str(summary["last_unavailable_count"]),
                "latest route-health status must not be unavailable",
            )
        )
    if policy["require_no_unknown_routes"]:
        checks.append(
            check_entry(
                "no_unknown_routes",
                int(summary["last_unknown_count"]) == 0,
                "0 unknown routes",
                str(summary["last_unknown_count"]),
                "every configured route needs synthetic evidence before live lab work",
            )
        )
    if policy["require_no_disabled_routes"]:
        checks.append(
            check_entry(
                "no_disabled_routes",
                int(summary["last_disabled_count"]) == 0,
                "0 disabled routes",
                str(summary["last_disabled_count"]),
                "disabled routes should be removed or intentionally excluded before live lab work",
            )
        )
    if policy["require_no_worsening_routes"]:
        checks.append(
            check_entry(
                "no_worsening_routes",
                int(summary["worsening_count"]) == 0,
                "0 worsening routes",
                str(summary["worsening_count"]),
                "route-health trend must not be worsening",
            )
        )
    route_reviews = [route_review(route, policy) for route in history["routes"]]
    if policy["operator_approval_required"]:
        checks.append(
            manual_check(
                "operator_approval",
                "explicit operator approval before live LAN peer experiment",
                "not represented in public synthetic evidence",
                "this public report cannot grant live-device or LAN approval",
            )
        )

    observed_at = now_text or str(policy["observed_at"])
    status = overall_status(checks, route_reviews)
    return {
        "schema": READINESS_REPORT_SCHEMA,
        "fleet_id": history["fleet_id"],
        "source_agent_id": history["source_agent_id"],
        "observed_at": observed_at,
        "experiment_scope": policy["experiment_scope"],
        "overall_status": status,
        "checks": checks,
        "routes": route_reviews,
        "summary": summarize(checks, route_reviews),
        "authority_boundary": [
            "Live-lab readiness reports evaluate synthetic peer-mesh evidence only.",
            "Readiness reports do not approve live work, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Readiness reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    policy = load_json(Path(args.policy))
    history = load_json(Path(args.history))
    write_json(args.output, build_readiness_report(policy, history, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer live-lab readiness report.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
