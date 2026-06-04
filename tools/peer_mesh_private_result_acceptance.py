#!/usr/bin/env python3
"""Public-safe private result acceptance gate for peer mesh preparation.

The acceptance report consumes a public-safe result placeholder report and
decides whether future sanitized derivative result slots could be accepted
after private review. It does not read private evidence, import artifacts,
sanitize live artifacts, approve live work, select endpoints, collect evidence,
replay evidence, monitor peers, probe peers, open sockets, copy files,
discover devices, use ADB, send gossip, launch apps, execute commands, or
execute validation slots.
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
import peer_mesh_private_result_placeholder


ACCEPTANCE_MANIFEST_SCHEMA = "quest-termux-lab.peer-private-result-acceptance-manifest.v1"
ACCEPTANCE_REPORT_SCHEMA = "quest-termux-lab.peer-private-result-acceptance-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
ACCEPTANCE_STATUSES = {"acceptance_ready", "manual_review", "acceptance_blocked"}
ITEM_STATUSES = {
    "private_only",
    "ready_to_accept_sanitized_artifact",
    "blocked_until_placeholders_ready",
    "blocked_missing_derivative_schema",
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
    peer_mesh_evidence_intake.validate_artifact_path(value, label)
    if Path(value).suffix.lower() != ".json":
        raise ValueError(f"{label} must reference a json file")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != ACCEPTANCE_MANIFEST_SCHEMA:
        raise ValueError("unsupported private result acceptance manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("private result acceptance manifest contains command-like or credential-like fields")
    for key in [
        "acceptance_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "placeholder_report_path",
        "require_placeholders_ready",
        "require_derivative_slots",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"private result acceptance manifest missing {key}")
    for key in ["acceptance_id", "fleet_id", "source_agent_id", "observed_at", "placeholder_report_path"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"private result acceptance manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_report_path(str(manifest["placeholder_report_path"]), "placeholder_report_path")
    for key in ["require_placeholders_ready", "require_derivative_slots"]:
        if not isinstance(manifest[key], bool):
            raise ValueError(f"{key} must be boolean")
    boundary = manifest["authority_boundary"]
    if not isinstance(boundary, list) or not boundary:
        raise ValueError("authority_boundary must be a non-empty array")
    for entry in boundary:
        if not isinstance(entry, str) or not entry:
            raise ValueError("authority_boundary entries must be text")


def validate_placeholder_slot(slot: Any) -> None:
    if not isinstance(slot, dict):
        raise ValueError("placeholder slot must be an object")
    for key in [
        "slot_id",
        "evidence_kind",
        "expected_schema",
        "required",
        "collection_status",
        "public_release",
        "public_derivative_schema",
        "source_import_status",
        "placeholder_status",
        "public_placeholder",
        "reason",
    ]:
        if key not in slot:
            raise ValueError(f"placeholder slot missing {key}")
    for key in [
        "slot_id",
        "evidence_kind",
        "expected_schema",
        "collection_status",
        "public_release",
        "public_derivative_schema",
        "source_import_status",
        "placeholder_status",
        "reason",
    ]:
        if not isinstance(slot[key], str):
            raise ValueError(f"placeholder slot missing {key}")
    if not isinstance(slot["required"], bool):
        raise ValueError("placeholder slot missing required")
    if slot["public_release"] not in {"sanitized_derivative_only", "private_only", ""}:
        raise ValueError("unsupported public_release")
    if slot["placeholder_status"] not in peer_mesh_private_result_placeholder.PLACEHOLDER_STATUSES:
        raise ValueError("unsupported placeholder_status")
    if slot["public_placeholder"] is not True:
        raise ValueError("placeholder slot public_placeholder must be true")


def validate_placeholder_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_private_result_placeholder.PLACEHOLDER_REPORT_SCHEMA:
        raise ValueError("unsupported private result placeholder report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("private result placeholder report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "placeholder_id",
        "experiment_scope",
        "overall_status",
        "placeholder_slots",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"private result placeholder report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "placeholder_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"private result placeholder report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["overall_status"] not in peer_mesh_private_result_placeholder.OVERALL_STATUSES:
        raise ValueError("unsupported private result placeholder status")
    if not isinstance(report["placeholder_slots"], list):
        raise ValueError("placeholder_slots must be an array")
    for slot in report["placeholder_slots"]:
        validate_placeholder_slot(slot)


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported private result acceptance check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def identity_check(manifest: dict[str, Any], placeholder_report: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
        if placeholder_report.get(key) != manifest[key]:
            mismatches.append(key)
    if mismatches:
        return check_entry("placeholder_identity", "failed", ",".join(mismatches), "match", "placeholder report identity does not match acceptance manifest")
    return check_entry("placeholder_identity", "passed", "match", "match", "placeholder report identity matches acceptance manifest")


def placeholder_status_check(manifest: dict[str, Any], placeholder_report: dict[str, Any]) -> dict[str, Any]:
    status = str(placeholder_report["overall_status"])
    if status == "result_placeholders_ready":
        return check_entry("placeholder_status", "passed", status, "result_placeholders_ready", "result placeholders are ready for acceptance planning")
    if status == "manual_review" and not manifest["require_placeholders_ready"]:
        return check_entry("placeholder_status", "manual_review", status, "result_placeholders_ready", "result placeholders need manual review before acceptance planning")
    return check_entry("placeholder_status", "failed", status, "result_placeholders_ready", "result placeholders are not ready for sanitized result acceptance")


def derivative_slots_check(manifest: dict[str, Any], slots: list[dict[str, Any]]) -> dict[str, Any]:
    count = sum(1 for slot in slots if slot["public_release"] == "sanitized_derivative_only")
    if count < 1 and manifest["require_derivative_slots"]:
        return check_entry("derivative_slots", "failed", count, "> 0", "no sanitized derivative result slots are declared")
    if count < 1:
        return check_entry("derivative_slots", "manual_review", count, "> 0", "no sanitized derivative result slots are declared")
    return check_entry("derivative_slots", "passed", count, "> 0", "sanitized derivative result slots are declared")


def acceptance_item(slot: dict[str, Any]) -> dict[str, Any]:
    source_status = str(slot["placeholder_status"])
    public_release = str(slot["public_release"])
    derivative_schema = str(slot["public_derivative_schema"])
    if source_status == "private_only":
        status = "private_only"
        reason = "private-only evidence remains outside public acceptance"
    elif public_release == "sanitized_derivative_only" and not derivative_schema:
        status = "blocked_missing_derivative_schema"
        reason = "sanitized derivative result slot is missing a public derivative schema"
    elif source_status == "awaiting_sanitized_derivative_artifact":
        status = "ready_to_accept_sanitized_artifact"
        reason = "sanitized derivative result slot can accept a future public-safe artifact after private review"
    elif source_status == "blocked_missing_derivative_schema":
        status = "blocked_missing_derivative_schema"
        reason = "sanitized derivative result slot is blocked until a derivative schema is declared"
    else:
        status = "blocked_until_placeholders_ready"
        reason = "sanitized derivative result slot is blocked until result placeholders are ready"
    return {
        "slot_id": slot["slot_id"],
        "evidence_kind": slot["evidence_kind"],
        "expected_schema": slot["expected_schema"],
        "required": slot["required"],
        "public_release": public_release,
        "public_derivative_schema": derivative_schema,
        "source_placeholder_status": source_status,
        "acceptance_status": status,
        "reason": reason,
    }


def acceptance_items(placeholder_report: dict[str, Any]) -> list[dict[str, Any]]:
    return [acceptance_item(slot) for slot in placeholder_report["placeholder_slots"]]


def summarize(checks: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "acceptance_item_count": len(items),
        "private_only_item_count": sum(1 for item in items if item["acceptance_status"] == "private_only"),
        "ready_to_accept_item_count": sum(1 for item in items if item["acceptance_status"] == "ready_to_accept_sanitized_artifact"),
        "blocked_until_placeholders_ready_count": sum(1 for item in items if item["acceptance_status"] == "blocked_until_placeholders_ready"),
        "blocked_missing_derivative_schema_count": sum(1 for item in items if item["acceptance_status"] == "blocked_missing_derivative_schema"),
        "blocked_item_count": sum(1 for item in items if item["acceptance_status"] in {"blocked_until_placeholders_ready", "blocked_missing_derivative_schema"}),
    }


def overall_status(checks: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "acceptance_blocked"
    if int(summary["blocked_missing_derivative_schema_count"]) > 0:
        return "acceptance_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "acceptance_ready"


def build_acceptance_report(
    manifest: dict[str, Any],
    placeholder_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    validate_placeholder_report(placeholder_report)
    items = acceptance_items(placeholder_report)
    checks = [
        identity_check(manifest, placeholder_report),
        placeholder_status_check(manifest, placeholder_report),
        derivative_slots_check(manifest, placeholder_report["placeholder_slots"]),
    ]
    summary = summarize(checks, items)
    return {
        "schema": ACCEPTANCE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "acceptance_id": manifest["acceptance_id"],
        "placeholder_id": placeholder_report["placeholder_id"],
        "experiment_scope": manifest["experiment_scope"],
        "placeholder_status": placeholder_report["overall_status"],
        "overall_status": overall_status(checks, summary),
        "checks": checks,
        "acceptance_items": items,
        "summary": summary,
        "authority_boundary": [
            "Private result acceptance reports declare whether future sanitized derivative result slots could be accepted after private review.",
            "Private result acceptance reports do not read private evidence, import artifacts, sanitize live artifacts, approve live work, select endpoints, collect evidence, replay evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Private result acceptance reports do not carry private endpoint values, raw network addresses, raw device identifiers, raw logs, pairing material, app package IDs, operator identity, or credential material.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    validate_manifest(manifest)
    placeholder_report = load_json(root / str(manifest["placeholder_report_path"]))
    write_json(args.output, build_acceptance_report(manifest, placeholder_report, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe private result acceptance report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
