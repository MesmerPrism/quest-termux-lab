#!/usr/bin/env python3
"""Public-safe file-drop inbox intake dry run for peer gossip.

The intake dry run consumes a file-drop copy dry-run report plus a declared
synthetic inbox manifest. It reads only explicitly referenced public fixture
envelopes under the chosen artifact root. It does not scan inbox directories,
copy files, open sockets, discover peers, send gossip, use ADB, launch apps, or
execute commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_dispatch_plan
import peer_mesh_evidence_intake
import peer_mesh_file_drop_copy_dry_run
import peer_mesh_gossip
import peer_mesh_live_lab_readiness


COPY_DRY_RUN_REPORT_SCHEMA = "quest-termux-lab.peer-file-drop-copy-dry-run-report.v1"
INBOX_INTAKE_MANIFEST_SCHEMA = "quest-termux-lab.peer-file-drop-inbox-intake-manifest.v1"
INBOX_INTAKE_REPORT_SCHEMA = "quest-termux-lab.peer-file-drop-inbox-intake-report.v1"
MESSAGE_SCHEMA = "quest-termux-lab.peer-gossip-envelope.v1"
SIMULATED_PRESENCE_VALUES = {
    "simulated_present",
    "simulated_duplicate_file",
    "simulated_missing_file",
    "simulated_unreadable_file",
    "simulated_invalid_envelope",
}
READY_COPY_STATUSES = {"simulated_copied", "simulated_duplicate"}
INTAKE_ENTRY_STATUSES = {
    "accepted",
    "duplicate_ignored",
    "missing_file",
    "unreadable_file",
    "invalid_envelope",
    "not_copied",
}
OVERALL_STATUSES = {
    "file_drop_inbox_intake_ready",
    "manual_review",
    "file_drop_inbox_intake_blocked",
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


def validate_json_artifact_path(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string or null")
    peer_mesh_evidence_intake.validate_artifact_path(value, label)
    if Path(value).suffix.lower() != ".json":
        raise ValueError(f"{label} must reference a json file")
    return value


def validate_optional_relative_path(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string or null")
    peer_mesh_dispatch_plan.validate_relative_path(value, label)
    return value


def validate_copy_action(action: Any) -> None:
    if not isinstance(action, dict):
        raise ValueError("copy report actions entries must be objects")
    for key in [
        "delivery_id",
        "target_agent_id",
        "message_id",
        "staging_status",
        "dispatch_decision",
        "transport_mode",
        "method",
        "status",
        "reason",
    ]:
        if not isinstance(action.get(key), str) or not action[key]:
            raise ValueError(f"copy report action missing {key}")
    if action["status"] not in peer_mesh_file_drop_copy_dry_run.ACTION_STATUSES:
        raise ValueError("unsupported copy report action status")
    target_inbox_dir = validate_optional_relative_path(action.get("target_inbox_dir"), "target_inbox_dir")
    relative_path = validate_optional_relative_path(action.get("relative_staging_path"), "relative_staging_path")
    filename = action.get("staging_filename")
    if filename is not None:
        if not isinstance(filename, str) or not filename:
            raise ValueError("staging_filename must be a non-empty string or null")
        if Path(filename).name != filename or ".." in Path(filename).parts:
            raise ValueError("staging_filename must not contain path separators")
    if action["status"] in READY_COPY_STATUSES:
        if target_inbox_dir is None or relative_path is None or filename is None:
            raise ValueError("ready copy action must include target inbox, filename, and relative path")
        try:
            Path(relative_path).relative_to(Path(target_inbox_dir))
        except ValueError as error:
            raise ValueError("relative_staging_path must stay under target_inbox_dir") from error
        if Path(relative_path).name != filename:
            raise ValueError("relative_staging_path filename must match staging_filename")


def validate_copy_report(report: dict[str, Any]) -> None:
    if report.get("schema") != COPY_DRY_RUN_REPORT_SCHEMA:
        raise ValueError("unsupported file-drop copy dry-run report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("file-drop copy dry-run report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "staging_plan_id",
        "outcomes_id",
        "experiment_scope",
        "expected_message_schema",
        "actions",
        "summary",
        "overall_status",
        "authority_boundary",
    ]:
        if key not in report:
            raise ValueError(f"file-drop copy dry-run report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "staging_plan_id", "outcomes_id", "overall_status"]:
        validate_required_text(report, key, "file-drop copy dry-run report")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if report["expected_message_schema"] != MESSAGE_SCHEMA:
        raise ValueError("unsupported expected_message_schema")
    if not isinstance(report["actions"], list):
        raise ValueError("copy report actions must be an array")
    seen: set[tuple[str, str]] = set()
    for action in report["actions"]:
        validate_copy_action(action)
        key = (str(action["delivery_id"]), str(action["message_id"]))
        if key in seen:
            raise ValueError("duplicate copy action delivery/message pair")
        seen.add(key)
    validate_text_array(report["authority_boundary"], "authority_boundary")


def validate_manifest_entry(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("inbox_entries entries must be objects")
    for key in ["delivery_id", "target_agent_id", "message_id", "relative_staging_path", "simulated_presence", "reason"]:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"inbox entry missing {key}")
    peer_mesh_dispatch_plan.validate_relative_path(str(entry["relative_staging_path"]), "relative_staging_path")
    if entry["simulated_presence"] not in SIMULATED_PRESENCE_VALUES:
        raise ValueError("unsupported simulated_presence")
    envelope_path = validate_json_artifact_path(entry.get("envelope_path"), "envelope_path")
    if entry["simulated_presence"] in {
        "simulated_present",
        "simulated_duplicate_file",
        "simulated_invalid_envelope",
    } and envelope_path is None:
        raise ValueError("present or invalid inbox entries must declare envelope_path")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != INBOX_INTAKE_MANIFEST_SCHEMA:
        raise ValueError("unsupported file-drop inbox intake manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("file-drop inbox intake manifest contains command-like or credential-like fields")
    for key in [
        "intake_id",
        "fleet_id",
        "source_agent_id",
        "receiver_agent_id",
        "observed_at",
        "experiment_scope",
        "expected_message_schema",
        "inbox_entries",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"file-drop inbox intake manifest missing {key}")
    for key in ["intake_id", "fleet_id", "source_agent_id", "receiver_agent_id", "observed_at"]:
        validate_required_text(manifest, key, "file-drop inbox intake manifest")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    if manifest["expected_message_schema"] != MESSAGE_SCHEMA:
        raise ValueError("unsupported expected_message_schema")
    if not isinstance(manifest["inbox_entries"], list):
        raise ValueError("inbox_entries must be an array")
    seen: set[tuple[str, str]] = set()
    for entry in manifest["inbox_entries"]:
        validate_manifest_entry(entry)
        key = (str(entry["delivery_id"]), str(entry["message_id"]))
        if key in seen:
            raise ValueError("duplicate inbox entry delivery/message pair")
        seen.add(key)
        if entry["target_agent_id"] != manifest["receiver_agent_id"]:
            raise ValueError("inbox entry target_agent_id must match receiver_agent_id")
    validate_text_array(manifest["authority_boundary"], "authority_boundary")


def copy_actions_by_delivery(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    validate_copy_report(report)
    return {
        (str(action["delivery_id"]), str(action["message_id"])): dict(action)
        for action in report["actions"]
    }


def invalid_entry(
    entry: dict[str, Any],
    copy_action: dict[str, Any] | None,
    status: str,
    reason: str,
    envelope_path: str | None = None,
) -> dict[str, Any]:
    return {
        "delivery_id": entry["delivery_id"],
        "target_agent_id": entry["target_agent_id"],
        "message_id": entry["message_id"],
        "relative_staging_path": entry["relative_staging_path"],
        "copy_status": copy_action["status"] if copy_action else "missing_copy_action",
        "simulated_presence": entry["simulated_presence"],
        "envelope_path": envelope_path if envelope_path is not None else entry.get("envelope_path"),
        "observed_message_schema": "",
        "observed_sender_agent_id": "",
        "observed_observation_count": 0,
        "status": status,
        "reason": reason,
    }


def validate_envelope_for_entry(
    envelope: dict[str, Any],
    entry: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, str]:
    try:
        peer_mesh_gossip.validate_envelope(envelope)
    except ValueError as error:
        return False, str(error)
    if envelope.get("fleet_id") != manifest["fleet_id"]:
        return False, "envelope fleet_id mismatch"
    if envelope.get("message_id") != entry["message_id"]:
        return False, "envelope message_id mismatch"
    if envelope.get("sender_agent_id") != manifest["source_agent_id"]:
        return False, "envelope sender_agent_id mismatch"
    return True, "synthetic envelope validated for declared inbox entry"


def intake_entry(
    entry: dict[str, Any],
    copy_action: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    if copy_action["target_agent_id"] != entry["target_agent_id"]:
        raise ValueError("copy action target_agent_id mismatch")
    if copy_action["relative_staging_path"] != entry["relative_staging_path"]:
        raise ValueError("copy action relative_staging_path mismatch")
    if copy_action["status"] not in READY_COPY_STATUSES:
        return invalid_entry(
            entry,
            copy_action,
            "not_copied",
            f"copy dry-run action was not ready for intake: {copy_action['status']}",
        )
    simulated = str(entry["simulated_presence"])
    if simulated == "simulated_missing_file":
        return invalid_entry(entry, copy_action, "missing_file", entry["reason"])
    if simulated == "simulated_unreadable_file":
        return invalid_entry(entry, copy_action, "unreadable_file", entry["reason"])

    envelope_path = str(entry["envelope_path"])
    path = root / envelope_path
    try:
        envelope = load_json(path)
        if peer_mesh_gossip.contains_forbidden_key(envelope):
            raise ValueError("declared inbox envelope contains command-like or credential-like fields")
        valid, reason = validate_envelope_for_entry(envelope, entry, manifest)
    except OSError as error:
        return invalid_entry(entry, copy_action, "missing_file", str(error), envelope_path=envelope_path)
    except (json.JSONDecodeError, ValueError) as error:
        envelope = {}
        valid = False
        reason = str(error)
    if simulated == "simulated_invalid_envelope":
        return invalid_entry(entry, copy_action, "invalid_envelope", entry["reason"], envelope_path=envelope_path)
    if not valid:
        return invalid_entry(entry, copy_action, "invalid_envelope", reason, envelope_path=envelope_path)

    status = "duplicate_ignored" if simulated == "simulated_duplicate_file" or copy_action["status"] == "simulated_duplicate" else "accepted"
    return {
        "delivery_id": entry["delivery_id"],
        "target_agent_id": entry["target_agent_id"],
        "message_id": entry["message_id"],
        "relative_staging_path": entry["relative_staging_path"],
        "copy_status": copy_action["status"],
        "simulated_presence": simulated,
        "envelope_path": envelope_path,
        "observed_message_schema": str(envelope.get("schema", "")),
        "observed_sender_agent_id": str(envelope.get("sender_agent_id", "")),
        "observed_observation_count": len(envelope.get("observations", [])) if isinstance(envelope.get("observations"), list) else 0,
        "status": status,
        "reason": reason,
    }


def summarize_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    failed_statuses = {"missing_file", "unreadable_file", "invalid_envelope", "not_copied"}
    return {
        "entry_count": len(entries),
        "accepted_count": sum(1 for entry in entries if entry["status"] == "accepted"),
        "duplicate_count": sum(1 for entry in entries if entry["status"] == "duplicate_ignored"),
        "missing_file_count": sum(1 for entry in entries if entry["status"] == "missing_file"),
        "unreadable_file_count": sum(1 for entry in entries if entry["status"] == "unreadable_file"),
        "invalid_envelope_count": sum(1 for entry in entries if entry["status"] == "invalid_envelope"),
        "not_copied_count": sum(1 for entry in entries if entry["status"] == "not_copied"),
        "failed_count": sum(1 for entry in entries if entry["status"] in failed_statuses),
    }


def overall_status(summary: dict[str, Any]) -> str:
    if int(summary["failed_count"]) > 0:
        return "file_drop_inbox_intake_blocked"
    if int(summary["accepted_count"]) + int(summary["duplicate_count"]) > 0:
        return "file_drop_inbox_intake_ready"
    return "manual_review"


def build_inbox_intake_report(
    copy_report: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_copy_report(copy_report)
    validate_manifest(manifest)
    for key in ["fleet_id", "source_agent_id", "experiment_scope"]:
        if manifest[key] != copy_report[key]:
            raise ValueError(f"manifest {key} mismatch")
    if manifest["expected_message_schema"] != copy_report["expected_message_schema"]:
        raise ValueError("manifest expected_message_schema mismatch")
    actions = copy_actions_by_delivery(copy_report)
    manifest_keys = {
        (str(entry["delivery_id"]), str(entry["message_id"]))
        for entry in manifest["inbox_entries"]
    }
    unknown_keys = manifest_keys - set(actions)
    if unknown_keys:
        raise ValueError("inbox manifest references delivery/message pairs not present in copy report")
    entries = [
        intake_entry(
            entry,
            actions[(str(entry["delivery_id"]), str(entry["message_id"]))],
            manifest,
            root,
        )
        for entry in manifest["inbox_entries"]
    ]
    summary = summarize_entries(entries)
    return {
        "schema": INBOX_INTAKE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "receiver_agent_id": manifest["receiver_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "intake_id": manifest["intake_id"],
        "staging_plan_id": copy_report["staging_plan_id"],
        "outcomes_id": copy_report["outcomes_id"],
        "experiment_scope": manifest["experiment_scope"],
        "expected_message_schema": manifest["expected_message_schema"],
        "intake_entries": entries,
        "summary": summary,
        "overall_status": overall_status(summary),
        "authority_boundary": [
            "File-drop inbox intake reports classify explicitly declared synthetic inbox entries only.",
            "File-drop inbox intake reports may read declared public fixture envelopes under the artifact root, but they do not scan inbox directories, copy files, approve live work, select private endpoints, monitor peers, probe peers, open sockets, discover devices, send gossip, use ADB, launch apps, or execute commands.",
            "File-drop inbox intake reports do not carry private endpoint values, raw network addresses, raw device identifiers, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    copy_report = load_json(Path(args.copy_report))
    manifest = load_json(Path(args.manifest))
    write_json(
        args.output,
        build_inbox_intake_report(
            copy_report,
            manifest,
            Path(args.artifact_root),
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe file-drop inbox intake report.")
    parser.add_argument("--copy-report", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
