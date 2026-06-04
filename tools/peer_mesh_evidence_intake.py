#!/usr/bin/env python3
"""Public-safe post-run evidence intake for peer mesh experiments.

The intake report validates synthetic evidence artifacts that a future private
run would produce. It does not approve live work, select endpoints, open
sockets, copy files, discover peers, use ADB, send gossip, launch apps, or
carry commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import peer_mesh_gossip
import peer_mesh_http_sim
import peer_mesh_rehearsal
import peer_mesh_route_health
import peer_mesh_route_history
import peer_mesh_trust_gate


EVIDENCE_MANIFEST_SCHEMA = "quest-termux-lab.peer-evidence-intake-manifest.v1"
EVIDENCE_REPORT_SCHEMA = "quest-termux-lab.peer-evidence-intake-report.v1"
INTAKE_STATUSES = {"accepted", "manual_review", "rejected"}
ARTIFACT_STATUSES = {"accepted", "missing", "rejected", "manual_review"}
ARTIFACT_SCHEMAS = {
    "rehearsal_report": peer_mesh_rehearsal.REHEARSAL_REPORT_SCHEMA,
    "trust_report": peer_mesh_trust_gate.TRUST_REPORT_SCHEMA,
    "gossip_receipt": peer_mesh_http_sim.HTTP_RECEIPT_SCHEMA,
    "route_health_report": peer_mesh_route_health.ROUTE_HEALTH_REPORT_SCHEMA,
    "route_history_report": peer_mesh_route_history.ROUTE_HISTORY_SCHEMA,
    "cleanup_record": "quest-termux-lab.peer-cleanup-record.v1",
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
    # Public fixtures may point at examples/ and runs/, but not absolute paths
    # or traversal outside the chosen evidence root.
    import peer_mesh_dispatch_plan

    peer_mesh_dispatch_plan.validate_relative_path(value, label)


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != EVIDENCE_MANIFEST_SCHEMA:
        raise ValueError("unsupported evidence intake manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("evidence intake manifest contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "intake_id",
        "experiment_scope",
        "require_rehearsal_ready",
        "required_artifact_kinds",
        "optional_artifact_kinds",
        "artifact_paths",
    ]:
        if key not in manifest:
            raise ValueError(f"evidence intake manifest missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "intake_id"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"evidence intake manifest missing {key}")
    import peer_mesh_live_lab_readiness

    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if not isinstance(manifest["require_rehearsal_ready"], bool):
        raise ValueError("require_rehearsal_ready must be boolean")
    for key in ["required_artifact_kinds", "optional_artifact_kinds"]:
        if not isinstance(manifest[key], list):
            raise ValueError(f"{key} must be an array")
        for kind in manifest[key]:
            if kind not in ARTIFACT_SCHEMAS:
                raise ValueError(f"unsupported {key} entry")
        if len(set(manifest[key])) != len(manifest[key]):
            raise ValueError(f"{key} entries must be unique")
    overlap = set(manifest["required_artifact_kinds"]) & set(manifest["optional_artifact_kinds"])
    if overlap:
        raise ValueError("required and optional artifact kinds must not overlap")
    paths = manifest["artifact_paths"]
    if not isinstance(paths, dict):
        raise ValueError("artifact_paths must be an object")
    for kind, value in paths.items():
        if kind not in ARTIFACT_SCHEMAS:
            raise ValueError("artifact_paths contains unsupported kind")
        if isinstance(value, str):
            validate_artifact_path(value, f"artifact_paths.{kind}")
        elif isinstance(value, list):
            if not value:
                raise ValueError(f"artifact_paths.{kind} must not be empty")
            for index, item in enumerate(value):
                if not isinstance(item, str) or not item:
                    raise ValueError(f"artifact_paths.{kind}[{index}] must be a non-empty string")
                validate_artifact_path(item, f"artifact_paths.{kind}[{index}]")
        else:
            raise ValueError(f"artifact_paths.{kind} must be a string or array")


def validate_rehearsal_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_rehearsal.REHEARSAL_REPORT_SCHEMA:
        raise ValueError("unsupported rehearsal report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("rehearsal report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "experiment_scope", "overall_status", "summary"]:
        if key not in report:
            raise ValueError(f"rehearsal report missing {key}")
    if report["overall_status"] not in peer_mesh_rehearsal.REHEARSAL_STATUSES:
        raise ValueError("unsupported rehearsal status")


def validate_trust_report(report: dict[str, Any]) -> None:
    peer_mesh_rehearsal.validate_trust_report(report)


def validate_gossip_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != peer_mesh_http_sim.HTTP_RECEIPT_SCHEMA:
        raise ValueError("unsupported gossip receipt schema")
    if peer_mesh_gossip.contains_forbidden_key(receipt):
        raise ValueError("gossip receipt contains command-like or credential-like fields")
    for key in ["fleet_id", "observer_agent_id", "message_id", "sender_agent_id", "status", "applied"]:
        if key not in receipt:
            raise ValueError(f"gossip receipt missing {key}")
    if receipt["status"] not in {"accepted", "duplicate"}:
        raise ValueError("unsupported gossip receipt status")
    if not isinstance(receipt["applied"], bool):
        raise ValueError("gossip receipt applied must be boolean")


def validate_route_health_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_route_health.ROUTE_HEALTH_REPORT_SCHEMA:
        raise ValueError("unsupported route-health report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("route-health report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "routes", "summary"]:
        if key not in report:
            raise ValueError(f"route-health report missing {key}")
    if not isinstance(report["routes"], list):
        raise ValueError("route-health routes must be an array")


def validate_route_history_report(report: dict[str, Any]) -> None:
    import peer_mesh_live_lab_readiness

    peer_mesh_live_lab_readiness.validate_history(report)


def validate_cleanup_record(record: dict[str, Any]) -> None:
    if record.get("schema") != ARTIFACT_SCHEMAS["cleanup_record"]:
        raise ValueError("unsupported cleanup record schema")
    if peer_mesh_gossip.contains_forbidden_key(record):
        raise ValueError("cleanup record contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "cleanup_status", "private_live_work_performed"]:
        if key not in record:
            raise ValueError(f"cleanup record missing {key}")
    if record["cleanup_status"] not in {"not_started", "completed", "manual_review"}:
        raise ValueError("unsupported cleanup_status")
    if not isinstance(record["private_live_work_performed"], bool):
        raise ValueError("private_live_work_performed must be boolean")


VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "rehearsal_report": validate_rehearsal_report,
    "trust_report": validate_trust_report,
    "gossip_receipt": validate_gossip_receipt,
    "route_health_report": validate_route_health_report,
    "route_history_report": validate_route_history_report,
    "cleanup_record": validate_cleanup_record,
}


def identity_check(kind: str, artifact: dict[str, Any], manifest: dict[str, Any]) -> None:
    if artifact.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError("fleet_id mismatch")
    if kind == "gossip_receipt":
        # Receipts are observed by the peer endpoint. They still need to belong
        # to this fleet, but observer_agent_id can differ from source_agent_id.
        return
    if artifact.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError("source_agent_id mismatch")
    if artifact.get("experiment_scope") and artifact.get("experiment_scope") != manifest["experiment_scope"]:
        raise ValueError("experiment_scope mismatch")


def artifact_entries(kind: str, manifest: dict[str, Any], artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_schema = ARTIFACT_SCHEMAS[kind]
    entries = []
    required = kind in set(manifest["required_artifact_kinds"])
    if not artifacts:
        entries.append(
            {
                "artifact_kind": kind,
                "status": "missing" if required else "manual_review",
                "expected_schema": expected_schema,
                "observed_schema": "",
                "reason": "required artifact missing" if required else "optional artifact not provided",
            }
        )
        return entries
    for artifact in artifacts:
        try:
            VALIDATORS[kind](artifact)
            if artifact.get("schema") != expected_schema:
                raise ValueError("schema mismatch")
            identity_check(kind, artifact, manifest)
            status = "accepted"
            reason = "artifact accepted"
            if kind == "rehearsal_report" and manifest["require_rehearsal_ready"]:
                if artifact.get("overall_status") == "manual_review":
                    status = "manual_review"
                    reason = "rehearsal report requires manual review"
                elif artifact.get("overall_status") != "rehearsal_ready":
                    status = "rejected"
                    reason = "rehearsal report is not rehearsal_ready"
            if kind == "trust_report" and artifact.get("overall_status") == "manual_review":
                status = "manual_review"
                reason = "trust report requires manual review"
            elif kind == "trust_report" and artifact.get("overall_status") == "untrusted":
                status = "rejected"
                reason = "trust report is untrusted"
            if kind == "route_health_report":
                summary = artifact.get("summary", {})
                if isinstance(summary, dict) and summary.get("unknown_count", 0) > 0:
                    status = "manual_review"
                    reason = "route-health report still has unknown routes"
            if kind == "route_history_report":
                summary = artifact.get("summary", {})
                if isinstance(summary, dict) and summary.get("last_unknown_count", 0) > 0:
                    status = "manual_review"
                    reason = "route-history report still has unknown routes"
            if kind == "cleanup_record" and artifact.get("cleanup_status") == "manual_review":
                status = "manual_review"
                reason = "cleanup record requires manual review"
            elif kind == "cleanup_record" and artifact.get("cleanup_status") == "not_started":
                status = "manual_review"
                reason = "cleanup has not started in public synthetic evidence"
        except ValueError as error:
            status = "rejected"
            reason = str(error)
        entries.append(
            {
                "artifact_kind": kind,
                "status": status,
                "expected_schema": expected_schema,
                "observed_schema": str(artifact.get("schema", "")),
                "reason": reason,
            }
        )
    return entries


def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_count": len(entries),
        "accepted_artifact_count": sum(1 for entry in entries if entry["status"] == "accepted"),
        "missing_artifact_count": sum(1 for entry in entries if entry["status"] == "missing"),
        "rejected_artifact_count": sum(1 for entry in entries if entry["status"] == "rejected"),
        "manual_review_artifact_count": sum(1 for entry in entries if entry["status"] == "manual_review"),
    }


def overall_status(entries: list[dict[str, Any]]) -> str:
    if any(entry["status"] in {"missing", "rejected"} for entry in entries):
        return "rejected"
    if any(entry["status"] == "manual_review" for entry in entries):
        return "manual_review"
    return "accepted"


def build_evidence_report(
    manifest: dict[str, Any],
    artifacts_by_kind: dict[str, list[dict[str, Any]]],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    ordered_kinds = list(manifest["required_artifact_kinds"]) + list(manifest["optional_artifact_kinds"])
    entries: list[dict[str, Any]] = []
    for kind in ordered_kinds:
        entries.extend(artifact_entries(kind, manifest, artifacts_by_kind.get(kind, [])))
    status = overall_status(entries)
    return {
        "schema": EVIDENCE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "intake_id": manifest["intake_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": status,
        "artifacts": entries,
        "summary": summarize(entries),
        "authority_boundary": [
            "Evidence intake reports validate synthetic peer-mesh artifacts only.",
            "Evidence intake reports do not approve live work, select endpoints, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Evidence intake reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def paths_for_kind(manifest: dict[str, Any], kind: str) -> list[str]:
    value = manifest.get("artifact_paths", {}).get(kind)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def load_artifacts_from_manifest(manifest: dict[str, Any], root: Path) -> dict[str, list[dict[str, Any]]]:
    artifacts: dict[str, list[dict[str, Any]]] = {}
    for kind in list(manifest.get("required_artifact_kinds", [])) + list(manifest.get("optional_artifact_kinds", [])):
        artifacts[kind] = [load_json(root / path_text) for path_text in paths_for_kind(manifest, str(kind))]
    return artifacts


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    report = build_evidence_report(
        manifest,
        load_artifacts_from_manifest(manifest, root),
        now_text=args.now or None,
    )
    write_json(args.output, report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer evidence intake report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
