#!/usr/bin/env python3
"""Public-safe fixture index for peer mesh preparation.

The fixture index summarizes the expected public fixture lanes, such as the
blocked baseline, clear repeated-scorecard fixture, and private handoff
placeholders. It does not execute validation slots, approve live work, select
endpoints, collect evidence, monitor peers, probe peers, open sockets, copy
files, discover devices, use ADB, send gossip, launch apps, or execute
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


FIXTURE_INDEX_MANIFEST_SCHEMA = "quest-termux-lab.peer-fixture-index-manifest.v1"
FIXTURE_INDEX_REPORT_SCHEMA = "quest-termux-lab.peer-fixture-index-report.v1"
GROUP_ROLES = {
    "blocked_baseline",
    "cleanup_plan",
    "clear_preflight",
    "clear_repeated_scorecard",
    "file_drop_copy_dry_run",
    "file_drop_inbox_intake",
    "file_drop_staging",
    "private_handoff_pending",
}
GROUP_STATUS_VALUES = {"ready", "manual_review", "blocked"}
EXPECTATION_STATUSES = {"passed", "failed"}
OVERALL_STATUSES = {"fixture_index_ready", "fixture_index_blocked"}


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


def validate_json_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    peer_mesh_evidence_intake.validate_artifact_path(value, label)
    if Path(value).suffix.lower() != ".json":
        raise ValueError(f"{label} must reference a json file")
    return value


def validate_text_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        result.append(item)
    return result


def validate_artifact_ref(item: Any) -> None:
    if not isinstance(item, dict):
        raise ValueError("artifact_refs entries must be objects")
    for key in ["artifact_id", "path", "expected_schema"]:
        if not isinstance(item.get(key), str) or not item[key]:
            raise ValueError(f"artifact_refs entry missing {key}")
    validate_json_path(item["path"], "artifact_refs.path")


def validate_status_check(item: Any, artifact_ids: set[str]) -> None:
    if not isinstance(item, dict):
        raise ValueError("status_checks entries must be objects")
    for key in ["artifact_id", "status_field", "accepted_values", "manual_review_values", "blocked_values"]:
        if key not in item:
            raise ValueError(f"status_checks entry missing {key}")
    if not isinstance(item["artifact_id"], str) or item["artifact_id"] not in artifact_ids:
        raise ValueError("status_checks artifact_id must reference an artifact")
    if not isinstance(item["status_field"], str) or not item["status_field"]:
        raise ValueError("status_checks status_field must be text")
    for key in ["accepted_values", "manual_review_values", "blocked_values"]:
        validate_text_array(item[key], f"status_checks.{key}")


def validate_fixture_group(item: Any) -> None:
    if not isinstance(item, dict):
        raise ValueError("fixture_groups entries must be objects")
    for key in ["group_id", "group_role", "expected_group_status", "artifact_refs", "status_checks", "reason"]:
        if key not in item:
            raise ValueError(f"fixture_groups entry missing {key}")
    for key in ["group_id", "group_role", "expected_group_status", "reason"]:
        if not isinstance(item[key], str) or not item[key]:
            raise ValueError(f"fixture_groups entry missing {key}")
    if item["group_role"] not in GROUP_ROLES:
        raise ValueError("unsupported fixture group role")
    if item["expected_group_status"] not in GROUP_STATUS_VALUES:
        raise ValueError("unsupported expected group status")
    if not isinstance(item["artifact_refs"], list) or not item["artifact_refs"]:
        raise ValueError("fixture group artifact_refs must be a non-empty array")
    if not isinstance(item["status_checks"], list) or not item["status_checks"]:
        raise ValueError("fixture group status_checks must be a non-empty array")
    for artifact in item["artifact_refs"]:
        validate_artifact_ref(artifact)
    artifact_ids = [str(artifact["artifact_id"]) for artifact in item["artifact_refs"]]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("fixture group artifact_id entries must be unique")
    for status_check in item["status_checks"]:
        validate_status_check(status_check, set(artifact_ids))


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != FIXTURE_INDEX_MANIFEST_SCHEMA:
        raise ValueError("unsupported fixture index manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("fixture index manifest contains command-like or credential-like fields")
    for key in [
        "index_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "fixture_groups",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"fixture index manifest missing {key}")
    for key in ["index_id", "fleet_id", "source_agent_id", "observed_at"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"fixture index manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if not isinstance(manifest["fixture_groups"], list) or not manifest["fixture_groups"]:
        raise ValueError("fixture_groups must be a non-empty array")
    group_ids = []
    for group in manifest["fixture_groups"]:
        validate_fixture_group(group)
        group_ids.append(str(group["group_id"]))
    if len(group_ids) != len(set(group_ids)):
        raise ValueError("fixture group ids must be unique")
    boundary = manifest["authority_boundary"]
    if not isinstance(boundary, list) or not boundary:
        raise ValueError("authority_boundary must be a non-empty array")
    for item in boundary:
        if not isinstance(item, str) or not item:
            raise ValueError("authority boundary entries must be text")


def identity_check(document: dict[str, Any], manifest: dict[str, Any]) -> None:
    if document.get("fleet_id") and document.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError("fleet_id mismatch")
    if document.get("source_agent_id") and document.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError("source_agent_id mismatch")
    if document.get("experiment_scope") and document.get("experiment_scope") != manifest["experiment_scope"]:
        raise ValueError("experiment_scope mismatch")


def artifact_entry(item: dict[str, Any], manifest: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path_text = str(item["path"])
    expected_schema = str(item["expected_schema"])
    path = root / path_text
    if not path.is_file():
        return (
            {
                "artifact_id": item["artifact_id"],
                "path": path_text,
                "expected_schema": expected_schema,
                "observed_schema": "",
                "status": "failed",
                "reason": "artifact missing",
            },
            None,
        )
    try:
        document = load_json(path)
        if peer_mesh_gossip.contains_forbidden_key(document):
            raise ValueError("artifact contains command-like or credential-like fields")
        observed_schema = str(document.get("schema", ""))
        if observed_schema != expected_schema:
            raise ValueError("schema mismatch")
        identity_check(document, manifest)
        status = "passed"
        reason = "artifact exists, matches schema, and identity is compatible"
    except (OSError, json.JSONDecodeError, ValueError) as error:
        document = None
        observed_schema = ""
        status = "failed"
        reason = str(error)
    return (
        {
            "artifact_id": item["artifact_id"],
            "path": path_text,
            "expected_schema": expected_schema,
            "observed_schema": observed_schema,
            "status": status,
            "reason": reason,
        },
        document,
    )


def status_check_entry(item: dict[str, Any], documents_by_id: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    artifact_id = str(item["artifact_id"])
    document = documents_by_id.get(artifact_id)
    if document is None:
        return {
            "artifact_id": artifact_id,
            "status_field": str(item["status_field"]),
            "observed_value": "",
            "status_class": "blocked",
            "status": "failed",
            "reason": "status artifact missing or invalid",
        }
    value: Any = document
    for part in str(item["status_field"]).split("."):
        if not isinstance(value, dict) or part not in value:
            return {
                "artifact_id": artifact_id,
                "status_field": str(item["status_field"]),
                "observed_value": "",
                "status_class": "blocked",
                "status": "failed",
                "reason": "status field missing",
            }
        value = value[part]
    observed = str(value)
    if observed in set(item["accepted_values"]):
        status_class = "ready"
        status = "passed"
        reason = "status value is in ready set"
    elif observed in set(item["manual_review_values"]):
        status_class = "manual_review"
        status = "passed"
        reason = "status value is in manual-review set"
    elif observed in set(item["blocked_values"]):
        status_class = "blocked"
        status = "passed"
        reason = "status value is in blocked set"
    else:
        status_class = "blocked"
        status = "failed"
        reason = "status value is not declared by fixture index"
    return {
        "artifact_id": artifact_id,
        "status_field": str(item["status_field"]),
        "observed_value": observed,
        "status_class": status_class,
        "status": status,
        "reason": reason,
    }


def observed_group_status(artifact_entries: list[dict[str, Any]], status_checks: list[dict[str, Any]]) -> str:
    if any(entry["status"] == "failed" for entry in artifact_entries):
        return "blocked"
    if any(entry["status"] == "failed" for entry in status_checks):
        return "blocked"
    classes = {str(entry["status_class"]) for entry in status_checks}
    if "blocked" in classes:
        return "blocked"
    if "manual_review" in classes:
        return "manual_review"
    return "ready"


def group_summary(artifact_entries: list[dict[str, Any]], status_checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_count": len(artifact_entries),
        "artifact_failed_count": sum(1 for entry in artifact_entries if entry["status"] == "failed"),
        "status_check_count": len(status_checks),
        "status_check_failed_count": sum(1 for entry in status_checks if entry["status"] == "failed"),
        "ready_status_count": sum(1 for entry in status_checks if entry["status_class"] == "ready"),
        "manual_review_status_count": sum(1 for entry in status_checks if entry["status_class"] == "manual_review"),
        "blocked_status_count": sum(1 for entry in status_checks if entry["status_class"] == "blocked"),
    }


def fixture_group_entry(group: dict[str, Any], manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    artifact_entries = []
    documents_by_id: dict[str, dict[str, Any] | None] = {}
    for item in group["artifact_refs"]:
        entry, document = artifact_entry(item, manifest, root)
        artifact_entries.append(entry)
        documents_by_id[str(item["artifact_id"])] = document
    status_checks = [
        status_check_entry(item, documents_by_id)
        for item in group["status_checks"]
    ]
    observed = observed_group_status(artifact_entries, status_checks)
    expected = str(group["expected_group_status"])
    expectation = "passed" if observed == expected else "failed"
    return {
        "group_id": group["group_id"],
        "group_role": group["group_role"],
        "expected_group_status": expected,
        "observed_group_status": observed,
        "expectation_status": expectation,
        "reason": group["reason"],
        "artifacts": artifact_entries,
        "status_checks": status_checks,
        "summary": group_summary(artifact_entries, status_checks),
    }


def summarize_index(groups: list[dict[str, Any]]) -> dict[str, Any]:
    artifact_count = sum(int(group["summary"]["artifact_count"]) for group in groups)
    artifact_failed_count = sum(int(group["summary"]["artifact_failed_count"]) for group in groups)
    status_check_count = sum(int(group["summary"]["status_check_count"]) for group in groups)
    status_check_failed_count = sum(int(group["summary"]["status_check_failed_count"]) for group in groups)
    return {
        "group_count": len(groups),
        "expectation_passed_count": sum(1 for group in groups if group["expectation_status"] == "passed"),
        "expectation_failed_count": sum(1 for group in groups if group["expectation_status"] == "failed"),
        "ready_group_count": sum(1 for group in groups if group["observed_group_status"] == "ready"),
        "manual_review_group_count": sum(1 for group in groups if group["observed_group_status"] == "manual_review"),
        "blocked_group_count": sum(1 for group in groups if group["observed_group_status"] == "blocked"),
        "artifact_count": artifact_count,
        "artifact_failed_count": artifact_failed_count,
        "status_check_count": status_check_count,
        "status_check_failed_count": status_check_failed_count,
    }


def overall_status(groups: list[dict[str, Any]]) -> str:
    if any(group["expectation_status"] == "failed" for group in groups):
        return "fixture_index_blocked"
    return "fixture_index_ready"


def build_fixture_index_report(
    manifest: dict[str, Any],
    root: Path,
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    groups = [
        fixture_group_entry(group, manifest, root)
        for group in manifest["fixture_groups"]
    ]
    return {
        "schema": FIXTURE_INDEX_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "index_id": manifest["index_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": overall_status(groups),
        "fixture_groups": groups,
        "summary": summarize_index(groups),
        "authority_boundary": [
            "Fixture indexes summarize public-safe peer-mesh fixture lanes only.",
            "Fixture indexes can treat deliberately blocked public baselines as expected fixture states.",
            "Fixture indexes do not execute validation slots, approve live work, select endpoints, collect evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, or execute commands.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    write_json(
        args.output,
        build_fixture_index_report(
            manifest,
            Path(args.artifact_root),
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer mesh fixture index.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
