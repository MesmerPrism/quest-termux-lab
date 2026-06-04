#!/usr/bin/env python3
"""Public-safe lab bundle checker for future private peer experiments.

The bundle report packages synthetic readiness evidence before any live peer
transport work. It does not approve live work, open sockets, copy files,
discover peers, use ADB, send gossip, launch apps, or carry commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import peer_mesh_dispatch_plan
import peer_mesh_gossip
import peer_mesh_live_lab_readiness
import peer_mesh_route_history
import peer_mesh_topology


LAB_BUNDLE_MANIFEST_SCHEMA = "quest-termux-lab.peer-lab-bundle-manifest.v1"
LAB_BUNDLE_REPORT_SCHEMA = "quest-termux-lab.peer-lab-bundle-report.v1"
BUNDLE_STATUSES = {"synthetic_ready", "manual_review", "blocked"}
ARTIFACT_SCHEMAS = {
    "route_config": peer_mesh_dispatch_plan.ROUTE_CONFIG_SCHEMA,
    "topology_report": peer_mesh_topology.TOPOLOGY_REPORT_SCHEMA,
    "route_history": peer_mesh_route_history.ROUTE_HISTORY_SCHEMA,
    "readiness_report": peer_mesh_live_lab_readiness.READINESS_REPORT_SCHEMA,
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


def validate_artifact_path(value: str, label: str) -> None:
    peer_mesh_dispatch_plan.validate_relative_path(value, label)


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != LAB_BUNDLE_MANIFEST_SCHEMA:
        raise ValueError("unsupported lab bundle manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("lab bundle manifest contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_id",
        "experiment_scope",
        "operator_approval_required",
        "operator_approval_recorded",
        "artifact_paths",
        "expected_artifact_schemas",
    ]:
        if key not in manifest:
            raise ValueError(f"lab bundle manifest missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "experiment_id"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"lab bundle manifest missing {key}")
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    for key in ["operator_approval_required", "operator_approval_recorded"]:
        if not isinstance(manifest[key], bool):
            raise ValueError(f"{key} must be boolean")
    artifact_paths = manifest["artifact_paths"]
    if not isinstance(artifact_paths, dict):
        raise ValueError("artifact_paths must be an object")
    expected_schemas = manifest["expected_artifact_schemas"]
    if not isinstance(expected_schemas, dict):
        raise ValueError("expected_artifact_schemas must be an object")
    for artifact_id, schema in ARTIFACT_SCHEMAS.items():
        if expected_schemas.get(artifact_id) != schema:
            raise ValueError(f"expected_artifact_schemas missing {artifact_id}")
        path_text = artifact_paths.get(artifact_id)
        if not isinstance(path_text, str) or not path_text:
            raise ValueError(f"artifact_paths missing {artifact_id}")
        validate_artifact_path(path_text, f"artifact_paths.{artifact_id}")


def validate_readiness_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_live_lab_readiness.READINESS_REPORT_SCHEMA:
        raise ValueError("unsupported readiness report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("readiness report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "experiment_scope", "overall_status", "summary"]:
        if key not in report:
            raise ValueError(f"readiness report missing {key}")
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported readiness experiment_scope")
    if report["overall_status"] not in peer_mesh_live_lab_readiness.OVERALL_STATUSES:
        raise ValueError("unsupported readiness status")
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise ValueError("readiness summary must be an object")
    for key in ["route_count", "ready_route_count", "not_ready_route_count"]:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"readiness summary missing non-negative {key}")


def validate_topology_report(report: dict[str, Any]) -> None:
    peer_mesh_topology.validate_topology_report(report)
    if report["overall_status"] not in peer_mesh_topology.TOPOLOGY_STATUSES:
        raise ValueError("unsupported topology status")
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise ValueError("topology summary must be an object")
    for key in ["reachable_agent_count", "non_ready_edge_count"]:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"topology summary missing non-negative {key}")


def artifact_check(
    artifact_id: str,
    payload: dict[str, Any],
    manifest: dict[str, Any],
    validator: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    expected_schema = ARTIFACT_SCHEMAS[artifact_id]
    try:
        validator(payload)
        if payload.get("schema") != expected_schema:
            raise ValueError("schema mismatch")
        if payload.get("fleet_id") != manifest["fleet_id"]:
            raise ValueError("fleet_id mismatch")
        if payload.get("source_agent_id") != manifest["source_agent_id"]:
            raise ValueError("source_agent_id mismatch")
        if artifact_id in {"topology_report", "readiness_report"} and payload.get("experiment_scope") != manifest["experiment_scope"]:
            raise ValueError("experiment_scope mismatch")
        status = "passed"
        reason = "artifact matches manifest and schema"
    except ValueError as error:
        status = "failed"
        reason = str(error)
    return {
        "artifact_id": artifact_id,
        "expected_schema": expected_schema,
        "observed_schema": str(payload.get("schema", "")),
        "status": status,
        "reason": reason,
    }


def summarize(
    checks: list[dict[str, Any]],
    route_config: dict[str, Any],
    topology: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    def non_negative_int(value: Any) -> int:
        if isinstance(value, int) and value >= 0:
            return value
        return 0

    routes = route_config.get("routes", [])
    readiness_summary = readiness.get("summary", {})
    if not isinstance(readiness_summary, dict):
        readiness_summary = {}
    topology_summary = topology.get("summary", {})
    if not isinstance(topology_summary, dict):
        topology_summary = {}
    return {
        "artifact_check_count": len(checks),
        "passed_artifact_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "failed_artifact_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "configured_route_count": len(routes) if isinstance(routes, list) else 0,
        "topology_reachable_agent_count": non_negative_int(topology_summary.get("reachable_agent_count")),
        "topology_non_ready_edge_count": non_negative_int(topology_summary.get("non_ready_edge_count")),
        "ready_route_count": non_negative_int(readiness_summary.get("ready_route_count")),
        "not_ready_route_count": non_negative_int(readiness_summary.get("not_ready_route_count")),
    }


def overall_status(
    manifest: dict[str, Any],
    checks: list[dict[str, Any]],
    topology_status: str,
    readiness_status: str,
) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "blocked"
    if topology_status == "topology_blocked":
        return "blocked"
    if readiness_status == "not_ready":
        return "blocked"
    if topology_status == "manual_review":
        return "manual_review"
    if readiness_status == "manual_review":
        return "manual_review"
    if manifest["operator_approval_required"] and not manifest["operator_approval_recorded"]:
        return "manual_review"
    return "synthetic_ready"


def next_private_steps(status: str) -> list[str]:
    if status == "blocked":
        return [
            "Resolve blocked readiness status or failed synthetic artifact checks before any private LAN peer experiment.",
            "Regenerate route health, route history, readiness, and bundle reports from sanitized inputs.",
            "Do not start live transport from this public bundle report.",
        ]
    if status == "manual_review":
        return [
            "Record explicit operator approval in the private workflow before any live LAN peer experiment.",
            "Use the team device workflow for live ADB, port, install, launch, capture, and cleanup gates.",
            "Keep peer messages gossip-only and keep central ADB reserved for bootstrap and recovery.",
        ]
    return [
        "Treat this as synthetic readiness only, not live approval.",
        "Move private LAN endpoint selection and live transport evidence into the private workflow.",
        "Capture first live evidence as gossip-only peer observations, receipts, route health, and cleanup records.",
    ]


def build_bundle_report(
    manifest: dict[str, Any],
    route_config: dict[str, Any],
    topology_report: dict[str, Any],
    route_history: dict[str, Any],
    readiness_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    checks = [
        artifact_check("route_config", route_config, manifest, peer_mesh_dispatch_plan.validate_route_config),
        artifact_check("topology_report", topology_report, manifest, validate_topology_report),
        artifact_check("route_history", route_history, manifest, peer_mesh_live_lab_readiness.validate_history),
        artifact_check("readiness_report", readiness_report, manifest, validate_readiness_report),
    ]
    raw_topology_status = str(topology_report.get("overall_status", "invalid"))
    topology_status = (
        raw_topology_status
        if raw_topology_status in peer_mesh_topology.TOPOLOGY_STATUSES
        else "invalid"
    )
    raw_readiness_status = str(readiness_report.get("overall_status", "invalid"))
    readiness_status = (
        raw_readiness_status
        if raw_readiness_status in peer_mesh_live_lab_readiness.OVERALL_STATUSES
        else "invalid"
    )
    status = overall_status(manifest, checks, topology_status, readiness_status)
    observed_at = now_text or str(manifest["observed_at"])
    return {
        "schema": LAB_BUNDLE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": observed_at,
        "experiment_id": manifest["experiment_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": status,
        "topology_status": topology_status,
        "readiness_status": readiness_status,
        "operator_approval_required": manifest["operator_approval_required"],
        "operator_approval_recorded": manifest["operator_approval_recorded"],
        "artifact_checks": checks,
        "summary": summarize(checks, route_config, topology_report, readiness_report),
        "next_private_steps": next_private_steps(status),
        "authority_boundary": [
            "Lab bundle reports package synthetic peer-mesh evidence only.",
            "Lab bundle reports do not approve live work, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Lab bundle reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    route_config = load_json(Path(args.route_config))
    topology_report = load_json(Path(args.topology_report))
    route_history = load_json(Path(args.route_history))
    readiness_report = load_json(Path(args.readiness_report))
    report = build_bundle_report(
        manifest,
        route_config,
        topology_report,
        route_history,
        readiness_report,
        now_text=args.now or None,
    )
    write_json(args.output, report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer live-lab bundle report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--route-config", required=True)
    parser.add_argument("--topology-report", required=True)
    parser.add_argument("--route-history", required=True)
    parser.add_argument("--readiness-report", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
