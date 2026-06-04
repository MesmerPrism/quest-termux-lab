#!/usr/bin/env python3
"""Public-safe peer live-run rehearsal report.

The rehearsal report packages synthetic preflight status and private evidence
requirements before any live peer experiment. It does not approve live work,
select endpoints, open sockets, copy files, discover peers, use ADB, send
gossip, launch apps, or carry commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_gossip
import peer_mesh_lab_bundle
import peer_mesh_live_lab_readiness
import peer_mesh_trust_gate


REHEARSAL_MANIFEST_SCHEMA = "quest-termux-lab.peer-rehearsal-manifest.v1"
REHEARSAL_REPORT_SCHEMA = "quest-termux-lab.peer-rehearsal-report.v1"
REHEARSAL_STATUSES = {"rehearsal_ready", "manual_review", "blocked"}
CHECK_STATUSES = {"passed", "failed", "manual_review"}
PHASE_STATUSES = {"ready", "manual_review", "blocked", "private_only"}
EVIDENCE_KINDS = {
    "preflight_bundle_report",
    "trust_report",
    "private_operator_approval",
    "private_endpoint_selection_record",
    "gossip_receipts",
    "route_health_after_run",
    "route_history_after_run",
    "cleanup_record",
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


def validate_status_list(value: Any, allowed: set[str], label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    result = []
    for item in value:
        if item not in allowed:
            raise ValueError(f"unsupported {label} entry")
        result.append(str(item))
    if len(set(result)) != len(result):
        raise ValueError(f"{label} entries must be unique")
    return result


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != REHEARSAL_MANIFEST_SCHEMA:
        raise ValueError("unsupported rehearsal manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("rehearsal manifest contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "rehearsal_id",
        "experiment_scope",
        "required_lab_bundle_statuses",
        "required_trust_statuses",
        "operator_review_required",
        "operator_review_recorded",
        "planned_phases",
    ]:
        if key not in manifest:
            raise ValueError(f"rehearsal manifest missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "rehearsal_id"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"rehearsal manifest missing {key}")
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_status_list(
        manifest["required_lab_bundle_statuses"],
        peer_mesh_lab_bundle.BUNDLE_STATUSES,
        "required_lab_bundle_statuses",
    )
    validate_status_list(
        manifest["required_trust_statuses"],
        peer_mesh_trust_gate.TRUST_STATUSES,
        "required_trust_statuses",
    )
    for key in ["operator_review_required", "operator_review_recorded"]:
        if not isinstance(manifest[key], bool):
            raise ValueError(f"{key} must be boolean")
    phases = manifest["planned_phases"]
    if not isinstance(phases, list) or not phases:
        raise ValueError("planned_phases must be a non-empty array")
    seen_phase_ids: set[str] = set()
    for phase in phases:
        if not isinstance(phase, dict):
            raise ValueError("planned phase must be an object")
        for key in ["phase_id", "evidence_kind", "required_before_live"]:
            if key not in phase:
                raise ValueError(f"planned phase missing {key}")
        phase_id = phase["phase_id"]
        if not isinstance(phase_id, str) or not phase_id:
            raise ValueError("planned phase missing phase_id")
        if phase_id in seen_phase_ids:
            raise ValueError("duplicate phase_id")
        seen_phase_ids.add(phase_id)
        if phase["evidence_kind"] not in EVIDENCE_KINDS:
            raise ValueError("unsupported evidence_kind")
        if not isinstance(phase["required_before_live"], bool):
            raise ValueError("required_before_live must be boolean")


def validate_trust_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_trust_gate.TRUST_REPORT_SCHEMA:
        raise ValueError("unsupported trust report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("trust report contains command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "experiment_scope", "overall_status", "summary"]:
        if key not in report:
            raise ValueError(f"trust report missing {key}")
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported trust report experiment_scope")
    if report["overall_status"] not in peer_mesh_trust_gate.TRUST_STATUSES:
        raise ValueError("unsupported trust report status")
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise ValueError("trust report summary must be an object")
    for key in ["configured_peer_count", "trusted_peer_count", "untrusted_peer_count"]:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"trust report summary missing non-negative {key}")


def check_entry(check_id: str, status: str, expected: str, observed: str, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported check status")
    return {
        "check_id": check_id,
        "status": status,
        "expected": expected,
        "observed": observed,
        "reason": reason,
    }


def phase_entry(phase_id: str, evidence_kind: str, status: str, required_before_live: bool, reason: str) -> dict[str, Any]:
    if status not in PHASE_STATUSES:
        raise ValueError("unsupported phase status")
    return {
        "phase_id": phase_id,
        "evidence_kind": evidence_kind,
        "status": status,
        "required_before_live": required_before_live,
        "reason": reason,
    }


def preflight_checks(manifest: dict[str, Any], bundle: dict[str, Any], trust: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        peer_mesh_trust_gate.validate_bundle_report(bundle)
        if bundle["fleet_id"] != manifest["fleet_id"]:
            raise ValueError("fleet_id mismatch")
        if bundle["source_agent_id"] != manifest["source_agent_id"]:
            raise ValueError("source_agent_id mismatch")
        if bundle["experiment_scope"] != manifest["experiment_scope"]:
            raise ValueError("experiment_scope mismatch")
        checks.append(check_entry("lab_bundle_valid", "passed", "valid lab bundle report", "valid", "lab bundle matches rehearsal identity"))
    except ValueError as error:
        checks.append(check_entry("lab_bundle_valid", "failed", "valid lab bundle report", "invalid", str(error)))

    try:
        validate_trust_report(trust)
        if trust["fleet_id"] != manifest["fleet_id"]:
            raise ValueError("fleet_id mismatch")
        if trust["source_agent_id"] != manifest["source_agent_id"]:
            raise ValueError("source_agent_id mismatch")
        if trust["experiment_scope"] != manifest["experiment_scope"]:
            raise ValueError("experiment_scope mismatch")
        checks.append(check_entry("trust_report_valid", "passed", "valid trust report", "valid", "trust report matches rehearsal identity"))
    except ValueError as error:
        checks.append(check_entry("trust_report_valid", "failed", "valid trust report", "invalid", str(error)))

    bundle_status = str(bundle.get("overall_status", "invalid"))
    required_bundle = set(manifest["required_lab_bundle_statuses"])
    if bundle_status in required_bundle:
        status = "manual_review" if bundle_status == "manual_review" else "passed"
        checks.append(
            check_entry(
                "lab_bundle_status",
                status,
                ", ".join(sorted(required_bundle)),
                bundle_status,
                "lab bundle status satisfies rehearsal manifest",
            )
        )
    else:
        checks.append(
            check_entry(
                "lab_bundle_status",
                "failed",
                ", ".join(sorted(required_bundle)),
                bundle_status,
                "lab bundle status is not acceptable for rehearsal",
            )
        )

    trust_status = str(trust.get("overall_status", "invalid"))
    required_trust = set(manifest["required_trust_statuses"])
    if trust_status in required_trust:
        status = "manual_review" if trust_status == "manual_review" else "passed"
        checks.append(
            check_entry(
                "trust_status",
                status,
                ", ".join(sorted(required_trust)),
                trust_status,
                "trust status satisfies rehearsal manifest",
            )
        )
    else:
        checks.append(
            check_entry(
                "trust_status",
                "failed",
                ", ".join(sorted(required_trust)),
                trust_status,
                "trust status is not acceptable for rehearsal",
            )
        )

    if manifest["operator_review_required"] and not manifest["operator_review_recorded"]:
        checks.append(
            check_entry(
                "operator_review",
                "manual_review",
                "operator review recorded in private workflow",
                "not represented in public synthetic evidence",
                "public rehearsal reports cannot grant live-device or LAN approval",
            )
        )
    elif manifest["operator_review_required"]:
        checks.append(
            check_entry(
                "operator_review",
                "passed",
                "operator review recorded in private workflow",
                "recorded flag true",
                "manifest says private operator review has been recorded",
            )
        )
    return checks


def phase_reviews(manifest: dict[str, Any], bundle: dict[str, Any], trust: dict[str, Any]) -> list[dict[str, Any]]:
    phases = []
    bundle_status = str(bundle.get("overall_status", "invalid"))
    trust_status = str(trust.get("overall_status", "invalid"))
    allowed_bundle = set(manifest["required_lab_bundle_statuses"])
    allowed_trust = set(manifest["required_trust_statuses"])
    for phase in manifest["planned_phases"]:
        phase_id = str(phase["phase_id"])
        kind = str(phase["evidence_kind"])
        required_before_live = bool(phase["required_before_live"])
        if kind == "preflight_bundle_report":
            status = "ready" if bundle_status in allowed_bundle else "blocked"
            reason = f"lab bundle status is {bundle_status}"
        elif kind == "trust_report":
            if trust_status not in allowed_trust:
                status = "blocked"
            elif trust_status == "manual_review":
                status = "manual_review"
            else:
                status = "ready"
            reason = f"trust status is {trust_status}"
        elif kind == "private_operator_approval":
            if manifest["operator_review_required"] and not manifest["operator_review_recorded"]:
                status = "manual_review"
                reason = "operator review is required and not represented in public synthetic evidence"
            else:
                status = "ready"
                reason = "operator review gate is not blocking this rehearsal report"
        else:
            status = "private_only"
            reason = "evidence belongs to a future private live-run workflow, not this public repo"
        phases.append(phase_entry(phase_id, kind, status, required_before_live, reason))
    return phases


def summarize(checks: list[dict[str, Any]], phases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "phase_count": len(phases),
        "ready_phase_count": sum(1 for phase in phases if phase["status"] == "ready"),
        "blocked_phase_count": sum(1 for phase in phases if phase["status"] == "blocked"),
        "manual_review_phase_count": sum(1 for phase in phases if phase["status"] == "manual_review"),
        "private_only_phase_count": sum(1 for phase in phases if phase["status"] == "private_only"),
    }


def overall_status(checks: list[dict[str, Any]], phases: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "blocked"
    if any(phase["status"] == "blocked" for phase in phases):
        return "blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    if any(phase["status"] == "manual_review" for phase in phases):
        return "manual_review"
    return "rehearsal_ready"


def build_rehearsal_report(
    manifest: dict[str, Any],
    lab_bundle_report: dict[str, Any],
    trust_report: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    checks = preflight_checks(manifest, lab_bundle_report, trust_report)
    phases = phase_reviews(manifest, lab_bundle_report, trust_report)
    status = overall_status(checks, phases)
    return {
        "schema": REHEARSAL_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "rehearsal_id": manifest["rehearsal_id"],
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": status,
        "checks": checks,
        "phases": phases,
        "summary": summarize(checks, phases),
        "authority_boundary": [
            "Rehearsal reports package synthetic preflight evidence and private evidence requirements only.",
            "Rehearsal reports do not approve live work, select endpoints, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Rehearsal reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    manifest = load_json(Path(args.manifest))
    lab_bundle_report = load_json(Path(args.lab_bundle_report))
    trust_report = load_json(Path(args.trust_report))
    write_json(
        args.output,
        build_rehearsal_report(
            manifest,
            lab_bundle_report,
            trust_report,
            now_text=args.now or None,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer live-run rehearsal report.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--lab-bundle-report", required=True)
    parser.add_argument("--trust-report", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
