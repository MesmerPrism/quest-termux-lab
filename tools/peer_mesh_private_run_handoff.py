#!/usr/bin/env python3
"""Public-safe private-run handoff gate for peer mesh preparation.

The handoff report checks whether sanitized public artifacts are ready to hand
to a private live-run process and lists expected private evidence slots. It
does not approve live work, select endpoints, replay evidence, monitor peers,
probe peers, open sockets, copy files, discover devices, use ADB, send gossip,
launch apps, execute commands, or execute validation slots.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_evidence_intake
import peer_mesh_gossip
import peer_mesh_live_lab_readiness
import peer_mesh_review_bundle


HANDOFF_MANIFEST_SCHEMA = "quest-termux-lab.peer-private-run-handoff-manifest.v1"
HANDOFF_REPORT_SCHEMA = "quest-termux-lab.peer-private-run-handoff-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
OVERALL_STATUSES = {"handoff_ready", "manual_review", "handoff_blocked"}
EVIDENCE_SLOT_KINDS = {
    "operator_approval_record",
    "endpoint_selection_record",
    "gossip_receipt",
    "route_health_report",
    "route_history_report",
    "cleanup_record",
    "scorecard_report",
    "scorecard_history",
    "scorecard_regression_report",
    "review_bundle_report",
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


def validate_report_path(value: str, label: str) -> None:
    peer_mesh_evidence_intake.validate_artifact_path(value, label)
    if Path(value).suffix.lower() != ".json":
        raise ValueError(f"{label} must reference a json file")


def validate_slot(item: Any) -> None:
    if not isinstance(item, dict):
        raise ValueError("evidence slot entries must be objects")
    for key in ["slot_id", "evidence_kind", "expected_schema", "reason"]:
        if not isinstance(item.get(key), str) or not item[key]:
            raise ValueError(f"evidence slot missing {key}")
    if item["evidence_kind"] not in EVIDENCE_SLOT_KINDS:
        raise ValueError("unsupported evidence_kind")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != HANDOFF_MANIFEST_SCHEMA:
        raise ValueError("unsupported private-run handoff manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("private-run handoff manifest contains command-like or credential-like fields")
    for key in [
        "handoff_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "review_bundle_report_path",
        "require_review_ready",
        "required_private_evidence_slots",
        "optional_private_evidence_slots",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"private-run handoff manifest missing {key}")
    for key in ["handoff_id", "fleet_id", "source_agent_id", "observed_at", "review_bundle_report_path"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"private-run handoff manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_report_path(str(manifest["review_bundle_report_path"]), "review_bundle_report_path")
    if not isinstance(manifest["require_review_ready"], bool):
        raise ValueError("require_review_ready must be boolean")
    for key in ["required_private_evidence_slots", "optional_private_evidence_slots", "authority_boundary"]:
        if not isinstance(manifest[key], list):
            raise ValueError(f"private-run handoff manifest {key} must be an array")
    for key in ["required_private_evidence_slots", "optional_private_evidence_slots"]:
        for item in manifest[key]:
            validate_slot(item)
    slot_ids = [
        str(item["slot_id"])
        for item in list(manifest["required_private_evidence_slots"]) + list(manifest["optional_private_evidence_slots"])
    ]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("evidence slot ids must be unique")
    if not manifest["required_private_evidence_slots"]:
        raise ValueError("at least one required private evidence slot is required")
    if not manifest["authority_boundary"]:
        raise ValueError("authority_boundary must not be empty")
    for item in manifest["authority_boundary"]:
        if not isinstance(item, str) or not item:
            raise ValueError("authority boundary entries must be text")


def validate_review_bundle_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_review_bundle.REVIEW_BUNDLE_REPORT_SCHEMA:
        raise ValueError("unsupported review bundle report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("review bundle report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "experiment_scope", "overall_status", "summary"]:
        if key not in report:
            raise ValueError(f"review bundle report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"review bundle report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["overall_status"] not in peer_mesh_review_bundle.OVERALL_STATUSES:
        raise ValueError("unsupported review bundle status")
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise ValueError("review bundle summary must be an object")
    for key in ["entry_count", "passed_count", "manual_review_count", "failed_count"]:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"review bundle summary missing non-negative integer {key}")


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported handoff check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def review_bundle_check(manifest: dict[str, Any], review_report: dict[str, Any]) -> dict[str, Any]:
    status = str(review_report["overall_status"])
    if status == "review_ready":
        return check_entry("review_bundle_status", "passed", status, "review_ready", "review bundle is ready")
    if status == "manual_review" and not manifest["require_review_ready"]:
        return check_entry("review_bundle_status", "manual_review", status, "review_ready", "review bundle needs manual review")
    if status == "manual_review":
        return check_entry("review_bundle_status", "failed", status, "review_ready", "review bundle is not fully ready")
    return check_entry("review_bundle_status", "failed", status, "review_ready", "review bundle is blocked")


def identity_check(manifest: dict[str, Any], review_report: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
        if review_report.get(key) != manifest[key]:
            mismatches.append(key)
    if mismatches:
        return check_entry("review_bundle_identity", "failed", ",".join(mismatches), "match", "review bundle identity does not match handoff manifest")
    return check_entry("review_bundle_identity", "passed", "match", "match", "review bundle identity matches handoff manifest")


def evidence_slot_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for required, key in [(True, "required_private_evidence_slots"), (False, "optional_private_evidence_slots")]:
        for item in manifest[key]:
            entries.append(
                {
                    "slot_id": item["slot_id"],
                    "evidence_kind": item["evidence_kind"],
                    "expected_schema": item["expected_schema"],
                    "required": required,
                    "status": "declared",
                    "reason": item["reason"],
                }
            )
    return entries


def slot_declaration_check(slots: list[dict[str, Any]]) -> dict[str, Any]:
    required_count = sum(1 for slot in slots if slot["required"])
    if required_count == 0:
        return check_entry("required_evidence_slots", "failed", required_count, "> 0", "no required private evidence slots declared")
    return check_entry("required_evidence_slots", "passed", required_count, "> 0", "required private evidence slots are declared")


def summarize_checks(checks: list[dict[str, Any]], slots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "required_evidence_slot_count": sum(1 for slot in slots if slot["required"]),
        "optional_evidence_slot_count": sum(1 for slot in slots if not slot["required"]),
    }


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "handoff_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "handoff_ready"


def build_handoff_report(
    manifest: dict[str, Any],
    review_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    validate_review_bundle_report(review_report)
    slots = evidence_slot_entries(manifest)
    checks = [
        identity_check(manifest, review_report),
        review_bundle_check(manifest, review_report),
        slot_declaration_check(slots),
    ]
    return {
        "schema": HANDOFF_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "handoff_id": manifest["handoff_id"],
        "experiment_scope": manifest["experiment_scope"],
        "review_bundle_status": review_report["overall_status"],
        "overall_status": overall_status(checks),
        "checks": checks,
        "private_evidence_slots": slots,
        "summary": summarize_checks(checks, slots),
        "authority_boundary": [
            "Private-run handoff reports inspect sanitized peer-mesh artifacts and declare private evidence slots only.",
            "Private-run handoff reports do not approve live work, select endpoints, replay evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Private-run handoff reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, launch requests, or private endpoint values.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    review_report = load_json(root / str(manifest.get("review_bundle_report_path", "")))
    write_json(args.output, build_handoff_report(manifest, review_report, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer private-run handoff report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
