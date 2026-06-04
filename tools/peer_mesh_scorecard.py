#!/usr/bin/env python3
"""Public-safe scorecard over peer mesh preparation evidence.

The scorecard summarizes synthetic peer-mesh reports for operator review. It
does not approve live work, select endpoints, open sockets, copy files,
discover peers, use ADB, send gossip, launch apps, replay evidence, or carry
commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import peer_mesh_evidence_intake
import peer_mesh_gossip
import peer_mesh_lab_bundle
import peer_mesh_live_lab_readiness
import peer_mesh_rehearsal
import peer_mesh_route_health
import peer_mesh_route_history
import peer_mesh_trust_gate


SCORECARD_MANIFEST_SCHEMA = "quest-termux-lab.peer-scorecard-manifest.v1"
SCORECARD_REPORT_SCHEMA = "quest-termux-lab.peer-scorecard-report.v1"
SCORE_STATUSES = {"synthetic_clear", "manual_review", "blocked", "missing"}
OVERALL_STATUSES = {"synthetic_clear", "manual_review", "blocked"}
ARTIFACT_SCHEMAS = {
    "readiness_report": peer_mesh_live_lab_readiness.READINESS_REPORT_SCHEMA,
    "lab_bundle_report": peer_mesh_lab_bundle.LAB_BUNDLE_REPORT_SCHEMA,
    "trust_report": peer_mesh_trust_gate.TRUST_REPORT_SCHEMA,
    "rehearsal_report": peer_mesh_rehearsal.REHEARSAL_REPORT_SCHEMA,
    "evidence_intake_report": peer_mesh_evidence_intake.EVIDENCE_REPORT_SCHEMA,
    "route_health_report": peer_mesh_route_health.ROUTE_HEALTH_REPORT_SCHEMA,
    "route_history_report": peer_mesh_route_history.ROUTE_HISTORY_SCHEMA,
    "cleanup_record": peer_mesh_evidence_intake.ARTIFACT_SCHEMAS["cleanup_record"],
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


def validate_artifact_kind_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result = []
    for item in value:
        if item not in ARTIFACT_SCHEMAS:
            raise ValueError(f"unsupported {label} entry")
        result.append(str(item))
    if len(set(result)) != len(result):
        raise ValueError(f"{label} entries must be unique")
    return result


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != SCORECARD_MANIFEST_SCHEMA:
        raise ValueError("unsupported scorecard manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("scorecard manifest contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "scorecard_id",
        "experiment_scope",
        "required_artifact_kinds",
        "optional_artifact_kinds",
        "artifact_paths",
    ]:
        if key not in manifest:
            raise ValueError(f"scorecard manifest missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "scorecard_id"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"scorecard manifest missing {key}")
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    required = validate_artifact_kind_list(manifest["required_artifact_kinds"], "required_artifact_kinds")
    optional = validate_artifact_kind_list(manifest["optional_artifact_kinds"], "optional_artifact_kinds")
    overlap = set(required) & set(optional)
    if overlap:
        raise ValueError("required and optional artifact kinds must not overlap")
    paths = manifest["artifact_paths"]
    if not isinstance(paths, dict):
        raise ValueError("artifact_paths must be an object")
    for kind, value in paths.items():
        if kind not in ARTIFACT_SCHEMAS:
            raise ValueError("artifact_paths contains unsupported kind")
        if not isinstance(value, str) or not value:
            raise ValueError(f"artifact_paths.{kind} must be a non-empty string")
        peer_mesh_evidence_intake.validate_artifact_path(value, f"artifact_paths.{kind}")


def validate_evidence_intake_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_evidence_intake.EVIDENCE_REPORT_SCHEMA:
        raise ValueError("unsupported evidence intake report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("evidence intake report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "experiment_scope", "overall_status", "summary"]:
        if key not in report:
            raise ValueError(f"evidence intake report missing {key}")
    if report["overall_status"] not in peer_mesh_evidence_intake.INTAKE_STATUSES:
        raise ValueError("unsupported evidence intake status")


VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "readiness_report": peer_mesh_lab_bundle.validate_readiness_report,
    "lab_bundle_report": peer_mesh_trust_gate.validate_bundle_report,
    "trust_report": peer_mesh_rehearsal.validate_trust_report,
    "rehearsal_report": peer_mesh_evidence_intake.validate_rehearsal_report,
    "evidence_intake_report": validate_evidence_intake_report,
    "route_health_report": peer_mesh_evidence_intake.validate_route_health_report,
    "route_history_report": peer_mesh_evidence_intake.validate_route_history_report,
    "cleanup_record": peer_mesh_evidence_intake.validate_cleanup_record,
}


def identity_check(kind: str, artifact: dict[str, Any], manifest: dict[str, Any]) -> None:
    if artifact.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError("fleet_id mismatch")
    if artifact.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError("source_agent_id mismatch")
    if artifact.get("experiment_scope") and artifact.get("experiment_scope") != manifest["experiment_scope"]:
        raise ValueError("experiment_scope mismatch")


def status_from_artifact(kind: str, artifact: dict[str, Any]) -> tuple[str, str, str]:
    if kind == "readiness_report":
        source_status = str(artifact["overall_status"])
        if source_status == "ready":
            return "synthetic_clear", source_status, "readiness report is ready"
        if source_status == "manual_review":
            return "manual_review", source_status, "readiness report requires manual review"
        return "blocked", source_status, "readiness report is not ready"
    if kind == "lab_bundle_report":
        source_status = str(artifact["overall_status"])
        if source_status == "synthetic_ready":
            return "synthetic_clear", source_status, "lab bundle is synthetically ready"
        if source_status == "manual_review":
            return "manual_review", source_status, "lab bundle requires manual review"
        return "blocked", source_status, "lab bundle is blocked"
    if kind == "trust_report":
        source_status = str(artifact["overall_status"])
        if source_status == "trusted":
            return "synthetic_clear", source_status, "trust report is trusted"
        if source_status == "manual_review":
            return "manual_review", source_status, "trust report requires manual review"
        return "blocked", source_status, "trust report is untrusted"
    if kind == "rehearsal_report":
        source_status = str(artifact["overall_status"])
        if source_status == "rehearsal_ready":
            return "synthetic_clear", source_status, "rehearsal report is ready"
        if source_status == "manual_review":
            return "manual_review", source_status, "rehearsal report requires manual review"
        return "blocked", source_status, "rehearsal report is blocked"
    if kind == "evidence_intake_report":
        source_status = str(artifact["overall_status"])
        if source_status == "accepted":
            return "synthetic_clear", source_status, "evidence intake is accepted"
        if source_status == "manual_review":
            return "manual_review", source_status, "evidence intake requires manual review"
        return "blocked", source_status, "evidence intake is rejected"
    if kind == "route_health_report":
        summary = artifact.get("summary", {})
        unknown = int(summary.get("unknown_count", 0)) if isinstance(summary, dict) else 0
        unavailable = int(summary.get("unavailable_count", 0)) if isinstance(summary, dict) else 0
        if unavailable > 0:
            return "blocked", "unavailable", "route-health report has unavailable routes"
        if unknown > 0:
            return "manual_review", "unknown", "route-health report has unknown routes"
        return "synthetic_clear", "clear", "route-health report has no unavailable or unknown routes"
    if kind == "route_history_report":
        summary = artifact.get("summary", {})
        unknown = int(summary.get("last_unknown_count", 0)) if isinstance(summary, dict) else 0
        unavailable = int(summary.get("last_unavailable_count", 0)) if isinstance(summary, dict) else 0
        worsening = int(summary.get("worsening_count", 0)) if isinstance(summary, dict) else 0
        if unavailable > 0 or worsening > 0:
            return "blocked", "unavailable_or_worsening", "route-history report has unavailable or worsening routes"
        if unknown > 0:
            return "manual_review", "unknown", "route-history report has unknown routes"
        return "synthetic_clear", "clear", "route-history report has no unavailable, worsening, or unknown routes"
    if kind == "cleanup_record":
        source_status = str(artifact["cleanup_status"])
        if source_status == "completed":
            return "synthetic_clear", source_status, "cleanup record is completed"
        return "manual_review", source_status, "cleanup record is not completed"
    raise ValueError("unsupported artifact kind")


def artifact_entry(kind: str, required: bool, artifact: dict[str, Any] | None, manifest: dict[str, Any]) -> dict[str, Any]:
    expected_schema = ARTIFACT_SCHEMAS[kind]
    if artifact is None:
        return {
            "artifact_kind": kind,
            "required": required,
            "status": "missing",
            "source_status": "missing",
            "expected_schema": expected_schema,
            "observed_schema": "",
            "reason": "required artifact missing" if required else "optional artifact not provided",
        }
    try:
        VALIDATORS[kind](artifact)
        if artifact.get("schema") != expected_schema:
            raise ValueError("schema mismatch")
        identity_check(kind, artifact, manifest)
        status, source_status, reason = status_from_artifact(kind, artifact)
    except ValueError as error:
        status = "blocked"
        source_status = "invalid"
        reason = str(error)
    return {
        "artifact_kind": kind,
        "required": required,
        "status": status,
        "source_status": source_status,
        "expected_schema": expected_schema,
        "observed_schema": str(artifact.get("schema", "")),
        "reason": reason,
    }


def ordered_kinds(manifest: dict[str, Any]) -> list[tuple[str, bool]]:
    result = [(kind, True) for kind in manifest["required_artifact_kinds"]]
    result.extend((kind, False) for kind in manifest["optional_artifact_kinds"])
    return result


def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_count": len(entries),
        "required_artifact_count": sum(1 for entry in entries if entry["required"]),
        "synthetic_clear_count": sum(1 for entry in entries if entry["status"] == "synthetic_clear"),
        "manual_review_count": sum(1 for entry in entries if entry["status"] == "manual_review"),
        "blocked_count": sum(1 for entry in entries if entry["status"] == "blocked"),
        "missing_count": sum(1 for entry in entries if entry["status"] == "missing"),
    }


def pressure_points(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "artifact_kind": entry["artifact_kind"],
            "status": entry["status"],
            "reason": entry["reason"],
        }
        for entry in entries
        if entry["status"] in {"blocked", "manual_review", "missing"}
    ]


def overall_status(entries: list[dict[str, Any]]) -> str:
    for entry in entries:
        if entry["status"] == "blocked":
            return "blocked"
        if entry["required"] and entry["status"] == "missing":
            return "blocked"
    if any(entry["status"] == "manual_review" for entry in entries):
        return "manual_review"
    return "synthetic_clear"


def load_artifacts_from_manifest(manifest: dict[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for kind, _required in ordered_kinds(manifest):
        path_text = manifest.get("artifact_paths", {}).get(kind)
        if isinstance(path_text, str) and path_text:
            artifacts[kind] = load_json(root / path_text)
    return artifacts


def build_scorecard_report(
    manifest: dict[str, Any],
    artifacts_by_kind: dict[str, dict[str, Any]],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    entries = [
        artifact_entry(kind, required, artifacts_by_kind.get(kind), manifest)
        for kind, required in ordered_kinds(manifest)
    ]
    return {
        "schema": SCORECARD_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "scorecard_id": manifest["scorecard_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": overall_status(entries),
        "artifacts": entries,
        "pressure_points": pressure_points(entries),
        "summary": summarize(entries),
        "authority_boundary": [
            "Scorecards summarize synthetic peer-mesh evidence only.",
            "Scorecards do not approve live work, select endpoints, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Scorecards do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    write_json(
        args.output,
        build_scorecard_report(
            manifest,
            load_artifacts_from_manifest(manifest, root),
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer mesh scorecard report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
