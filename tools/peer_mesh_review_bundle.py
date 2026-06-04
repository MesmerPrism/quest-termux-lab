#!/usr/bin/env python3
"""Public-safe review bundle checker for peer mesh preparation.

The review bundle verifies that sanitized peer-mesh artifacts are present,
schema-tagged, and status-gated for review. It does not execute validation
slots, approve live work, select endpoints, replay evidence, monitor peers,
probe peers, open sockets, copy files, discover devices, use ADB, send gossip,
launch apps, or carry commands.
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


REVIEW_BUNDLE_MANIFEST_SCHEMA = "quest-termux-lab.peer-review-bundle-manifest.v1"
REVIEW_BUNDLE_REPORT_SCHEMA = "quest-termux-lab.peer-review-bundle-report.v1"
ENTRY_STATUSES = {"passed", "manual_review", "failed"}
OVERALL_STATUSES = {"review_ready", "manual_review", "review_blocked"}


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


def validate_relative_path(value: str, label: str) -> None:
    peer_mesh_evidence_intake.validate_artifact_path(value, label)
    suffix = Path(value).suffix.lower()
    if suffix not in {".json", ".md", ".py"}:
        raise ValueError(f"{label} must reference a json, md, or py file")


def validate_json_artifact_ref(item: Any) -> None:
    if not isinstance(item, dict):
        raise ValueError("json_artifacts entries must be objects")
    for key in ["artifact_id", "path", "expected_schema"]:
        if not isinstance(item.get(key), str) or not item[key]:
            raise ValueError(f"json_artifacts entry missing {key}")
    validate_relative_path(str(item["path"]), "json_artifacts.path")
    if Path(str(item["path"])).suffix.lower() != ".json":
        raise ValueError("json_artifacts.path must reference a json file")


def validate_file_artifact_ref(item: Any) -> None:
    if not isinstance(item, dict):
        raise ValueError("file_artifacts entries must be objects")
    for key in ["artifact_id", "path", "artifact_role"]:
        if not isinstance(item.get(key), str) or not item[key]:
            raise ValueError(f"file_artifacts entry missing {key}")
    validate_relative_path(str(item["path"]), "file_artifacts.path")
    if item["artifact_role"] not in {"tool", "test", "doc", "schema", "example"}:
        raise ValueError("unsupported file artifact role")


def validate_status_check_ref(item: Any, artifact_ids: set[str]) -> None:
    if not isinstance(item, dict):
        raise ValueError("status_checks entries must be objects")
    for key in ["artifact_id", "status_field", "accepted_values", "manual_review_values", "blocked_values"]:
        if key not in item:
            raise ValueError(f"status_checks entry missing {key}")
    if not isinstance(item["artifact_id"], str) or item["artifact_id"] not in artifact_ids:
        raise ValueError("status_checks artifact_id must reference a json artifact")
    if not isinstance(item["status_field"], str) or not item["status_field"]:
        raise ValueError("status_checks status_field must be text")
    for key in ["accepted_values", "manual_review_values", "blocked_values"]:
        values = item[key]
        if not isinstance(values, list):
            raise ValueError(f"status_checks {key} must be an array")
        for value in values:
            if not isinstance(value, str) or not value:
                raise ValueError(f"status_checks {key} entries must be text")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != REVIEW_BUNDLE_MANIFEST_SCHEMA:
        raise ValueError("unsupported review bundle manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("review bundle manifest contains command-like or credential-like fields")
    for key in [
        "bundle_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "json_artifacts",
        "file_artifacts",
        "status_checks",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"review bundle manifest missing {key}")
    for key in ["bundle_id", "fleet_id", "source_agent_id", "observed_at"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"review bundle manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    for key in ["json_artifacts", "file_artifacts", "status_checks", "authority_boundary"]:
        if not isinstance(manifest[key], list):
            raise ValueError(f"review bundle manifest {key} must be an array")
    for item in manifest["json_artifacts"]:
        validate_json_artifact_ref(item)
    for item in manifest["file_artifacts"]:
        validate_file_artifact_ref(item)
    json_ids = [str(item["artifact_id"]) for item in manifest["json_artifacts"]]
    file_ids = [str(item["artifact_id"]) for item in manifest["file_artifacts"]]
    if len(json_ids) != len(set(json_ids)):
        raise ValueError("json_artifacts artifact_id entries must be unique")
    if len(file_ids) != len(set(file_ids)):
        raise ValueError("file_artifacts artifact_id entries must be unique")
    for item in manifest["status_checks"]:
        validate_status_check_ref(item, set(json_ids))
    if not manifest["authority_boundary"]:
        raise ValueError("review bundle manifest authority_boundary must not be empty")
    for item in manifest["authority_boundary"]:
        if not isinstance(item, str) or not item:
            raise ValueError("review bundle manifest authority boundary entries must be text")


def identity_check(payload: dict[str, Any], manifest: dict[str, Any]) -> None:
    if payload.get("fleet_id") and payload.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError("fleet_id mismatch")
    if payload.get("source_agent_id") and payload.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError("source_agent_id mismatch")
    if payload.get("experiment_scope") and payload.get("experiment_scope") != manifest["experiment_scope"]:
        raise ValueError("experiment_scope mismatch")


def json_artifact_entry(item: dict[str, Any], manifest: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
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
                "reason": "json artifact missing",
            },
            None,
        )
    try:
        payload = load_json(path)
        if peer_mesh_gossip.contains_forbidden_key(payload):
            raise ValueError("json artifact contains command-like or credential-like fields")
        observed_schema = str(payload.get("schema", ""))
        if observed_schema != expected_schema:
            raise ValueError("schema mismatch")
        identity_check(payload, manifest)
        status = "passed"
        reason = "json artifact exists, matches schema, and identity is compatible"
    except (OSError, json.JSONDecodeError, ValueError) as error:
        payload = None
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
        payload,
    )


def file_artifact_entry(item: dict[str, Any], root: Path) -> dict[str, Any]:
    path_text = str(item["path"])
    path = root / path_text
    if not path.is_file():
        status = "failed"
        reason = "file artifact missing"
    elif path.suffix.lower() not in {".json", ".md", ".py"}:
        status = "failed"
        reason = "file artifact has unsupported suffix"
    else:
        status = "passed"
        reason = "file artifact exists"
    return {
        "artifact_id": item["artifact_id"],
        "artifact_role": item["artifact_role"],
        "path": path_text,
        "status": status,
        "reason": reason,
    }


def status_check_entry(item: dict[str, Any], payloads_by_id: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    artifact_id = str(item["artifact_id"])
    payload = payloads_by_id.get(artifact_id)
    if payload is None:
        return {
            "artifact_id": artifact_id,
            "status_field": str(item["status_field"]),
            "observed_value": "",
            "status": "failed",
            "reason": "status artifact missing or invalid",
        }
    value = payload
    for part in str(item["status_field"]).split("."):
        if not isinstance(value, dict) or part not in value:
            return {
                "artifact_id": artifact_id,
                "status_field": str(item["status_field"]),
                "observed_value": "",
                "status": "failed",
                "reason": "status field missing",
            }
        value = value[part]
    observed = str(value)
    if observed in set(item["accepted_values"]):
        status = "passed"
        reason = "status value is accepted by review policy"
    elif observed in set(item["manual_review_values"]):
        status = "manual_review"
        reason = "status value requires manual review"
    elif observed in set(item["blocked_values"]):
        status = "failed"
        reason = "status value blocks review"
    else:
        status = "failed"
        reason = "status value is not declared in review policy"
    return {
        "artifact_id": artifact_id,
        "status_field": str(item["status_field"]),
        "observed_value": observed,
        "status": status,
        "reason": reason,
    }


def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "entry_count": len(entries),
        "passed_count": sum(1 for entry in entries if entry["status"] == "passed"),
        "manual_review_count": sum(1 for entry in entries if entry["status"] == "manual_review"),
        "failed_count": sum(1 for entry in entries if entry["status"] == "failed"),
    }


def overall_status(entries: list[dict[str, Any]]) -> str:
    if any(entry["status"] == "failed" for entry in entries):
        return "review_blocked"
    if any(entry["status"] == "manual_review" for entry in entries):
        return "manual_review"
    return "review_ready"


def build_review_bundle_report(
    manifest: dict[str, Any],
    root: Path,
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    json_entries = []
    payloads_by_id: dict[str, dict[str, Any] | None] = {}
    for item in manifest["json_artifacts"]:
        entry, payload = json_artifact_entry(item, manifest, root)
        json_entries.append(entry)
        payloads_by_id[str(item["artifact_id"])] = payload
    file_entries = [
        file_artifact_entry(item, root)
        for item in manifest["file_artifacts"]
    ]
    status_entries = [
        status_check_entry(item, payloads_by_id)
        for item in manifest["status_checks"]
    ]
    all_entries = json_entries + file_entries + status_entries
    return {
        "schema": REVIEW_BUNDLE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "bundle_id": manifest["bundle_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": overall_status(all_entries),
        "json_artifacts": json_entries,
        "file_artifacts": file_entries,
        "status_checks": status_entries,
        "summary": summarize(all_entries),
        "authority_boundary": [
            "Review bundle reports inspect sanitized peer-mesh artifacts only.",
            "Review bundle reports do not execute validation slots, approve live work, select endpoints, replay evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Review bundle reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    write_json(args.output, build_review_bundle_report(manifest, Path(args.artifact_root), now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer mesh review bundle report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
