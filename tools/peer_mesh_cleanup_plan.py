#!/usr/bin/env python3
"""Public-safe cleanup planning for peer mesh preparation.

The cleanup plan declares the cleanup categories a future private peer run
must account for before any endpoint selection or live transport happens. It
does not execute cleanup, stop processes, inspect devices, open sockets, copy
files, discover peers, send gossip, use ADB, launch apps, or carry commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_gossip
import peer_mesh_live_lab_readiness


CLEANUP_PLAN_MANIFEST_SCHEMA = "quest-termux-lab.peer-cleanup-plan-manifest.v1"
CLEANUP_PLAN_REPORT_SCHEMA = "quest-termux-lab.peer-cleanup-plan-report.v1"
CLEANUP_KINDS = {
    "operator_review",
    "confirm_peer_transport_stopped",
    "clear_ephemeral_inbox",
    "clear_ephemeral_outbox",
    "preserve_sanitized_summary",
    "record_post_run_route_health",
    "record_route_history",
    "record_cleanup_record",
}
REQUIRED_CLEANUP_KINDS = {
    "operator_review",
    "confirm_peer_transport_stopped",
    "clear_ephemeral_inbox",
    "clear_ephemeral_outbox",
    "record_cleanup_record",
}
TIMING_VALUES = {"pre_run", "post_run", "post_evidence", "final_review"}
EVIDENCE_KINDS = {
    "none",
    "cleanup_record",
    "route_health_report",
    "route_history_report",
    "evidence_intake_report",
    "scorecard_report",
}
STEP_STATUSES = {"planned", "missing"}
OVERALL_STATUSES = {"cleanup_plan_ready", "cleanup_plan_blocked"}


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


def validate_cleanup_step(step: Any) -> None:
    if not isinstance(step, dict):
        raise ValueError("cleanup_steps entries must be objects")
    for key in ["step_id", "cleanup_kind", "timing", "required", "expected_evidence_kind", "reason"]:
        if key not in step:
            raise ValueError(f"cleanup step missing {key}")
    for key in ["step_id", "cleanup_kind", "timing", "expected_evidence_kind", "reason"]:
        if not isinstance(step[key], str) or not step[key]:
            raise ValueError(f"cleanup step missing {key}")
    if step["cleanup_kind"] not in CLEANUP_KINDS:
        raise ValueError("unsupported cleanup_kind")
    if step["timing"] not in TIMING_VALUES:
        raise ValueError("unsupported cleanup timing")
    if not isinstance(step["required"], bool):
        raise ValueError("cleanup step required must be boolean")
    if step["expected_evidence_kind"] not in EVIDENCE_KINDS:
        raise ValueError("unsupported expected_evidence_kind")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != CLEANUP_PLAN_MANIFEST_SCHEMA:
        raise ValueError("unsupported cleanup plan manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("cleanup plan manifest contains command-like or credential-like fields")
    for key in [
        "cleanup_plan_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "cleanup_steps",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"cleanup plan manifest missing {key}")
    for key in ["cleanup_plan_id", "fleet_id", "source_agent_id", "observed_at"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"cleanup plan manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    steps = manifest["cleanup_steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("cleanup_steps must be a non-empty array")
    step_ids = []
    for step in steps:
        validate_cleanup_step(step)
        step_ids.append(str(step["step_id"]))
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("cleanup step ids must be unique")
    validate_text_array(manifest["authority_boundary"], "authority_boundary")


def step_entry(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_id": step["step_id"],
        "cleanup_kind": step["cleanup_kind"],
        "timing": step["timing"],
        "required": step["required"],
        "expected_evidence_kind": step["expected_evidence_kind"],
        "status": "planned",
        "reason": step["reason"],
    }


def missing_required_entries(observed_kinds: set[str]) -> list[dict[str, Any]]:
    entries = []
    for kind in sorted(REQUIRED_CLEANUP_KINDS - observed_kinds):
        entries.append(
            {
                "step_id": f"missing-{kind}",
                "cleanup_kind": kind,
                "timing": "final_review",
                "required": True,
                "expected_evidence_kind": "cleanup_record",
                "status": "missing",
                "reason": "required cleanup category is not declared",
            }
        )
    return entries


def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    observed_required = {
        entry["cleanup_kind"]
        for entry in entries
        if entry["status"] == "planned" and entry["cleanup_kind"] in REQUIRED_CLEANUP_KINDS
    }
    evidence_kinds = {
        entry["expected_evidence_kind"]
        for entry in entries
        if entry["expected_evidence_kind"] != "none" and entry["status"] == "planned"
    }
    return {
        "step_count": len(entries),
        "planned_step_count": sum(1 for entry in entries if entry["status"] == "planned"),
        "missing_step_count": sum(1 for entry in entries if entry["status"] == "missing"),
        "required_cleanup_kind_count": len(REQUIRED_CLEANUP_KINDS),
        "observed_required_cleanup_kind_count": len(observed_required),
        "missing_required_cleanup_kind_count": len(REQUIRED_CLEANUP_KINDS - observed_required),
        "evidence_kind_count": len(evidence_kinds),
    }


def overall_status(entries: list[dict[str, Any]]) -> str:
    if any(entry["status"] == "missing" for entry in entries):
        return "cleanup_plan_blocked"
    return "cleanup_plan_ready"


def build_cleanup_plan_report(
    manifest: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    declared = [step_entry(step) for step in manifest["cleanup_steps"]]
    observed_required = {
        entry["cleanup_kind"]
        for entry in declared
        if entry["required"] and entry["cleanup_kind"] in REQUIRED_CLEANUP_KINDS
    }
    entries = declared + missing_required_entries(observed_required)
    return {
        "schema": CLEANUP_PLAN_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "cleanup_plan_id": manifest["cleanup_plan_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": overall_status(entries),
        "required_cleanup_kinds": sorted(REQUIRED_CLEANUP_KINDS),
        "cleanup_steps": entries,
        "summary": summarize(entries),
        "authority_boundary": [
            "Cleanup plan reports declare public-safe peer-mesh cleanup requirements only.",
            "Cleanup plan reports do not execute cleanup, approve live work, select endpoints, inspect devices, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, launch apps, or execute commands.",
            "Cleanup plan reports do not carry private endpoint values, raw network addresses, raw device identifiers, gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    write_json(args.output, build_cleanup_plan_report(manifest, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer mesh cleanup plan report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
