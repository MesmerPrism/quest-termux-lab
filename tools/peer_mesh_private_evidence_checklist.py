#!/usr/bin/env python3
"""Public-safe private evidence checklist for peer mesh handoff.

The checklist turns a sanitized private-run handoff report into pending private
evidence slots. It does not approve live work, select endpoints, collect
evidence, monitor peers, probe peers, open sockets, copy files, discover
devices, use ADB, send gossip, launch apps, execute commands, or execute
validation slots.
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
import peer_mesh_private_run_handoff


CHECKLIST_MANIFEST_SCHEMA = "quest-termux-lab.peer-private-evidence-checklist-manifest.v1"
CHECKLIST_REPORT_SCHEMA = "quest-termux-lab.peer-private-evidence-checklist-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
OVERALL_STATUSES = {"checklist_ready", "manual_review", "checklist_blocked"}
COLLECTION_STATUSES = {"pending_private_run", "optional_pending_private_run"}


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
    if manifest.get("schema") != CHECKLIST_MANIFEST_SCHEMA:
        raise ValueError("unsupported private evidence checklist manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("private evidence checklist manifest contains command-like or credential-like fields")
    for key in [
        "checklist_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "handoff_report_path",
        "require_handoff_ready",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"private evidence checklist manifest missing {key}")
    for key in ["checklist_id", "fleet_id", "source_agent_id", "observed_at", "handoff_report_path"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"private evidence checklist manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_report_path(str(manifest["handoff_report_path"]), "handoff_report_path")
    if not isinstance(manifest["require_handoff_ready"], bool):
        raise ValueError("require_handoff_ready must be boolean")
    boundary = manifest["authority_boundary"]
    if not isinstance(boundary, list) or not boundary:
        raise ValueError("authority_boundary must be a non-empty array")
    for item in boundary:
        if not isinstance(item, str) or not item:
            raise ValueError("authority_boundary entries must be text")


def validate_check(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("handoff check must be an object")
    for key in ["check_id", "status", "observed", "threshold", "reason"]:
        if not isinstance(entry.get(key), str):
            raise ValueError(f"handoff check missing {key}")
    if entry["status"] not in peer_mesh_private_run_handoff.CHECK_STATUSES:
        raise ValueError("unsupported handoff check status")


def validate_private_slot(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("private evidence slot must be an object")
    for key in ["slot_id", "evidence_kind", "expected_schema", "status", "reason"]:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"private evidence slot missing {key}")
    if not isinstance(entry.get("required"), bool):
        raise ValueError("private evidence slot missing required")
    if entry["evidence_kind"] not in peer_mesh_private_run_handoff.EVIDENCE_SLOT_KINDS:
        raise ValueError("unsupported private evidence kind")
    if entry["status"] != "declared":
        raise ValueError("private evidence slot status must be declared")


def validate_handoff_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_private_run_handoff.HANDOFF_REPORT_SCHEMA:
        raise ValueError("unsupported private-run handoff report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("private-run handoff report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "handoff_id",
        "experiment_scope",
        "review_bundle_status",
        "overall_status",
        "checks",
        "private_evidence_slots",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"private-run handoff report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "handoff_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"private-run handoff report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["overall_status"] not in peer_mesh_private_run_handoff.OVERALL_STATUSES:
        raise ValueError("unsupported private-run handoff status")
    if not isinstance(report["checks"], list):
        raise ValueError("private-run handoff checks must be an array")
    for check in report["checks"]:
        validate_check(check)
    if not isinstance(report["private_evidence_slots"], list):
        raise ValueError("private evidence slots must be an array")
    for slot in report["private_evidence_slots"]:
        validate_private_slot(slot)


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported checklist check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def identity_check(manifest: dict[str, Any], handoff_report: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
        if handoff_report.get(key) != manifest[key]:
            mismatches.append(key)
    if mismatches:
        return check_entry("handoff_identity", "failed", ",".join(mismatches), "match", "handoff identity does not match checklist manifest")
    return check_entry("handoff_identity", "passed", "match", "match", "handoff identity matches checklist manifest")


def handoff_status_check(manifest: dict[str, Any], handoff_report: dict[str, Any]) -> dict[str, Any]:
    status = str(handoff_report["overall_status"])
    if status == "handoff_ready":
        return check_entry("handoff_status", "passed", status, "handoff_ready", "handoff is ready for private evidence collection")
    if status == "manual_review" and not manifest["require_handoff_ready"]:
        return check_entry("handoff_status", "manual_review", status, "handoff_ready", "handoff requires manual review before private evidence collection")
    return check_entry("handoff_status", "failed", status, "handoff_ready", "handoff is not ready for private evidence collection")


def slot_count_check(slots: list[dict[str, Any]]) -> dict[str, Any]:
    required_count = sum(1 for slot in slots if slot["required"])
    if required_count < 1:
        return check_entry("required_private_evidence_slots", "failed", required_count, "> 0", "no required private evidence slots are declared")
    return check_entry("required_private_evidence_slots", "passed", required_count, "> 0", "required private evidence slots are declared")


def evidence_items(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for slot in slots:
        required = bool(slot["required"])
        items.append(
            {
                "slot_id": slot["slot_id"],
                "evidence_kind": slot["evidence_kind"],
                "expected_schema": slot["expected_schema"],
                "required": required,
                "collection_status": "pending_private_run" if required else "optional_pending_private_run",
                "public_placeholder": True,
                "reason": slot["reason"],
            }
        )
    return items


def summarize(checks: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "private_evidence_item_count": len(items),
        "required_private_evidence_item_count": sum(1 for item in items if item["required"]),
        "optional_private_evidence_item_count": sum(1 for item in items if not item["required"]),
    }


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "checklist_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "checklist_ready"


def build_checklist_report(
    manifest: dict[str, Any],
    handoff_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    validate_handoff_report(handoff_report)
    items = evidence_items(handoff_report["private_evidence_slots"])
    checks = [
        identity_check(manifest, handoff_report),
        handoff_status_check(manifest, handoff_report),
        slot_count_check(handoff_report["private_evidence_slots"]),
    ]
    return {
        "schema": CHECKLIST_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "checklist_id": manifest["checklist_id"],
        "experiment_scope": manifest["experiment_scope"],
        "handoff_status": handoff_report["overall_status"],
        "overall_status": overall_status(checks),
        "checks": checks,
        "private_evidence_items": items,
        "summary": summarize(checks, items),
        "authority_boundary": [
            "Private evidence checklists declare pending private evidence items only.",
            "Private evidence checklists do not approve live work, select endpoints, collect evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Private evidence checklists do not carry private endpoint values, gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    root = Path(args.artifact_root)
    validate_manifest(manifest)
    handoff_report = load_json(root / str(manifest["handoff_report_path"]))
    write_json(args.output, build_checklist_report(manifest, handoff_report, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe private evidence checklist.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
