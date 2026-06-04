#!/usr/bin/env python3
"""Public-safe private evidence import plan for peer mesh preparation.

The import plan consumes public package and private evidence redaction reports
to describe which sanitized derivatives could be imported after a private run.
It does not read private evidence, sanitize live artifacts, approve live work,
select endpoints, collect evidence, replay evidence, monitor peers, probe
peers, open sockets, copy files, discover devices, use ADB, send gossip,
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
import peer_mesh_private_evidence_redaction
import peer_mesh_public_package


IMPORT_MANIFEST_SCHEMA = "quest-termux-lab.peer-private-import-plan-manifest.v1"
IMPORT_REPORT_SCHEMA = "quest-termux-lab.peer-private-import-plan-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
IMPORT_STATUSES = {"import_ready", "manual_review", "import_blocked"}
ITEM_STATUSES = {
    "ready_for_public_derivative",
    "blocked_until_redaction_ready",
    "private_only",
    "missing_derivative_schema",
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
    if manifest.get("schema") != IMPORT_MANIFEST_SCHEMA:
        raise ValueError("unsupported private import plan manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("private import plan manifest contains command-like or credential-like fields")
    for key in [
        "import_plan_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "package_report_path",
        "redaction_report_path",
        "require_package_ready",
        "require_redaction_ready",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"private import plan manifest missing {key}")
    for key in ["import_plan_id", "fleet_id", "source_agent_id", "observed_at", "package_report_path", "redaction_report_path"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"private import plan manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_report_path(str(manifest["package_report_path"]), "package_report_path")
    validate_report_path(str(manifest["redaction_report_path"]), "redaction_report_path")
    for key in ["require_package_ready", "require_redaction_ready"]:
        if not isinstance(manifest[key], bool):
            raise ValueError(f"{key} must be boolean")
    boundary = manifest["authority_boundary"]
    if not isinstance(boundary, list) or not boundary:
        raise ValueError("authority_boundary must be a non-empty array")
    for entry in boundary:
        if not isinstance(entry, str) or not entry:
            raise ValueError("authority_boundary entries must be text")


def validate_package_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_public_package.PACKAGE_REPORT_SCHEMA:
        raise ValueError("unsupported public package report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("public package report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "package_index_id", "experiment_scope", "overall_status", "summary"]:
        if key not in report:
            raise ValueError(f"public package report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "package_index_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"public package report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["overall_status"] not in peer_mesh_public_package.PACKAGE_STATUSES:
        raise ValueError("unsupported public package status")


def validate_redaction_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_private_evidence_redaction.REDACTION_REPORT_SCHEMA:
        raise ValueError("unsupported private evidence redaction report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("private evidence redaction report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "redaction_id",
        "experiment_scope",
        "checklist_status",
        "overall_status",
        "redaction_items",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"private evidence redaction report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "redaction_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"private evidence redaction report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["overall_status"] not in peer_mesh_private_evidence_redaction.OVERALL_STATUSES:
        raise ValueError("unsupported private evidence redaction status")
    if not isinstance(report["redaction_items"], list):
        raise ValueError("redaction_items must be an array")
    for item in report["redaction_items"]:
        validate_redaction_item(item)


def validate_redaction_item(item: Any) -> None:
    if not isinstance(item, dict):
        raise ValueError("redaction item must be an object")
    for key in [
        "slot_id",
        "evidence_kind",
        "expected_schema",
        "required",
        "collection_status",
        "public_release",
        "public_derivative_schema",
        "redaction_status",
        "reason",
    ]:
        if key not in item:
            raise ValueError(f"redaction item missing {key}")
    for key in ["slot_id", "evidence_kind", "expected_schema", "collection_status", "public_release", "public_derivative_schema", "redaction_status", "reason"]:
        if not isinstance(item[key], str):
            raise ValueError(f"redaction item missing {key}")
    if not isinstance(item["required"], bool):
        raise ValueError("redaction item missing required")
    if item["public_release"] not in {"sanitized_derivative_only", "private_only", ""}:
        raise ValueError("unsupported public_release")
    if item["redaction_status"] not in peer_mesh_private_evidence_redaction.REDACTION_STATUSES:
        raise ValueError("unsupported redaction_status")


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported import plan check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def identity_checks(manifest: dict[str, Any], package_report: dict[str, Any], redaction_report: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for check_id, report in [("package_identity", package_report), ("redaction_identity", redaction_report)]:
        mismatches = []
        for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
            if report.get(key) != manifest[key]:
                mismatches.append(key)
        if mismatches:
            checks.append(check_entry(check_id, "failed", ",".join(mismatches), "match", f"{check_id} does not match import plan manifest"))
        else:
            checks.append(check_entry(check_id, "passed", "match", "match", f"{check_id} matches import plan manifest"))
    return checks


def package_status_check(manifest: dict[str, Any], package_report: dict[str, Any]) -> dict[str, Any]:
    status = str(package_report["overall_status"])
    if status == "package_ready":
        return check_entry("package_status", "passed", status, "package_ready", "public package is ready for import planning")
    if status == "manual_review" and not manifest["require_package_ready"]:
        return check_entry("package_status", "manual_review", status, "package_ready", "public package needs manual review before import planning")
    return check_entry("package_status", "failed", status, "package_ready", "public package is not ready for import planning")


def redaction_status_check(manifest: dict[str, Any], redaction_report: dict[str, Any]) -> dict[str, Any]:
    status = str(redaction_report["overall_status"])
    if status == "redaction_ready":
        return check_entry("redaction_status", "passed", status, "redaction_ready", "redaction plan is ready for sanitized derivative import")
    if status == "manual_review" and not manifest["require_redaction_ready"]:
        return check_entry("redaction_status", "manual_review", status, "redaction_ready", "redaction plan needs manual review before sanitized derivative import")
    return check_entry("redaction_status", "failed", status, "redaction_ready", "redaction plan is not ready for sanitized derivative import")


def derivative_slot_check(items: list[dict[str, Any]]) -> dict[str, Any]:
    count = sum(1 for item in items if item["public_release"] == "sanitized_derivative_only")
    if count < 1:
        return check_entry("sanitized_derivative_slots", "failed", count, "> 0", "no sanitized derivative slots are declared")
    return check_entry("sanitized_derivative_slots", "passed", count, "> 0", "sanitized derivative slots are declared")


def import_item(item: dict[str, Any], redaction_status: str) -> dict[str, Any]:
    public_release = str(item["public_release"])
    derivative_schema = str(item["public_derivative_schema"])
    if public_release == "private_only":
        status = "private_only"
        reason = "item remains private-only and is not imported into public artifacts"
    elif not derivative_schema:
        status = "missing_derivative_schema"
        reason = "sanitized derivative item is missing a public derivative schema"
    elif redaction_status == "redaction_ready" and item["redaction_status"] == "ready_for_sanitized_derivative":
        status = "ready_for_public_derivative"
        reason = "item can be imported after sanitized private derivative evidence is supplied"
    else:
        status = "blocked_until_redaction_ready"
        reason = "item waits for redaction readiness and private sanitized derivative evidence"
    return {
        "slot_id": item["slot_id"],
        "evidence_kind": item["evidence_kind"],
        "expected_schema": item["expected_schema"],
        "required": item["required"],
        "collection_status": item["collection_status"],
        "public_release": public_release,
        "public_derivative_schema": derivative_schema,
        "import_status": status,
        "reason": reason,
    }


def import_items(redaction_report: dict[str, Any]) -> list[dict[str, Any]]:
    redaction_status = str(redaction_report["overall_status"])
    return [import_item(item, redaction_status) for item in redaction_report["redaction_items"]]


def summarize(checks: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "import_item_count": len(items),
        "private_only_item_count": sum(1 for item in items if item["import_status"] == "private_only"),
        "ready_derivative_item_count": sum(1 for item in items if item["import_status"] == "ready_for_public_derivative"),
        "blocked_derivative_item_count": sum(1 for item in items if item["import_status"] == "blocked_until_redaction_ready"),
        "missing_derivative_schema_count": sum(1 for item in items if item["import_status"] == "missing_derivative_schema"),
    }


def overall_status(checks: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "import_blocked"
    if int(summary["missing_derivative_schema_count"]) > 0:
        return "import_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "import_ready"


def build_import_plan_report(
    manifest: dict[str, Any],
    package_report: dict[str, Any],
    redaction_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    validate_package_report(package_report)
    validate_redaction_report(redaction_report)
    items = import_items(redaction_report)
    checks = [
        *identity_checks(manifest, package_report, redaction_report),
        package_status_check(manifest, package_report),
        redaction_status_check(manifest, redaction_report),
        derivative_slot_check(items),
    ]
    summary = summarize(checks, items)
    return {
        "schema": IMPORT_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "import_plan_id": manifest["import_plan_id"],
        "experiment_scope": manifest["experiment_scope"],
        "package_status": package_report["overall_status"],
        "redaction_status": redaction_report["overall_status"],
        "overall_status": overall_status(checks, summary),
        "checks": checks,
        "import_items": items,
        "summary": summary,
        "authority_boundary": [
            "Private import plan reports describe public-safe sanitized derivative import readiness only.",
            "Private import plan reports do not read private evidence, sanitize live artifacts, approve live work, select endpoints, collect evidence, replay evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Private import plan reports do not carry private endpoint values, raw network addresses, raw device identifiers, raw logs, pairing material, app package IDs, operator identity, or credential material.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    validate_manifest(manifest)
    package_report = load_json(root / str(manifest["package_report_path"]))
    redaction_report = load_json(root / str(manifest["redaction_report_path"]))
    write_json(args.output, build_import_plan_report(manifest, package_report, redaction_report, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe private evidence import plan.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
