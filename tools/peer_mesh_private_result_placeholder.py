#!/usr/bin/env python3
"""Public-safe private result placeholder bundle for peer mesh preparation.

The placeholder report turns an import plan into future public result slots.
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
import peer_mesh_private_import_plan


PLACEHOLDER_MANIFEST_SCHEMA = "quest-termux-lab.peer-private-result-placeholder-manifest.v1"
PLACEHOLDER_REPORT_SCHEMA = "quest-termux-lab.peer-private-result-placeholder-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
OVERALL_STATUSES = {"result_placeholders_ready", "manual_review", "result_placeholders_blocked"}
PLACEHOLDER_STATUSES = {
    "private_only",
    "awaiting_sanitized_derivative_artifact",
    "blocked_until_import_ready",
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
    if manifest.get("schema") != PLACEHOLDER_MANIFEST_SCHEMA:
        raise ValueError("unsupported private result placeholder manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("private result placeholder manifest contains command-like or credential-like fields")
    for key in [
        "placeholder_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "import_plan_report_path",
        "require_import_ready",
        "require_derivative_schemas",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"private result placeholder manifest missing {key}")
    for key in ["placeholder_id", "fleet_id", "source_agent_id", "observed_at", "import_plan_report_path"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"private result placeholder manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_report_path(str(manifest["import_plan_report_path"]), "import_plan_report_path")
    for key in ["require_import_ready", "require_derivative_schemas"]:
        if not isinstance(manifest[key], bool):
            raise ValueError(f"{key} must be boolean")
    boundary = manifest["authority_boundary"]
    if not isinstance(boundary, list) or not boundary:
        raise ValueError("authority_boundary must be a non-empty array")
    for entry in boundary:
        if not isinstance(entry, str) or not entry:
            raise ValueError("authority_boundary entries must be text")


def validate_import_item(item: Any) -> None:
    if not isinstance(item, dict):
        raise ValueError("import item must be an object")
    for key in [
        "slot_id",
        "evidence_kind",
        "expected_schema",
        "required",
        "collection_status",
        "public_release",
        "public_derivative_schema",
        "import_status",
        "reason",
    ]:
        if key not in item:
            raise ValueError(f"import item missing {key}")
    for key in ["slot_id", "evidence_kind", "expected_schema", "collection_status", "public_release", "public_derivative_schema", "import_status", "reason"]:
        if not isinstance(item[key], str):
            raise ValueError(f"import item missing {key}")
    if not isinstance(item["required"], bool):
        raise ValueError("import item missing required")
    if item["import_status"] not in peer_mesh_private_import_plan.ITEM_STATUSES:
        raise ValueError("unsupported import_status")


def validate_import_plan_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_private_import_plan.IMPORT_REPORT_SCHEMA:
        raise ValueError("unsupported private import plan report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("private import plan report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "import_plan_id",
        "experiment_scope",
        "package_status",
        "redaction_status",
        "overall_status",
        "import_items",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"private import plan report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "import_plan_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"private import plan report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["overall_status"] not in peer_mesh_private_import_plan.IMPORT_STATUSES:
        raise ValueError("unsupported private import plan status")
    if not isinstance(report["import_items"], list):
        raise ValueError("import_items must be an array")
    for item in report["import_items"]:
        validate_import_item(item)


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported result placeholder check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def identity_check(manifest: dict[str, Any], import_report: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
        if import_report.get(key) != manifest[key]:
            mismatches.append(key)
    if mismatches:
        return check_entry("import_plan_identity", "failed", ",".join(mismatches), "match", "import plan identity does not match placeholder manifest")
    return check_entry("import_plan_identity", "passed", "match", "match", "import plan identity matches placeholder manifest")


def import_status_check(manifest: dict[str, Any], import_report: dict[str, Any]) -> dict[str, Any]:
    status = str(import_report["overall_status"])
    if status == "import_ready":
        return check_entry("import_plan_status", "passed", status, "import_ready", "import plan is ready for result placeholders")
    if status == "manual_review" and not manifest["require_import_ready"]:
        return check_entry("import_plan_status", "manual_review", status, "import_ready", "import plan needs manual review before result placeholders")
    return check_entry("import_plan_status", "failed", status, "import_ready", "import plan is not ready for public result placeholders")


def derivative_schema_check(manifest: dict[str, Any], slots: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [
        slot["slot_id"]
        for slot in slots
        if slot["public_release"] == "sanitized_derivative_only" and not slot["public_derivative_schema"]
    ]
    if missing and manifest["require_derivative_schemas"]:
        return check_entry("derivative_schema_presence", "failed", ",".join(missing), "all derivative slots carry schema", "sanitized derivative slots are missing public derivative schemas")
    if missing:
        return check_entry("derivative_schema_presence", "manual_review", ",".join(missing), "all derivative slots carry schema", "sanitized derivative schema gaps need manual review")
    return check_entry("derivative_schema_presence", "passed", "all_present", "all derivative slots carry schema", "sanitized derivative slots declare public derivative schemas")


def placeholder_slot(item: dict[str, Any]) -> dict[str, Any]:
    import_status = str(item["import_status"])
    if import_status == "private_only":
        status = "private_only"
        reason = "private-only evidence is represented as a non-public placeholder"
    elif import_status == "ready_for_public_derivative":
        status = "awaiting_sanitized_derivative_artifact"
        reason = "public derivative slot is ready to receive a sanitized artifact after private review"
    elif import_status == "missing_derivative_schema":
        status = "blocked_missing_derivative_schema"
        reason = "public derivative slot is blocked until a derivative schema is declared"
    else:
        status = "blocked_until_import_ready"
        reason = "public derivative slot is blocked until import planning is ready"
    return {
        "slot_id": item["slot_id"],
        "evidence_kind": item["evidence_kind"],
        "expected_schema": item["expected_schema"],
        "required": item["required"],
        "collection_status": item["collection_status"],
        "public_release": item["public_release"],
        "public_derivative_schema": item["public_derivative_schema"],
        "source_import_status": import_status,
        "placeholder_status": status,
        "public_placeholder": True,
        "reason": reason,
    }


def placeholder_slots(import_report: dict[str, Any]) -> list[dict[str, Any]]:
    return [placeholder_slot(item) for item in import_report["import_items"]]


def summarize(checks: list[dict[str, Any]], slots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "placeholder_slot_count": len(slots),
        "private_only_slot_count": sum(1 for slot in slots if slot["placeholder_status"] == "private_only"),
        "awaiting_derivative_slot_count": sum(1 for slot in slots if slot["placeholder_status"] == "awaiting_sanitized_derivative_artifact"),
        "blocked_slot_count": sum(1 for slot in slots if slot["placeholder_status"] in {"blocked_until_import_ready", "blocked_missing_derivative_schema"}),
    }


def overall_status(checks: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "result_placeholders_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    if int(summary["blocked_slot_count"]) > 0:
        return "result_placeholders_blocked"
    return "result_placeholders_ready"


def build_placeholder_report(
    manifest: dict[str, Any],
    import_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    validate_import_plan_report(import_report)
    slots = placeholder_slots(import_report)
    checks = [
        identity_check(manifest, import_report),
        import_status_check(manifest, import_report),
        derivative_schema_check(manifest, slots),
    ]
    summary = summarize(checks, slots)
    return {
        "schema": PLACEHOLDER_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "placeholder_id": manifest["placeholder_id"],
        "experiment_scope": manifest["experiment_scope"],
        "import_plan_status": import_report["overall_status"],
        "overall_status": overall_status(checks, summary),
        "checks": checks,
        "placeholder_slots": slots,
        "summary": summary,
        "authority_boundary": [
            "Private result placeholder reports declare future public result slots only.",
            "Private result placeholder reports do not read private evidence, sanitize live artifacts, approve live work, select endpoints, collect evidence, replay evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Private result placeholder reports do not carry private endpoint values, raw network addresses, raw device identifiers, raw logs, pairing material, app package IDs, operator identity, or credential material.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    validate_manifest(manifest)
    import_report = load_json(root / str(manifest["import_plan_report_path"]))
    write_json(args.output, build_placeholder_report(manifest, import_report, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe private result placeholder report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
