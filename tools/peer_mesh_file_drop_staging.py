#!/usr/bin/env python3
"""Public-safe file-drop staging planner for peer gossip.

The planner turns ready file-drop dispatches into deterministic relative inbox
filenames. It does not copy files, read gossip bodies, open sockets, discover
peers, use ADB, launch apps, or execute commands.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import peer_mesh_dispatch_plan
import peer_mesh_evidence_intake
import peer_mesh_gossip
import peer_mesh_live_lab_readiness


FILE_DROP_STAGING_MANIFEST_SCHEMA = "quest-termux-lab.peer-file-drop-staging-manifest.v1"
FILE_DROP_STAGING_REPORT_SCHEMA = "quest-termux-lab.peer-file-drop-staging-report.v1"
MESSAGE_SCHEMA = "quest-termux-lab.peer-gossip-envelope.v1"
ENTRY_STATUSES = {
    "planned",
    "skipped_non_file_drop",
    "skipped_not_ready",
}
OVERALL_STATUSES = {
    "file_drop_staging_ready",
    "manual_review",
    "file_drop_staging_blocked",
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


def validate_json_artifact_path(value: Any, label: str) -> str:
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


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != FILE_DROP_STAGING_MANIFEST_SCHEMA:
        raise ValueError("unsupported file-drop staging manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("file-drop staging manifest contains command-like or credential-like fields")
    for key in [
        "staging_plan_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "route_config_path",
        "delivery_state_path",
        "expected_message_schema",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"file-drop staging manifest missing {key}")
    for key in ["staging_plan_id", "fleet_id", "source_agent_id", "observed_at"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"file-drop staging manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_json_artifact_path(manifest["route_config_path"], "route_config_path")
    validate_json_artifact_path(manifest["delivery_state_path"], "delivery_state_path")
    if manifest["expected_message_schema"] != MESSAGE_SCHEMA:
        raise ValueError("unsupported expected_message_schema")
    validate_text_array(manifest["authority_boundary"], "authority_boundary")


def safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    if not cleaned:
        cleaned = "entry"
    return cleaned[:96]


def staging_filename(source_agent_id: str, target_agent_id: str, message_id: str) -> str:
    filename = (
        f"{safe_segment(source_agent_id)}__to__"
        f"{safe_segment(target_agent_id)}__"
        f"{safe_segment(message_id)}.peer-gossip-envelope.json"
    )
    if Path(filename).name != filename or ".." in Path(filename).parts:
        raise ValueError("computed staging filename is unsafe")
    return filename


def relative_staging_path(target_inbox_dir: str, filename: str) -> str:
    peer_mesh_dispatch_plan.validate_relative_path(target_inbox_dir, "target_inbox_dir")
    if Path(filename).name != filename:
        raise ValueError("staging filename must not contain path separators")
    path = Path(target_inbox_dir) / filename
    peer_mesh_dispatch_plan.validate_relative_path(str(path), "relative_staging_path")
    try:
        path.relative_to(Path(target_inbox_dir))
    except ValueError as error:
        raise ValueError("relative staging path must stay under target inbox dir") from error
    return path.as_posix()


def staging_entry(dispatch: dict[str, Any], source_agent_id: str) -> dict[str, Any]:
    base = {
        "delivery_id": dispatch["delivery_id"],
        "target_agent_id": dispatch["target_agent_id"],
        "message_id": dispatch["message_id"],
        "dispatch_decision": dispatch["decision"],
        "transport_mode": dispatch["transport_mode"],
        "method": dispatch["method"],
        "target_inbox_dir": None,
        "staging_filename": None,
        "relative_staging_path": None,
        "message_schema": dispatch["message_schema"],
    }
    if dispatch["decision"] != "ready":
        return {
            **base,
            "status": "skipped_not_ready",
            "reason": dispatch.get("reason") or "dispatch is not ready",
        }
    if dispatch["transport_mode"] != "file_drop_simulator" or dispatch["method"] != "copy_envelope":
        return {
            **base,
            "status": "skipped_non_file_drop",
            "reason": "ready dispatch does not use file-drop transport",
        }

    target_inbox_dir = str(dispatch["route_target"])
    filename = staging_filename(source_agent_id, str(dispatch["target_agent_id"]), str(dispatch["message_id"]))
    return {
        **base,
        "target_inbox_dir": target_inbox_dir,
        "staging_filename": filename,
        "relative_staging_path": relative_staging_path(target_inbox_dir, filename),
        "status": "planned",
        "reason": "ready file-drop dispatch has a deterministic relative staging path",
    }


def summarize(entries: list[dict[str, Any]], dispatch_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "dispatch_count": int(dispatch_summary["dispatch_count"]),
        "ready_dispatch_count": int(dispatch_summary["ready_count"]),
        "entry_count": len(entries),
        "planned_count": sum(1 for entry in entries if entry["status"] == "planned"),
        "skipped_non_file_drop_count": sum(1 for entry in entries if entry["status"] == "skipped_non_file_drop"),
        "skipped_not_ready_count": sum(1 for entry in entries if entry["status"] == "skipped_not_ready"),
    }


def overall_status(summary: dict[str, Any]) -> str:
    if int(summary["planned_count"]) > 0:
        return "file_drop_staging_ready"
    return "manual_review"


def build_file_drop_staging_report(
    manifest: dict[str, Any],
    root: Path,
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    route_config = load_json(root / str(manifest["route_config_path"]))
    delivery_state = load_json(root / str(manifest["delivery_state_path"]))
    if route_config.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError("route config fleet_id mismatch")
    if route_config.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError("route config source_agent_id mismatch")
    if delivery_state.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError("delivery state fleet_id mismatch")
    if delivery_state.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError("delivery state source_agent_id mismatch")

    observed_at = now_text or str(manifest["observed_at"])
    plan = peer_mesh_dispatch_plan.build_dispatch_plan(delivery_state, route_config, now_text=observed_at)
    entries = [
        staging_entry(dispatch, str(manifest["source_agent_id"]))
        for dispatch in plan["dispatches"]
    ]
    summary = summarize(entries, plan["summary"])
    return {
        "schema": FILE_DROP_STAGING_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": observed_at,
        "staging_plan_id": manifest["staging_plan_id"],
        "experiment_scope": manifest["experiment_scope"],
        "route_config_path": manifest["route_config_path"],
        "delivery_state_path": manifest["delivery_state_path"],
        "expected_message_schema": manifest["expected_message_schema"],
        "dispatch_summary": plan["summary"],
        "staging_entries": entries,
        "summary": summary,
        "overall_status": overall_status(summary),
        "authority_boundary": [
            "File-drop staging reports plan relative inbox filenames for ready file-drop gossip dispatches only.",
            "File-drop staging reports do not copy files, read gossip bodies, approve live work, select private endpoints, monitor peers, probe peers, open sockets, discover devices, send gossip, use ADB, launch apps, or execute commands.",
            "File-drop staging reports do not carry private endpoint values, raw network addresses, raw device identifiers, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    write_json(
        args.output,
        build_file_drop_staging_report(
            manifest,
            Path(args.artifact_root),
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer file-drop staging report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
