#!/usr/bin/env python3
"""Public-safe file-drop copy dry run for peer gossip.

The dry run consumes a file-drop staging report plus synthetic copy outcomes.
It does not copy files, create inbox directories, read gossip bodies, open
sockets, discover peers, send gossip, use ADB, launch apps, or execute
commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_dispatch_plan
import peer_mesh_gossip
import peer_mesh_live_lab_readiness


STAGING_REPORT_SCHEMA = "quest-termux-lab.peer-file-drop-staging-report.v1"
COPY_OUTCOMES_SCHEMA = "quest-termux-lab.peer-file-drop-copy-outcomes.v1"
COPY_DRY_RUN_REPORT_SCHEMA = "quest-termux-lab.peer-file-drop-copy-dry-run-report.v1"
MESSAGE_SCHEMA = "quest-termux-lab.peer-gossip-envelope.v1"
COPY_RESULTS = {
    "simulated_copied",
    "simulated_duplicate",
    "simulated_missing_source",
    "simulated_write_blocked",
}
ACTION_STATUSES = COPY_RESULTS | {"missing_outcome", "not_planned"}
OVERALL_STATUSES = {
    "file_drop_copy_dry_run_ready",
    "manual_review",
    "file_drop_copy_dry_run_blocked",
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


def validate_text_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        result.append(item)
    return result


def validate_required_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} missing {key}")
    return value


def validate_optional_relative_path(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string or null")
    peer_mesh_dispatch_plan.validate_relative_path(value, label)
    return value


def validate_staging_entry(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("staging_entries entries must be objects")
    for key in [
        "delivery_id",
        "target_agent_id",
        "message_id",
        "dispatch_decision",
        "transport_mode",
        "method",
        "message_schema",
        "status",
        "reason",
    ]:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"staging entry missing {key}")
    if entry["message_schema"] != MESSAGE_SCHEMA:
        raise ValueError("unsupported staging entry message_schema")
    if entry["status"] not in {"planned", "skipped_non_file_drop", "skipped_not_ready"}:
        raise ValueError("unsupported staging entry status")
    target_inbox_dir = validate_optional_relative_path(entry.get("target_inbox_dir"), "target_inbox_dir")
    relative_path = validate_optional_relative_path(entry.get("relative_staging_path"), "relative_staging_path")
    filename = entry.get("staging_filename")
    if filename is not None:
        if not isinstance(filename, str) or not filename:
            raise ValueError("staging_filename must be a non-empty string or null")
        if Path(filename).name != filename or ".." in Path(filename).parts:
            raise ValueError("staging_filename must not contain path separators")
    if entry["status"] == "planned":
        if target_inbox_dir is None or relative_path is None or filename is None:
            raise ValueError("planned staging entry must include target inbox, filename, and relative path")
        relative = Path(relative_path)
        inbox = Path(target_inbox_dir)
        try:
            relative.relative_to(inbox)
        except ValueError as error:
            raise ValueError("relative_staging_path must stay under target_inbox_dir") from error
        if relative.name != filename:
            raise ValueError("relative_staging_path filename must match staging_filename")


def validate_staging_report(report: dict[str, Any]) -> None:
    if report.get("schema") != STAGING_REPORT_SCHEMA:
        raise ValueError("unsupported file-drop staging report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("file-drop staging report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "staging_plan_id",
        "experiment_scope",
        "expected_message_schema",
        "staging_entries",
        "summary",
        "overall_status",
        "authority_boundary",
    ]:
        if key not in report:
            raise ValueError(f"file-drop staging report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "staging_plan_id", "overall_status"]:
        validate_required_text(report, key, "file-drop staging report")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["expected_message_schema"] != MESSAGE_SCHEMA:
        raise ValueError("unsupported expected_message_schema")
    if not isinstance(report["staging_entries"], list):
        raise ValueError("staging_entries must be an array")
    for entry in report["staging_entries"]:
        validate_staging_entry(entry)
    validate_text_array(report["authority_boundary"], "authority_boundary")


def validate_outcome_entry(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("outcomes entries must be objects")
    for key in ["delivery_id", "target_agent_id", "message_id", "simulated_result", "reason"]:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"outcome entry missing {key}")
    if entry["simulated_result"] not in COPY_RESULTS:
        raise ValueError("unsupported file-drop copy result")


def validate_outcomes(payload: dict[str, Any]) -> None:
    if payload.get("schema") != COPY_OUTCOMES_SCHEMA:
        raise ValueError("unsupported file-drop copy outcomes schema")
    if peer_mesh_gossip.contains_forbidden_key(payload):
        raise ValueError("file-drop copy outcomes contain command-like or credential-like fields")
    for key in [
        "outcomes_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "outcomes",
        "authority_boundary",
    ]:
        if key not in payload:
            raise ValueError(f"file-drop copy outcomes missing {key}")
    for key in ["outcomes_id", "fleet_id", "source_agent_id", "observed_at"]:
        validate_required_text(payload, key, "file-drop copy outcomes")
    peer_mesh_gossip.parse_time(str(payload["observed_at"]))
    if payload["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if not isinstance(payload["outcomes"], list):
        raise ValueError("outcomes must be an array")
    seen: set[tuple[str, str]] = set()
    for entry in payload["outcomes"]:
        validate_outcome_entry(entry)
        key = (str(entry["delivery_id"]), str(entry["message_id"]))
        if key in seen:
            raise ValueError("duplicate outcome delivery/message pair")
        seen.add(key)
    validate_text_array(payload["authority_boundary"], "authority_boundary")


def outcomes_by_delivery(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    validate_outcomes(payload)
    return {
        (str(outcome["delivery_id"]), str(outcome["message_id"])): dict(outcome)
        for outcome in payload["outcomes"]
    }


def copy_action(entry: dict[str, Any], outcome: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "delivery_id": entry["delivery_id"],
        "target_agent_id": entry["target_agent_id"],
        "message_id": entry["message_id"],
        "staging_status": entry["status"],
        "dispatch_decision": entry["dispatch_decision"],
        "transport_mode": entry["transport_mode"],
        "method": entry["method"],
        "target_inbox_dir": entry["target_inbox_dir"],
        "staging_filename": entry["staging_filename"],
        "relative_staging_path": entry["relative_staging_path"],
    }
    if entry["status"] != "planned":
        return {
            **base,
            "simulated_result": "not_planned",
            "status": "not_planned",
            "reason": f"staging entry was not planned: {entry['reason']}",
        }
    if outcome is None:
        return {
            **base,
            "simulated_result": "simulated_missing_outcome",
            "status": "missing_outcome",
            "reason": "planned staging entry has no synthetic copy outcome",
        }
    if outcome["target_agent_id"] != entry["target_agent_id"]:
        raise ValueError("outcome target_agent_id mismatch")
    simulated = str(outcome["simulated_result"])
    return {
        **base,
        "simulated_result": simulated,
        "status": simulated,
        "reason": outcome["reason"],
    }


def summarize_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "action_count": len(actions),
        "planned_action_count": sum(1 for action in actions if action["staging_status"] == "planned"),
        "copied_count": sum(1 for action in actions if action["status"] == "simulated_copied"),
        "duplicate_count": sum(1 for action in actions if action["status"] == "simulated_duplicate"),
        "missing_source_count": sum(1 for action in actions if action["status"] == "simulated_missing_source"),
        "write_blocked_count": sum(1 for action in actions if action["status"] == "simulated_write_blocked"),
        "not_planned_count": sum(1 for action in actions if action["status"] == "not_planned"),
        "missing_outcome_count": sum(1 for action in actions if action["status"] == "missing_outcome"),
        "failed_count": sum(
            1
            for action in actions
            if action["status"] in {"simulated_missing_source", "simulated_write_blocked", "missing_outcome"}
        ),
    }


def overall_status(summary: dict[str, Any]) -> str:
    if int(summary["failed_count"]) > 0:
        return "file_drop_copy_dry_run_blocked"
    if int(summary["copied_count"]) + int(summary["duplicate_count"]) > 0:
        return "file_drop_copy_dry_run_ready"
    return "manual_review"


def build_copy_dry_run_report(
    staging_report: dict[str, Any],
    outcomes: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_staging_report(staging_report)
    validate_outcomes(outcomes)
    for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
        if outcomes[key] != staging_report[key]:
            raise ValueError(f"outcomes {key} mismatch")
    by_delivery = outcomes_by_delivery(outcomes)
    staged_keys = {
        (str(entry["delivery_id"]), str(entry["message_id"]))
        for entry in staging_report["staging_entries"]
    }
    unknown_keys = set(by_delivery) - staged_keys
    if unknown_keys:
        raise ValueError("outcomes reference delivery/message pairs not present in staging report")
    actions = [
        copy_action(entry, by_delivery.get((str(entry["delivery_id"]), str(entry["message_id"]))))
        for entry in staging_report["staging_entries"]
    ]
    summary = summarize_actions(actions)
    return {
        "schema": COPY_DRY_RUN_REPORT_SCHEMA,
        "fleet_id": staging_report["fleet_id"],
        "source_agent_id": staging_report["source_agent_id"],
        "observed_at": now_text or str(outcomes["observed_at"]),
        "staging_plan_id": staging_report["staging_plan_id"],
        "outcomes_id": outcomes["outcomes_id"],
        "experiment_scope": staging_report["experiment_scope"],
        "expected_message_schema": staging_report["expected_message_schema"],
        "actions": actions,
        "summary": summary,
        "overall_status": overall_status(summary),
        "authority_boundary": [
            "File-drop copy dry runs summarize synthetic copy outcomes for planned file-drop gossip staging entries only.",
            "File-drop copy dry runs do not copy files, create inbox directories, read gossip bodies, approve live work, select private endpoints, monitor peers, probe peers, open sockets, discover devices, send gossip, use ADB, launch apps, or execute commands.",
            "File-drop copy dry runs do not carry private endpoint values, raw network addresses, raw device identifiers, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    staging_report = load_json(Path(args.staging_report))
    outcomes = load_json(Path(args.outcomes))
    write_json(
        args.output,
        build_copy_dry_run_report(
            staging_report,
            outcomes,
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe file-drop copy dry-run report.")
    parser.add_argument("--staging-report", required=True)
    parser.add_argument("--outcomes", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
