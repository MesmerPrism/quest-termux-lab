#!/usr/bin/env python3
"""Public-safe peer route-health history summarizer.

The history report aggregates synthetic route-health reports. It does not
probe peers, open sockets, copy files, discover devices, use ADB, send gossip,
or carry command payloads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_gossip
import peer_mesh_route_health


ROUTE_HISTORY_SCHEMA = "quest-termux-lab.peer-route-health-history.v1"
TREND_VALUES = {"stable", "improving", "worsening", "mixed", "single_sample"}
STATUS_SCORE = {
    "disabled": 0,
    "unavailable": 1,
    "unknown": 2,
    "degraded": 3,
    "healthy": 4,
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


def validate_health_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_route_health.ROUTE_HEALTH_REPORT_SCHEMA:
        raise ValueError("unsupported route-health report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("route-health report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "routes"]:
        if key not in report:
            raise ValueError(f"route-health report missing {key}")
    if not isinstance(report["routes"], list):
        raise ValueError("route-health routes must be an array")
    for route in report["routes"]:
        if not isinstance(route, dict):
            raise ValueError("route-health route must be an object")
        for key in ["target_agent_id", "transport_mode", "status"]:
            if not isinstance(route.get(key), str) or not route[key]:
                raise ValueError(f"route-health route missing {key}")
        if route["status"] not in peer_mesh_route_health.ROUTE_STATUSES:
            raise ValueError("unsupported route status")


def sort_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(reports, key=lambda report: peer_mesh_gossip.parse_time(str(report["observed_at"])))


def trend_for(statuses: list[str]) -> str:
    if len(statuses) <= 1:
        return "single_sample"
    first = STATUS_SCORE[statuses[0]]
    last = STATUS_SCORE[statuses[-1]]
    unique = set(statuses)
    if len(unique) == 1:
        return "stable"
    if last > first:
        return "improving"
    if last < first:
        return "worsening"
    return "mixed"


def route_history_entry(target_agent_id: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(sample["status"]) for sample in samples]
    status_counts = {status: 0 for status in sorted(peer_mesh_route_health.ROUTE_STATUSES)}
    transition_count = 0
    previous_status = None
    for status in statuses:
        status_counts[status] += 1
        if previous_status is not None and previous_status != status:
            transition_count += 1
        previous_status = status
    first = samples[0]
    last = samples[-1]
    return {
        "target_agent_id": target_agent_id,
        "transport_mode": str(last["transport_mode"]),
        "sample_count": len(samples),
        "first_observed_at": str(first["observed_at"]),
        "last_observed_at": str(last["observed_at"]),
        "first_status": str(first["status"]),
        "last_status": str(last["status"]),
        "trend": trend_for(statuses),
        "status_counts": status_counts,
        "transition_count": transition_count,
        "last_reason": str(last["reason"]),
    }


def summarize_routes(routes: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {status: 0 for status in sorted(peer_mesh_route_health.ROUTE_STATUSES)}
    trend_counts = {trend: 0 for trend in sorted(TREND_VALUES)}
    for route in routes:
        counts[str(route["last_status"])] += 1
        trend_counts[str(route["trend"])] += 1
    return {
        "tracked_route_count": len(routes),
        "last_healthy_count": counts["healthy"],
        "last_degraded_count": counts["degraded"],
        "last_unavailable_count": counts["unavailable"],
        "last_disabled_count": counts["disabled"],
        "last_unknown_count": counts["unknown"],
        "stable_count": trend_counts["stable"],
        "improving_count": trend_counts["improving"],
        "worsening_count": trend_counts["worsening"],
        "mixed_count": trend_counts["mixed"],
        "single_sample_count": trend_counts["single_sample"],
    }


def build_history(
    reports: list[dict[str, Any]],
    now_text: str | None = None,
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one route-health report is required")
    for report in reports:
        validate_health_report(report)
    first_report = reports[0]
    for report in reports[1:]:
        if report["fleet_id"] != first_report["fleet_id"]:
            raise ValueError("route-health report fleet_id mismatch")
        if report["source_agent_id"] != first_report["source_agent_id"]:
            raise ValueError("route-health report source_agent_id mismatch")

    ordered = sort_reports(reports)
    samples_by_target: dict[str, list[dict[str, Any]]] = {}
    for report in ordered:
        observed_at = str(report["observed_at"])
        for route in report["routes"]:
            sample = dict(route)
            sample["observed_at"] = observed_at
            samples_by_target.setdefault(str(route["target_agent_id"]), []).append(sample)
    route_histories = [
        route_history_entry(target, samples_by_target[target])
        for target in sorted(samples_by_target)
    ]
    observed_at = now_text or str(ordered[-1]["observed_at"])
    return {
        "schema": ROUTE_HISTORY_SCHEMA,
        "fleet_id": first_report["fleet_id"],
        "source_agent_id": first_report["source_agent_id"],
        "observed_at": observed_at,
        "report_count": len(ordered),
        "first_report_at": str(ordered[0]["observed_at"]),
        "last_report_at": str(ordered[-1]["observed_at"]),
        "routes": route_histories,
        "summary": summarize_routes(route_histories),
        "authority_boundary": [
            "Route-health history aggregates synthetic route-health reports only.",
            "Route-health history does not probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Route-health history does not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    reports = [load_json(Path(path)) for path in args.reports]
    write_json(args.output, build_history(reports, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer route-health history report.")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    parser.add_argument("reports", nargs="+")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
