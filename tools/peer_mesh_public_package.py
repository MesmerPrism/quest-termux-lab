#!/usr/bin/env python3
"""Public-safe peer mesh package readiness index.

The package index checks that public peer-mesh fixtures, docs, schemas, tools,
tests, and declared validation evidence are coherent enough for public review.
It does not execute validation slots, approve live work, select endpoints,
collect evidence, replay evidence, monitor peers, probe peers, open sockets,
copy files, discover devices, use ADB, send gossip, launch apps, or execute
commands.
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


PACKAGE_MANIFEST_SCHEMA = "quest-termux-lab.peer-public-package-manifest.v1"
PACKAGE_REPORT_SCHEMA = "quest-termux-lab.peer-public-package-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
PACKAGE_STATUSES = {"package_ready", "manual_review", "package_blocked"}
FILE_ROLES = {"doc", "tool", "test", "schema", "example"}
STATUS_CLASSES = {"ready", "manual_review", "blocked"}
DECLARED_VALIDATION_STATUSES = {"passed", "manual_review", "failed", "not_run"}


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


def validate_relative_path(value: str, label: str) -> None:
    peer_mesh_evidence_intake.validate_artifact_path(value, label)
    if Path(value).suffix.lower() not in {".json", ".md", ".py"}:
        raise ValueError(f"{label} must reference a json, md, or py file")


def validate_text_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        result.append(item)
    return result


def validate_file_ref(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("required_file_refs entries must be objects")
    for key in ["file_id", "file_role", "path", "reason"]:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"required_file_refs entry missing {key}")
    if entry["file_role"] not in FILE_ROLES:
        raise ValueError("unsupported file_role")
    validate_relative_path(str(entry["path"]), "required_file_refs.path")


def validate_status_expectation(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("status_expectations entries must be objects")
    for key in [
        "expectation_id",
        "path",
        "expected_schema",
        "status_field",
        "expected_status_class",
        "ready_values",
        "manual_review_values",
        "blocked_values",
        "reason",
    ]:
        if key not in entry:
            raise ValueError(f"status expectation missing {key}")
    for key in ["expectation_id", "path", "expected_schema", "status_field", "expected_status_class", "reason"]:
        if not isinstance(entry[key], str) or not entry[key]:
            raise ValueError(f"status expectation missing {key}")
    validate_relative_path(str(entry["path"]), "status_expectations.path")
    if Path(str(entry["path"])).suffix.lower() != ".json":
        raise ValueError("status_expectations.path must reference a json file")
    if entry["expected_status_class"] not in STATUS_CLASSES:
        raise ValueError("unsupported expected_status_class")
    for key in ["ready_values", "manual_review_values", "blocked_values"]:
        validate_text_array(entry[key], f"status_expectations.{key}")


def validate_declared_validation(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("declared_validation_slots entries must be objects")
    for key in ["validation_id", "observed_status", "evidence_note", "reason"]:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"declared validation slot missing {key}")
    if entry["observed_status"] not in DECLARED_VALIDATION_STATUSES:
        raise ValueError("unsupported declared validation status")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != PACKAGE_MANIFEST_SCHEMA:
        raise ValueError("unsupported peer public package manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("peer public package manifest contains command-like or credential-like fields")
    for key in [
        "package_index_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "required_file_refs",
        "status_expectations",
        "declared_validation_slots",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"peer public package manifest missing {key}")
    for key in ["package_index_id", "fleet_id", "source_agent_id", "observed_at"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"peer public package manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    for key in ["required_file_refs", "status_expectations", "declared_validation_slots", "authority_boundary"]:
        if not isinstance(manifest[key], list):
            raise ValueError(f"peer public package manifest {key} must be an array")
    if not manifest["required_file_refs"]:
        raise ValueError("required_file_refs must not be empty")
    if not manifest["status_expectations"]:
        raise ValueError("status_expectations must not be empty")
    if not manifest["declared_validation_slots"]:
        raise ValueError("declared_validation_slots must not be empty")
    for entry in manifest["required_file_refs"]:
        validate_file_ref(entry)
    for entry in manifest["status_expectations"]:
        validate_status_expectation(entry)
    for entry in manifest["declared_validation_slots"]:
        validate_declared_validation(entry)
    file_ids = [str(entry["file_id"]) for entry in manifest["required_file_refs"]]
    expectation_ids = [str(entry["expectation_id"]) for entry in manifest["status_expectations"]]
    validation_ids = [str(entry["validation_id"]) for entry in manifest["declared_validation_slots"]]
    if len(file_ids) != len(set(file_ids)):
        raise ValueError("required_file_refs file_id entries must be unique")
    if len(expectation_ids) != len(set(expectation_ids)):
        raise ValueError("status_expectations expectation_id entries must be unique")
    if len(validation_ids) != len(set(validation_ids)):
        raise ValueError("declared_validation_slots validation_id entries must be unique")
    if not manifest["authority_boundary"]:
        raise ValueError("authority_boundary must not be empty")
    for entry in manifest["authority_boundary"]:
        if not isinstance(entry, str) or not entry:
            raise ValueError("authority_boundary entries must be text")


def identity_check(document: dict[str, Any], manifest: dict[str, Any]) -> None:
    if document.get("fleet_id") and document.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError("fleet_id mismatch")
    if document.get("source_agent_id") and document.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError("source_agent_id mismatch")
    if document.get("experiment_scope") and document.get("experiment_scope") != manifest["experiment_scope"]:
        raise ValueError("experiment_scope mismatch")


def file_entry(entry: dict[str, Any], root: Path) -> dict[str, Any]:
    path_text = str(entry["path"])
    path = root / path_text
    if not path.is_file():
        status = "failed"
        reason = "required file missing"
    elif path.suffix.lower() not in {".json", ".md", ".py"}:
        status = "failed"
        reason = "required file has unsupported suffix"
    else:
        status = "passed"
        reason = "required file exists"
    return {
        "file_id": entry["file_id"],
        "file_role": entry["file_role"],
        "path": path_text,
        "status": status,
        "reason": reason,
    }


def resolve_status(document: dict[str, Any], status_field: str) -> str:
    value: Any = document
    for part in status_field.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError("status field missing")
        value = value[part]
    return str(value)


def status_class_for(observed: str, entry: dict[str, Any]) -> str:
    if observed in set(entry["ready_values"]):
        return "ready"
    if observed in set(entry["manual_review_values"]):
        return "manual_review"
    if observed in set(entry["blocked_values"]):
        return "blocked"
    raise ValueError("status value is not declared by package index")


def status_expectation_entry(entry: dict[str, Any], manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    path_text = str(entry["path"])
    expected_schema = str(entry["expected_schema"])
    path = root / path_text
    if not path.is_file():
        return {
            "expectation_id": entry["expectation_id"],
            "path": path_text,
            "expected_schema": expected_schema,
            "observed_schema": "",
            "status_field": entry["status_field"],
            "observed_value": "",
            "observed_status_class": "blocked",
            "expected_status_class": entry["expected_status_class"],
            "status": "failed",
            "reason": "status artifact missing",
        }
    try:
        document = load_json(path)
        if peer_mesh_gossip.contains_forbidden_key(document):
            raise ValueError("status artifact contains command-like or credential-like fields")
        observed_schema = str(document.get("schema", ""))
        if observed_schema != expected_schema:
            raise ValueError("schema mismatch")
        identity_check(document, manifest)
        observed_value = resolve_status(document, str(entry["status_field"]))
        observed_class = status_class_for(observed_value, entry)
        expected_class = str(entry["expected_status_class"])
        if observed_class == expected_class:
            status = "passed"
            reason = "status artifact matches expected package class"
        else:
            status = "failed"
            reason = "status artifact class does not match expected package class"
    except (OSError, json.JSONDecodeError, ValueError) as error:
        observed_schema = ""
        observed_value = ""
        observed_class = "blocked"
        status = "failed"
        reason = str(error)
    return {
        "expectation_id": entry["expectation_id"],
        "path": path_text,
        "expected_schema": expected_schema,
        "observed_schema": observed_schema,
        "status_field": entry["status_field"],
        "observed_value": observed_value,
        "observed_status_class": observed_class,
        "expected_status_class": entry["expected_status_class"],
        "status": status,
        "reason": reason,
    }


def validation_slot_entry(entry: dict[str, Any]) -> dict[str, Any]:
    observed = str(entry["observed_status"])
    if observed == "passed":
        status = "passed"
        reason = "declared validation slot passed"
    elif observed == "manual_review":
        status = "manual_review"
        reason = "declared validation slot needs manual review"
    else:
        status = "failed"
        reason = "declared validation slot is failed or not run"
    return {
        "validation_id": entry["validation_id"],
        "observed_status": observed,
        "status": status,
        "evidence_note": entry["evidence_note"],
        "reason": reason,
    }


def summarize(
    files: list[dict[str, Any]],
    expectations: list[dict[str, Any]],
    validations: list[dict[str, Any]],
) -> dict[str, Any]:
    entries = files + expectations + validations
    return {
        "entry_count": len(entries),
        "passed_count": sum(1 for entry in entries if entry["status"] == "passed"),
        "manual_review_count": sum(1 for entry in entries if entry["status"] == "manual_review"),
        "failed_count": sum(1 for entry in entries if entry["status"] == "failed"),
        "required_file_count": len(files),
        "missing_file_count": sum(1 for entry in files if entry["status"] == "failed"),
        "status_expectation_count": len(expectations),
        "status_expectation_failed_count": sum(1 for entry in expectations if entry["status"] == "failed"),
        "declared_validation_count": len(validations),
        "declared_validation_failed_count": sum(1 for entry in validations if entry["status"] == "failed"),
    }


def overall_status(summary: dict[str, Any]) -> str:
    if int(summary["failed_count"]) > 0:
        return "package_blocked"
    if int(summary["manual_review_count"]) > 0:
        return "manual_review"
    return "package_ready"


def build_package_report(
    manifest: dict[str, Any],
    root: Path,
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    files = [file_entry(entry, root) for entry in manifest["required_file_refs"]]
    expectations = [
        status_expectation_entry(entry, manifest, root)
        for entry in manifest["status_expectations"]
    ]
    validations = [validation_slot_entry(entry) for entry in manifest["declared_validation_slots"]]
    summary = summarize(files, expectations, validations)
    return {
        "schema": PACKAGE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "package_index_id": manifest["package_index_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": overall_status(summary),
        "required_files": files,
        "status_expectations": expectations,
        "declared_validation_slots": validations,
        "summary": summary,
        "authority_boundary": [
            "Peer public package reports summarize public-safe package readiness only.",
            "Peer public package reports can treat deliberately blocked private evidence placeholders as expected public package state.",
            "Peer public package reports do not execute validation slots, approve live work, select endpoints, collect evidence, replay evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, or execute commands.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    write_json(
        args.output,
        build_package_report(
            manifest,
            Path(args.artifact_root),
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer mesh package readiness index.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
