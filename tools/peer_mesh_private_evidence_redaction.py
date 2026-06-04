#!/usr/bin/env python3
"""Public-safe private evidence redaction plan for peer mesh preparation.

The redaction report turns a public-safe private evidence checklist into a
public derivative policy for each declared evidence slot. It does not read
private evidence, sanitize live artifacts, approve live work, select endpoints,
monitor peers, probe peers, open sockets, copy files, discover devices, use
ADB, send gossip, launch apps, execute commands, or execute validation slots.
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
import peer_mesh_private_evidence_checklist
import peer_mesh_private_run_handoff


REDACTION_MANIFEST_SCHEMA = "quest-termux-lab.peer-private-evidence-redaction-manifest.v1"
REDACTION_REPORT_SCHEMA = "quest-termux-lab.peer-private-evidence-redaction-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
OVERALL_STATUSES = {"redaction_ready", "manual_review", "redaction_blocked"}
PUBLIC_RELEASE_VALUES = {"sanitized_derivative_only", "private_only"}
REDACTION_STATUSES = {
    "blocked_until_private_evidence",
    "ready_for_sanitized_derivative",
    "private_only",
}
FORBIDDEN_VALUE_CLASSES = {
    "app_package_ids",
    "credential_material",
    "local_paths",
    "operator_identity",
    "pairing_material",
    "private_endpoint_values",
    "raw_device_identifiers",
    "raw_gossip_bodies",
    "raw_logs",
    "raw_network_addresses",
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


def validate_text_array(value: Any, label: str, allowed_values: set[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        if allowed_values is not None and item not in allowed_values:
            raise ValueError(f"{label} contains unsupported entry")
        result.append(item)
    return result


def validate_rule(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("evidence_redaction_rules entries must be objects")
    for key in [
        "evidence_kind",
        "public_release",
        "public_derivative_schema",
        "forbidden_value_classes",
        "required_redaction_notes",
    ]:
        if key not in entry:
            raise ValueError(f"evidence redaction rule missing {key}")
    for key in ["evidence_kind", "public_release", "public_derivative_schema"]:
        if not isinstance(entry[key], str):
            raise ValueError(f"evidence redaction rule missing {key}")
    if not entry["evidence_kind"]:
        raise ValueError("evidence redaction rule missing evidence_kind")
    if entry["evidence_kind"] not in peer_mesh_private_run_handoff.EVIDENCE_SLOT_KINDS:
        raise ValueError("unsupported evidence_kind")
    if entry["public_release"] not in PUBLIC_RELEASE_VALUES:
        raise ValueError("unsupported public_release")
    if entry["public_release"] == "sanitized_derivative_only" and not entry["public_derivative_schema"]:
        raise ValueError("sanitized derivative rules must declare a public_derivative_schema")
    validate_text_array(entry["forbidden_value_classes"], "forbidden_value_classes", FORBIDDEN_VALUE_CLASSES)
    validate_text_array(entry["required_redaction_notes"], "required_redaction_notes")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != REDACTION_MANIFEST_SCHEMA:
        raise ValueError("unsupported private evidence redaction manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("private evidence redaction manifest contains command-like or credential-like fields")
    for key in [
        "redaction_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "checklist_report_path",
        "require_checklist_ready",
        "default_public_release",
        "evidence_redaction_rules",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"private evidence redaction manifest missing {key}")
    for key in ["redaction_id", "fleet_id", "source_agent_id", "observed_at", "checklist_report_path"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"private evidence redaction manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_report_path(str(manifest["checklist_report_path"]), "checklist_report_path")
    if not isinstance(manifest["require_checklist_ready"], bool):
        raise ValueError("require_checklist_ready must be boolean")
    if manifest["default_public_release"] not in PUBLIC_RELEASE_VALUES:
        raise ValueError("unsupported default_public_release")
    rules = manifest["evidence_redaction_rules"]
    if not isinstance(rules, list) or not rules:
        raise ValueError("evidence_redaction_rules must be a non-empty array")
    rule_kinds = []
    for rule in rules:
        validate_rule(rule)
        rule_kinds.append(str(rule["evidence_kind"]))
    if len(rule_kinds) != len(set(rule_kinds)):
        raise ValueError("evidence redaction rule evidence_kind entries must be unique")
    boundary = manifest["authority_boundary"]
    if not isinstance(boundary, list) or not boundary:
        raise ValueError("authority_boundary must be a non-empty array")
    for item in boundary:
        if not isinstance(item, str) or not item:
            raise ValueError("authority_boundary entries must be text")


def validate_check(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("checklist check must be an object")
    for key in ["check_id", "status", "observed", "threshold", "reason"]:
        if not isinstance(entry.get(key), str):
            raise ValueError(f"checklist check missing {key}")
    if entry["status"] not in peer_mesh_private_evidence_checklist.CHECK_STATUSES:
        raise ValueError("unsupported checklist check status")


def validate_private_evidence_item(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("private evidence item must be an object")
    for key in ["slot_id", "evidence_kind", "expected_schema", "collection_status", "reason"]:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"private evidence item missing {key}")
    if not isinstance(entry.get("required"), bool):
        raise ValueError("private evidence item missing required")
    if entry["evidence_kind"] not in peer_mesh_private_run_handoff.EVIDENCE_SLOT_KINDS:
        raise ValueError("unsupported private evidence kind")
    if entry["collection_status"] not in peer_mesh_private_evidence_checklist.COLLECTION_STATUSES:
        raise ValueError("unsupported private evidence collection status")
    if entry.get("public_placeholder") is not True:
        raise ValueError("private evidence item must remain a public placeholder")


def validate_checklist_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_private_evidence_checklist.CHECKLIST_REPORT_SCHEMA:
        raise ValueError("unsupported private evidence checklist report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("private evidence checklist report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "checklist_id",
        "experiment_scope",
        "handoff_status",
        "overall_status",
        "checks",
        "private_evidence_items",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"private evidence checklist report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "checklist_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"private evidence checklist report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["overall_status"] not in peer_mesh_private_evidence_checklist.OVERALL_STATUSES:
        raise ValueError("unsupported private evidence checklist status")
    if not isinstance(report["checks"], list):
        raise ValueError("private evidence checklist checks must be an array")
    for check in report["checks"]:
        validate_check(check)
    if not isinstance(report["private_evidence_items"], list):
        raise ValueError("private evidence items must be an array")
    for item in report["private_evidence_items"]:
        validate_private_evidence_item(item)


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported redaction check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def identity_check(manifest: dict[str, Any], checklist_report: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
        if checklist_report.get(key) != manifest[key]:
            mismatches.append(key)
    if mismatches:
        return check_entry("checklist_identity", "failed", ",".join(mismatches), "match", "checklist identity does not match redaction manifest")
    return check_entry("checklist_identity", "passed", "match", "match", "checklist identity matches redaction manifest")


def checklist_status_check(manifest: dict[str, Any], checklist_report: dict[str, Any]) -> dict[str, Any]:
    status = str(checklist_report["overall_status"])
    if status == "checklist_ready":
        return check_entry("checklist_status", "passed", status, "checklist_ready", "checklist is ready for redaction planning")
    if status == "manual_review" and not manifest["require_checklist_ready"]:
        return check_entry("checklist_status", "manual_review", status, "checklist_ready", "checklist requires manual review before redaction planning")
    return check_entry("checklist_status", "failed", status, "checklist_ready", "checklist is not ready for redaction planning")


def rule_coverage_check(manifest: dict[str, Any], checklist_report: dict[str, Any]) -> dict[str, Any]:
    rule_kinds = {str(rule["evidence_kind"]) for rule in manifest["evidence_redaction_rules"]}
    item_kinds = {str(item["evidence_kind"]) for item in checklist_report["private_evidence_items"]}
    missing = sorted(item_kinds - rule_kinds)
    if missing:
        return check_entry("rule_coverage", "failed", ",".join(missing), "all evidence kinds covered", "redaction rules are missing for checklist evidence kinds")
    return check_entry("rule_coverage", "passed", len(rule_kinds), f">= {len(item_kinds)}", "redaction rules cover checklist evidence kinds")


def required_items_check(checklist_report: dict[str, Any]) -> dict[str, Any]:
    required_count = sum(1 for item in checklist_report["private_evidence_items"] if item["required"])
    if required_count < 1:
        return check_entry("required_private_evidence_items", "failed", required_count, "> 0", "no required private evidence items are declared")
    return check_entry("required_private_evidence_items", "passed", required_count, "> 0", "required private evidence items are declared")


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "redaction_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "redaction_ready"


def rule_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(rule["evidence_kind"]): rule for rule in manifest["evidence_redaction_rules"]}


def redaction_item(item: dict[str, Any], rule: dict[str, Any] | None, checklist_status: str) -> dict[str, Any]:
    if rule is None:
        return {
            "slot_id": item["slot_id"],
            "evidence_kind": item["evidence_kind"],
            "expected_schema": item["expected_schema"],
            "required": item["required"],
            "collection_status": item["collection_status"],
            "public_release": "",
            "public_derivative_schema": "",
            "redaction_status": "blocked_until_private_evidence",
            "forbidden_value_classes": [],
            "required_redaction_notes": [],
            "reason": "missing redaction rule for evidence kind",
        }
    public_release = str(rule["public_release"])
    if public_release == "private_only":
        status = "private_only"
        reason = "private evidence item is governed by a private-only rule"
    elif checklist_status == "checklist_ready":
        status = "ready_for_sanitized_derivative"
        reason = "redaction rule is ready to apply after private evidence is collected"
    else:
        status = "blocked_until_private_evidence"
        reason = "redaction rule is declared, but checklist readiness is blocked or pending manual review"
    return {
        "slot_id": item["slot_id"],
        "evidence_kind": item["evidence_kind"],
        "expected_schema": item["expected_schema"],
        "required": item["required"],
        "collection_status": item["collection_status"],
        "public_release": public_release,
        "public_derivative_schema": rule["public_derivative_schema"],
        "redaction_status": status,
        "forbidden_value_classes": list(rule["forbidden_value_classes"]),
        "required_redaction_notes": list(rule["required_redaction_notes"]),
        "reason": reason,
    }


def redaction_items(manifest: dict[str, Any], checklist_report: dict[str, Any]) -> list[dict[str, Any]]:
    rules_by_kind = rule_map(manifest)
    checklist_status = str(checklist_report["overall_status"])
    return [
        redaction_item(item, rules_by_kind.get(str(item["evidence_kind"])), checklist_status)
        for item in checklist_report["private_evidence_items"]
    ]


def summarize(checks: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "redaction_item_count": len(items),
        "required_redaction_item_count": sum(1 for item in items if item["required"]),
        "private_only_item_count": sum(1 for item in items if item["redaction_status"] == "private_only"),
        "sanitized_derivative_item_count": sum(1 for item in items if item["public_release"] == "sanitized_derivative_only"),
        "ready_derivative_item_count": sum(1 for item in items if item["redaction_status"] == "ready_for_sanitized_derivative"),
        "blocked_redaction_item_count": sum(1 for item in items if item["redaction_status"] == "blocked_until_private_evidence"),
        "missing_rule_count": sum(1 for item in items if not item["public_release"]),
    }


def build_redaction_report(
    manifest: dict[str, Any],
    checklist_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    validate_checklist_report(checklist_report)
    checks = [
        identity_check(manifest, checklist_report),
        checklist_status_check(manifest, checklist_report),
        rule_coverage_check(manifest, checklist_report),
        required_items_check(checklist_report),
    ]
    items = redaction_items(manifest, checklist_report)
    return {
        "schema": REDACTION_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "redaction_id": manifest["redaction_id"],
        "checklist_id": checklist_report["checklist_id"],
        "experiment_scope": manifest["experiment_scope"],
        "checklist_status": checklist_report["overall_status"],
        "overall_status": overall_status(checks),
        "checks": checks,
        "redaction_items": items,
        "summary": summarize(checks, items),
        "authority_boundary": [
            "Private evidence redaction reports declare public derivative policy for private evidence slots only.",
            "Private evidence redaction reports do not read private evidence, sanitize live artifacts, approve live work, select endpoints, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Private evidence redaction reports do not carry private endpoint values, raw network addresses, raw device identifiers, raw logs, pairing material, app package IDs, operator identity, or credential material.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    validate_manifest(manifest)
    checklist_report = load_json(root / str(manifest["checklist_report_path"]))
    write_json(args.output, build_redaction_report(manifest, checklist_report, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe private evidence redaction plan.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
