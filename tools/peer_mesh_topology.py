#!/usr/bin/env python3
"""Public-safe peer topology coverage analysis.

The topology report consumes configured peer routes and synthetic route-health
evidence to summarize whether an expected peer set is reachable from one
source agent. It does not probe peers, discover devices, open sockets, copy
files, send gossip, use ADB, launch apps, execute commands, or execute
validation slots.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_dispatch_plan
import peer_mesh_gossip
import peer_mesh_live_lab_readiness
import peer_mesh_route_health


TOPOLOGY_MANIFEST_SCHEMA = "quest-termux-lab.peer-topology-manifest.v1"
TOPOLOGY_REPORT_SCHEMA = "quest-termux-lab.peer-topology-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
TOPOLOGY_STATUSES = {"topology_ready", "manual_review", "topology_blocked"}
REACHABILITY_STATUSES = {
    "reachable",
    "degraded",
    "unreachable",
    "disabled",
    "unknown",
    "missing_health",
    "missing_route",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def write_json(path_text: str, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, sort_keys=True)
    if path_text == "-":
        print(text)
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def validate_report_path(value: str, label: str) -> None:
    peer_mesh_dispatch_plan.validate_relative_path(value, label)
    if Path(value).suffix.lower() != ".json":
        raise ValueError(f"{label} must reference a json file")


def validate_text_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        result.append(item)
    if len(result) != len(set(result)):
        raise ValueError(f"{label} entries must be unique")
    return result


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != TOPOLOGY_MANIFEST_SCHEMA:
        raise ValueError("unsupported peer topology manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("peer topology manifest contains command-like or credential-like fields")
    for key in [
        "topology_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "expected_agent_ids",
        "route_config_path",
        "route_health_report_path",
        "require_all_expected_routes",
        "require_no_unhealthy_routes",
        "min_healthy_route_count",
        "min_reachable_agent_count",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"peer topology manifest missing {key}")
    for key in ["topology_id", "fleet_id", "source_agent_id", "observed_at", "route_config_path", "route_health_report_path"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"peer topology manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    agents = validate_text_array(manifest["expected_agent_ids"], "expected_agent_ids")
    if manifest["source_agent_id"] not in agents:
        raise ValueError("expected_agent_ids must include source_agent_id")
    validate_report_path(str(manifest["route_config_path"]), "route_config_path")
    validate_report_path(str(manifest["route_health_report_path"]), "route_health_report_path")
    for key in ["require_all_expected_routes", "require_no_unhealthy_routes"]:
        if not isinstance(manifest[key], bool):
            raise ValueError(f"{key} must be boolean")
    for key in ["min_healthy_route_count", "min_reachable_agent_count"]:
        if not isinstance(manifest[key], int) or manifest[key] < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    boundary = validate_text_array(manifest["authority_boundary"], "authority_boundary")
    if not boundary:
        raise ValueError("authority_boundary must not be empty")


def validate_route_health_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_route_health.ROUTE_HEALTH_REPORT_SCHEMA:
        raise ValueError("unsupported route-health report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("route-health report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "routes", "summary"]:
        if key not in report:
            raise ValueError(f"route-health report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"route-health report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if not isinstance(report["routes"], list):
        raise ValueError("route-health routes must be an array")
    seen_targets: set[str] = set()
    for route in report["routes"]:
        if not isinstance(route, dict):
            raise ValueError("route-health route must be an object")
        for key in ["target_agent_id", "transport_mode", "status", "reason"]:
            if not isinstance(route.get(key), str) or not route[key]:
                raise ValueError(f"route-health route missing {key}")
        if route["target_agent_id"] in seen_targets:
            raise ValueError("duplicate target_agent_id in route-health routes")
        seen_targets.add(route["target_agent_id"])
        if route["transport_mode"] not in peer_mesh_dispatch_plan.TRANSPORT_MODES:
            raise ValueError("unsupported route-health transport_mode")
        if route["status"] not in peer_mesh_route_health.ROUTE_STATUSES:
            raise ValueError("unsupported route-health status")


def validate_topology_report(report: dict[str, Any]) -> None:
    if report.get("schema") != TOPOLOGY_REPORT_SCHEMA:
        raise ValueError("unsupported peer topology report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("peer topology report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "topology_id",
        "experiment_scope",
        "overall_status",
        "checks",
        "expected_agent_ids",
        "edges",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"peer topology report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "topology_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"peer topology report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["overall_status"] not in TOPOLOGY_STATUSES:
        raise ValueError("unsupported topology status")
    validate_text_array(report["expected_agent_ids"], "expected_agent_ids")
    if not isinstance(report["checks"], list):
        raise ValueError("topology checks must be an array")
    for check in report["checks"]:
        if not isinstance(check, dict):
            raise ValueError("topology check must be an object")
        for key in ["check_id", "status", "observed", "threshold", "reason"]:
            if key not in check:
                raise ValueError(f"topology check missing {key}")
        if check["status"] not in CHECK_STATUSES:
            raise ValueError("unsupported topology check status")
    if not isinstance(report["edges"], list):
        raise ValueError("topology edges must be an array")
    for edge in report["edges"]:
        if not isinstance(edge, dict):
            raise ValueError("topology edge must be an object")
        for key in ["source_agent_id", "target_agent_id", "configured", "transport_mode", "reachability_status", "reason"]:
            if key not in edge:
                raise ValueError(f"topology edge missing {key}")
        if not isinstance(edge["configured"], bool):
            raise ValueError("topology edge configured must be boolean")
        if edge["transport_mode"] not in {"file_drop_simulator", "loopback_http_simulator", "disabled", "none"}:
            raise ValueError("unsupported topology transport_mode")
        if edge["reachability_status"] not in REACHABILITY_STATUSES:
            raise ValueError("unsupported topology reachability status")
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise ValueError("topology summary must be an object")
    for key in [
        "expected_agent_count",
        "expected_target_count",
        "edge_count",
        "configured_edge_count",
        "missing_route_count",
        "missing_health_count",
        "reachable_edge_count",
        "degraded_edge_count",
        "unreachable_edge_count",
        "reachable_agent_count",
        "non_ready_edge_count",
    ]:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"topology summary missing non-negative {key}")


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported peer topology check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def identity_checks(
    manifest: dict[str, Any],
    route_config: dict[str, Any],
    route_health_report: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = []
    for check_id, document in [("route_config_identity", route_config), ("route_health_identity", route_health_report)]:
        mismatches = []
        for key in ["fleet_id", "source_agent_id"]:
            if document.get(key) != manifest[key]:
                mismatches.append(key)
        if mismatches:
            checks.append(check_entry(check_id, "failed", ",".join(mismatches), "match", f"{check_id} does not match topology manifest"))
        else:
            checks.append(check_entry(check_id, "passed", "match", "match", f"{check_id} matches topology manifest"))
    return checks


def route_config_by_target(route_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(route["target_agent_id"]): dict(route) for route in route_config["routes"]}


def route_health_by_target(route_health_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(route["target_agent_id"]): dict(route) for route in route_health_report["routes"]}


def reachability_for(route: dict[str, Any] | None, health: dict[str, Any] | None) -> tuple[str, str, str]:
    if route is None:
        return "none", "missing_route", "no configured route for expected target"
    transport_mode = str(route["transport_mode"])
    if health is None:
        return transport_mode, "missing_health", "configured route has no route-health evidence"
    health_status = str(health["status"])
    if health_status == "healthy":
        return transport_mode, "reachable", "route-health status is healthy"
    if health_status == "degraded":
        return transport_mode, "degraded", "route-health status is degraded"
    if health_status == "unavailable":
        return transport_mode, "unreachable", "route-health status is unavailable"
    if health_status == "disabled":
        return transport_mode, "disabled", "route-health status is disabled"
    return transport_mode, "unknown", "route-health status is unknown"


def topology_edges(
    manifest: dict[str, Any],
    route_config: dict[str, Any],
    route_health_report: dict[str, Any],
) -> list[dict[str, Any]]:
    routes = route_config_by_target(route_config)
    health = route_health_by_target(route_health_report)
    edges = []
    for target_agent_id in sorted(agent for agent in manifest["expected_agent_ids"] if agent != manifest["source_agent_id"]):
        route = routes.get(str(target_agent_id))
        health_entry = health.get(str(target_agent_id))
        transport_mode, reachability_status, reason = reachability_for(route, health_entry)
        if reachability_status not in REACHABILITY_STATUSES:
            raise ValueError("unsupported reachability status")
        edges.append(
            {
                "source_agent_id": manifest["source_agent_id"],
                "target_agent_id": target_agent_id,
                "configured": route is not None,
                "transport_mode": transport_mode,
                "route_health_status": health_entry.get("status") if health_entry is not None else None,
                "reachability_status": reachability_status,
                "reason": reason,
            }
        )
    return edges


def summarize(manifest: dict[str, Any], edges: list[dict[str, Any]]) -> dict[str, Any]:
    missing_route_count = sum(1 for edge in edges if edge["reachability_status"] == "missing_route")
    missing_health_count = sum(1 for edge in edges if edge["reachability_status"] == "missing_health")
    reachable_edge_count = sum(1 for edge in edges if edge["reachability_status"] == "reachable")
    degraded_edge_count = sum(1 for edge in edges if edge["reachability_status"] == "degraded")
    unreachable_edge_count = sum(1 for edge in edges if edge["reachability_status"] in {"unreachable", "disabled", "unknown"})
    return {
        "expected_agent_count": len(manifest["expected_agent_ids"]),
        "expected_target_count": max(len(manifest["expected_agent_ids"]) - 1, 0),
        "edge_count": len(edges),
        "configured_edge_count": sum(1 for edge in edges if edge["configured"]),
        "missing_route_count": missing_route_count,
        "missing_health_count": missing_health_count,
        "reachable_edge_count": reachable_edge_count,
        "degraded_edge_count": degraded_edge_count,
        "unreachable_edge_count": unreachable_edge_count,
        "reachable_agent_count": 1 + reachable_edge_count,
        "non_ready_edge_count": len(edges) - reachable_edge_count,
    }


def topology_checks(manifest: dict[str, Any], summary: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    missing_routes = int(summary["missing_route_count"])
    if missing_routes and manifest["require_all_expected_routes"]:
        checks.append(check_entry("configured_route_coverage", "failed", missing_routes, "0 missing", "expected agents are missing configured routes"))
    elif missing_routes:
        checks.append(check_entry("configured_route_coverage", "manual_review", missing_routes, "0 missing", "expected route gaps require review"))
    else:
        checks.append(check_entry("configured_route_coverage", "passed", 0, "0 missing", "expected targets have configured routes"))

    missing_health = int(summary["missing_health_count"])
    if missing_health:
        checks.append(check_entry("route_health_coverage", "manual_review", missing_health, "0 missing", "configured routes are missing route-health evidence"))
    else:
        checks.append(check_entry("route_health_coverage", "passed", 0, "0 missing", "configured routes have route-health evidence"))

    healthy = int(summary["reachable_edge_count"])
    min_healthy = int(manifest["min_healthy_route_count"])
    if healthy < min_healthy:
        checks.append(check_entry("healthy_route_threshold", "failed", healthy, min_healthy, "healthy route count is below threshold"))
    else:
        checks.append(check_entry("healthy_route_threshold", "passed", healthy, min_healthy, "healthy route count meets threshold"))

    reachable_agents = int(summary["reachable_agent_count"])
    min_reachable_agents = int(manifest["min_reachable_agent_count"])
    if reachable_agents < min_reachable_agents:
        checks.append(check_entry("reachable_agent_threshold", "failed", reachable_agents, min_reachable_agents, "reachable agent count is below threshold"))
    else:
        checks.append(check_entry("reachable_agent_threshold", "passed", reachable_agents, min_reachable_agents, "reachable agent count meets threshold"))

    non_ready = int(summary["non_ready_edge_count"])
    if non_ready and manifest["require_no_unhealthy_routes"]:
        checks.append(check_entry("non_ready_route_policy", "failed", non_ready, 0, "one or more expected routes are not ready"))
    elif non_ready:
        checks.append(check_entry("non_ready_route_policy", "manual_review", non_ready, 0, "one or more expected routes need review"))
    else:
        checks.append(check_entry("non_ready_route_policy", "passed", 0, 0, "all expected routes are reachable"))
    return checks


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "topology_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "topology_ready"


def build_topology_report(
    manifest: dict[str, Any],
    route_config: dict[str, Any],
    route_health_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    peer_mesh_dispatch_plan.validate_route_config(route_config)
    validate_route_health_report(route_health_report)
    edges = topology_edges(manifest, route_config, route_health_report)
    summary = summarize(manifest, edges)
    checks = [
        *identity_checks(manifest, route_config, route_health_report),
        *topology_checks(manifest, summary),
    ]
    return {
        "schema": TOPOLOGY_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "topology_id": manifest["topology_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": overall_status(checks),
        "checks": checks,
        "expected_agent_ids": list(manifest["expected_agent_ids"]),
        "edges": edges,
        "summary": summary,
        "authority_boundary": [
            "Peer topology reports summarize configured route coverage and synthetic route-health reachability only.",
            "Peer topology reports do not discover peers, probe peers, open sockets, copy files, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Peer topology reports do not carry private endpoint values, raw network addresses, raw device identifiers, gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    validate_manifest(manifest)
    route_config = load_json(root / str(manifest["route_config_path"]))
    route_health_report = load_json(root / str(manifest["route_health_report_path"]))
    write_json(args.output, build_topology_report(manifest, route_config, route_health_report, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer topology coverage report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
