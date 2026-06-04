#!/usr/bin/env python3
"""Public-safe regression gate over peer scorecard history.

The regression report evaluates synthetic scorecard history against an explicit
policy. It does not approve live work, select endpoints, replay evidence,
monitor peers, probe peers, open sockets, copy files, discover devices, use
ADB, send gossip, launch apps, or carry commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_gossip
import peer_mesh_live_lab_readiness
import peer_mesh_scorecard
import peer_mesh_scorecard_history


REGRESSION_POLICY_SCHEMA = "quest-termux-lab.peer-scorecard-regression-policy.v1"
REGRESSION_REPORT_SCHEMA = "quest-termux-lab.peer-scorecard-regression-report.v1"
CHECK_STATUSES = {"passed", "manual_review", "failed"}
OVERALL_STATUSES = {"regression_clear", "manual_review", "regression_blocked"}
POLICY_INTEGER_FIELDS = [
    "min_report_count",
    "max_new_pressure_point_count",
    "max_worsening_artifact_count",
    "max_persistent_pressure_point_count",
    "max_last_blocked_count",
    "max_last_missing_count",
]


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


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != REGRESSION_POLICY_SCHEMA:
        raise ValueError("unsupported scorecard regression policy schema")
    if peer_mesh_gossip.contains_forbidden_key(policy):
        raise ValueError("scorecard regression policy contains command-like or credential-like fields")
    for key in [
        "policy_id",
        "fleet_id",
        "source_agent_id",
        "experiment_scope",
        "allow_single_sample_review",
        "allow_manual_review_history",
        "require_non_worsening_overall",
        "authority_boundary",
    ] + POLICY_INTEGER_FIELDS:
        if key not in policy:
            raise ValueError(f"scorecard regression policy missing {key}")
    for key in ["policy_id", "fleet_id", "source_agent_id"]:
        if not isinstance(policy[key], str) or not policy[key]:
            raise ValueError(f"scorecard regression policy missing {key}")
    if policy["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    for key in POLICY_INTEGER_FIELDS:
        if not isinstance(policy[key], int) or policy[key] < 0:
            raise ValueError(f"scorecard regression policy {key} must be a non-negative integer")
    for key in ["allow_single_sample_review", "allow_manual_review_history", "require_non_worsening_overall"]:
        if not isinstance(policy[key], bool):
            raise ValueError(f"scorecard regression policy {key} must be boolean")
    boundary = policy["authority_boundary"]
    if not isinstance(boundary, list) or not boundary:
        raise ValueError("scorecard regression policy authority_boundary must be a non-empty array")
    for item in boundary:
        if not isinstance(item, str) or not item:
            raise ValueError("scorecard regression policy authority boundary entry must be text")


def validate_history(history: dict[str, Any]) -> None:
    if history.get("schema") != peer_mesh_scorecard_history.SCORECARD_HISTORY_SCHEMA:
        raise ValueError("unsupported scorecard history schema")
    if peer_mesh_gossip.contains_forbidden_key(history):
        raise ValueError("scorecard history contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "overall_status",
        "overall_trend",
        "report_count",
        "first_report_at",
        "last_report_at",
        "summary",
    ]:
        if key not in history:
            raise ValueError(f"scorecard history missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "experiment_scope"]:
        if not isinstance(history[key], str) or not history[key]:
            raise ValueError(f"scorecard history missing {key}")
    peer_mesh_gossip.parse_time(str(history["observed_at"]))
    if history["overall_status"] not in peer_mesh_scorecard.OVERALL_STATUSES:
        raise ValueError("unsupported scorecard history overall status")
    if history["overall_trend"] not in peer_mesh_scorecard_history.TREND_VALUES:
        raise ValueError("unsupported scorecard history overall trend")
    if not isinstance(history["report_count"], int) or history["report_count"] < 1:
        raise ValueError("scorecard history report_count must be positive")
    summary = history["summary"]
    if not isinstance(summary, dict):
        raise ValueError("scorecard history summary must be an object")
    for key in [
        "report_count",
        "last_blocked_count",
        "last_missing_count",
        "last_manual_review_count",
        "worsening_artifact_count",
        "new_pressure_point_count",
        "persistent_pressure_point_count",
    ]:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"scorecard history summary missing non-negative integer {key}")


def check_entry(check_id: str, status: str, observed: Any, threshold: Any, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported regression check status")
    return {
        "check_id": check_id,
        "status": status,
        "observed": str(observed),
        "threshold": str(threshold),
        "reason": reason,
    }


def build_checks(policy: dict[str, Any], history: dict[str, Any]) -> list[dict[str, Any]]:
    summary = history["summary"]
    checks: list[dict[str, Any]] = []

    report_count = int(history["report_count"])
    min_report_count = int(policy["min_report_count"])
    if report_count >= min_report_count:
        checks.append(check_entry("report_count", "passed", report_count, f">= {min_report_count}", "history has enough scorecard reports"))
    elif policy["allow_single_sample_review"] and report_count == 1:
        checks.append(check_entry("report_count", "manual_review", report_count, f">= {min_report_count}", "single scorecard needs repeat evidence"))
    else:
        checks.append(check_entry("report_count", "failed", report_count, f">= {min_report_count}", "not enough scorecard reports"))

    overall_trend = str(history["overall_trend"])
    if policy["require_non_worsening_overall"] and overall_trend == "worsening":
        checks.append(check_entry("overall_trend", "failed", overall_trend, "not worsening", "overall scorecard trend is worsening"))
    elif policy["require_non_worsening_overall"] and overall_trend == "mixed":
        checks.append(check_entry("overall_trend", "manual_review", overall_trend, "not worsening", "overall scorecard trend is mixed"))
    else:
        checks.append(check_entry("overall_trend", "passed", overall_trend, "not worsening", "overall scorecard trend is acceptable"))

    history_status = str(history["overall_status"])
    if history_status == "blocked":
        checks.append(check_entry("history_status", "failed", history_status, "not blocked", "latest scorecard history is blocked"))
    elif history_status == "manual_review" and not policy["allow_manual_review_history"]:
        checks.append(check_entry("history_status", "failed", history_status, "synthetic_clear", "manual-review history is not allowed by policy"))
    elif history_status == "manual_review":
        checks.append(check_entry("history_status", "manual_review", history_status, "synthetic_clear", "history requires manual review"))
    else:
        checks.append(check_entry("history_status", "passed", history_status, "synthetic_clear", "history is synthetically clear"))

    numeric_checks = [
        (
            "new_pressure_points",
            int(summary["new_pressure_point_count"]),
            int(policy["max_new_pressure_point_count"]),
            "new pressure points are within policy",
            "new pressure points exceed policy",
        ),
        (
            "worsening_artifacts",
            int(summary["worsening_artifact_count"]),
            int(policy["max_worsening_artifact_count"]),
            "worsening artifacts are within policy",
            "worsening artifacts exceed policy",
        ),
        (
            "persistent_pressure_points",
            int(summary["persistent_pressure_point_count"]),
            int(policy["max_persistent_pressure_point_count"]),
            "persistent pressure points are within policy",
            "persistent pressure points exceed policy",
        ),
        (
            "last_blocked_artifacts",
            int(summary["last_blocked_count"]),
            int(policy["max_last_blocked_count"]),
            "latest blocked artifact count is within policy",
            "latest blocked artifact count exceeds policy",
        ),
        (
            "last_missing_artifacts",
            int(summary["last_missing_count"]),
            int(policy["max_last_missing_count"]),
            "latest missing artifact count is within policy",
            "latest missing artifact count exceeds policy",
        ),
    ]
    for check_id, observed, threshold, ok_reason, fail_reason in numeric_checks:
        status = "passed" if observed <= threshold else "failed"
        checks.append(check_entry(check_id, status, observed, f"<= {threshold}", ok_reason if status == "passed" else fail_reason))
    return checks


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
    }


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "regression_blocked"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "regression_clear"


def build_regression_report(
    policy: dict[str, Any],
    history: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    validate_history(history)
    if history["fleet_id"] != policy["fleet_id"]:
        raise ValueError("scorecard regression fleet_id mismatch")
    if history["source_agent_id"] != policy["source_agent_id"]:
        raise ValueError("scorecard regression source_agent_id mismatch")
    if history["experiment_scope"] != policy["experiment_scope"]:
        raise ValueError("scorecard regression experiment_scope mismatch")
    checks = build_checks(policy, history)
    return {
        "schema": REGRESSION_REPORT_SCHEMA,
        "fleet_id": policy["fleet_id"],
        "source_agent_id": policy["source_agent_id"],
        "observed_at": now_text or str(history["observed_at"]),
        "experiment_scope": policy["experiment_scope"],
        "policy_id": policy["policy_id"],
        "history_status": history["overall_status"],
        "history_trend": history["overall_trend"],
        "overall_status": overall_status(checks),
        "checks": checks,
        "summary": summarize_checks(checks),
        "authority_boundary": [
            "Scorecard regression evaluates synthetic scorecard history only.",
            "Scorecard regression does not approve live work, select endpoints, replay evidence, monitor peers, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Scorecard regression does not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    policy = load_json(Path(args.policy))
    history = load_json(Path(args.history))
    write_json(args.output, build_regression_report(policy, history, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer scorecard regression report.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
