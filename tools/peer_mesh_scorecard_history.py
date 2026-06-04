#!/usr/bin/env python3
"""Public-safe history over peer mesh scorecards.

The history report compares synthetic scorecard reports over time. It does not
approve live work, select endpoints, replay evidence, probe peers, open
sockets, copy files, discover devices, use ADB, send gossip, launch apps, or
carry commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_gossip
import peer_mesh_scorecard


SCORECARD_HISTORY_SCHEMA = "quest-termux-lab.peer-scorecard-history.v1"
TREND_VALUES = {"stable", "improving", "worsening", "mixed", "single_sample"}
DELTA_VALUES = {
    "observed_pressure_point",
    "single_sample_clear",
    "resolved",
    "new_pressure_point",
    "improved",
    "regressed",
    "persistent",
    "unchanged_clear",
}
STATUS_SCORE = {
    "missing": 0,
    "blocked": 0,
    "manual_review": 1,
    "synthetic_clear": 2,
}
SUMMARY_COUNTERS = [
    "artifact_count",
    "required_artifact_count",
    "synthetic_clear_count",
    "manual_review_count",
    "blocked_count",
    "missing_count",
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


def validate_summary(summary: Any) -> None:
    if not isinstance(summary, dict):
        raise ValueError("scorecard summary must be an object")
    for key in SUMMARY_COUNTERS:
        value = summary.get(key)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"scorecard summary missing non-negative integer {key}")


def validate_artifact_entry(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("scorecard artifact entry must be an object")
    for key in ["artifact_kind", "status", "source_status", "expected_schema", "observed_schema", "reason"]:
        if not isinstance(entry.get(key), str):
            raise ValueError(f"scorecard artifact entry missing {key}")
    if not isinstance(entry.get("required"), bool):
        raise ValueError("scorecard artifact entry missing required")
    if entry["status"] not in peer_mesh_scorecard.SCORE_STATUSES:
        raise ValueError("unsupported scorecard artifact status")


def validate_pressure_points(value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError("scorecard pressure_points must be an array")
    for point in value:
        if not isinstance(point, dict):
            raise ValueError("scorecard pressure point must be an object")
        for key in ["artifact_kind", "status", "reason"]:
            if not isinstance(point.get(key), str) or not point[key]:
                raise ValueError(f"scorecard pressure point missing {key}")
        if point["status"] not in {"manual_review", "blocked", "missing"}:
            raise ValueError("unsupported scorecard pressure point status")


def validate_scorecard_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_scorecard.SCORECARD_REPORT_SCHEMA:
        raise ValueError("unsupported scorecard report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("scorecard report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "scorecard_id",
        "experiment_scope",
        "overall_status",
        "artifacts",
        "pressure_points",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"scorecard report missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "scorecard_id", "experiment_scope"]:
        if not isinstance(report[key], str) or not report[key]:
            raise ValueError(f"scorecard report missing {key}")
    peer_mesh_gossip.parse_time(str(report["observed_at"]))
    if report["overall_status"] not in peer_mesh_scorecard.OVERALL_STATUSES:
        raise ValueError("unsupported scorecard overall status")
    if not isinstance(report["artifacts"], list):
        raise ValueError("scorecard artifacts must be an array")
    for entry in report["artifacts"]:
        validate_artifact_entry(entry)
    validate_pressure_points(report["pressure_points"])
    validate_summary(report["summary"])


def sort_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(reports, key=lambda report: peer_mesh_gossip.parse_time(str(report["observed_at"])))


def trend_for(statuses: list[str]) -> str:
    if len(statuses) <= 1:
        return "single_sample"
    first = STATUS_SCORE[statuses[0]]
    last = STATUS_SCORE[statuses[-1]]
    unique = set(statuses)
    if len(unique) == 1:
        return "stable"
    if last > first:
        return "improving"
    if last < first:
        return "worsening"
    return "mixed"


def delta_for(first_status: str, last_status: str, trend: str) -> str:
    if trend == "single_sample":
        if last_status == "synthetic_clear":
            return "single_sample_clear"
        return "observed_pressure_point"
    if first_status != "synthetic_clear" and last_status == "synthetic_clear":
        return "resolved"
    if first_status == "synthetic_clear" and last_status != "synthetic_clear":
        return "new_pressure_point"
    if STATUS_SCORE[last_status] > STATUS_SCORE[first_status]:
        return "improved"
    if STATUS_SCORE[last_status] < STATUS_SCORE[first_status]:
        return "regressed"
    if last_status != "synthetic_clear":
        return "persistent"
    return "unchanged_clear"


def scorecard_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    summary = report["summary"]
    return {
        "scorecard_id": str(report["scorecard_id"]),
        "observed_at": str(report["observed_at"]),
        "overall_status": str(report["overall_status"]),
        "synthetic_clear_count": int(summary["synthetic_clear_count"]),
        "manual_review_count": int(summary["manual_review_count"]),
        "blocked_count": int(summary["blocked_count"]),
        "missing_count": int(summary["missing_count"]),
        "pressure_point_count": len(report["pressure_points"]),
    }


def artifact_samples_for_reports(reports: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    artifact_kinds = sorted(
        {
            str(entry["artifact_kind"])
            for report in reports
            for entry in report["artifacts"]
        }
    )
    samples_by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in artifact_kinds}
    for report in reports:
        entries_by_kind = {str(entry["artifact_kind"]): entry for entry in report["artifacts"]}
        for kind in artifact_kinds:
            entry = entries_by_kind.get(kind)
            if entry is None:
                sample = {
                    "artifact_kind": kind,
                    "status": "missing",
                    "source_status": "absent",
                    "reason": "artifact not present in scorecard report",
                }
            else:
                sample = dict(entry)
            sample["observed_at"] = str(report["observed_at"])
            sample["scorecard_id"] = str(report["scorecard_id"])
            samples_by_kind[kind].append(sample)
    return samples_by_kind


def artifact_history_entry(kind: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(sample["status"]) for sample in samples]
    status_counts = {status: 0 for status in sorted(peer_mesh_scorecard.SCORE_STATUSES)}
    transition_count = 0
    previous_status = None
    for status in statuses:
        status_counts[status] += 1
        if previous_status is not None and previous_status != status:
            transition_count += 1
        previous_status = status
    first = samples[0]
    last = samples[-1]
    trend = trend_for(statuses)
    delta = delta_for(str(first["status"]), str(last["status"]), trend)
    return {
        "artifact_kind": kind,
        "sample_count": len(samples),
        "first_observed_at": str(first["observed_at"]),
        "last_observed_at": str(last["observed_at"]),
        "first_status": str(first["status"]),
        "last_status": str(last["status"]),
        "first_source_status": str(first["source_status"]),
        "last_source_status": str(last["source_status"]),
        "trend": trend,
        "delta": delta,
        "status_counts": status_counts,
        "transition_count": transition_count,
        "last_reason": str(last["reason"]),
    }


def pressure_point_deltas(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible_deltas = []
    for artifact in artifacts:
        if artifact["delta"] in {"unchanged_clear", "single_sample_clear"}:
            continue
        visible_deltas.append(
            {
                "artifact_kind": artifact["artifact_kind"],
                "first_status": artifact["first_status"],
                "last_status": artifact["last_status"],
                "trend": artifact["trend"],
                "delta": artifact["delta"],
                "last_reason": artifact["last_reason"],
            }
        )
    return visible_deltas


def summarize_history(
    scorecards: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    overall_trend: str,
) -> dict[str, Any]:
    last = scorecards[-1]
    trend_counts = {trend: 0 for trend in sorted(TREND_VALUES)}
    delta_counts = {delta: 0 for delta in sorted(DELTA_VALUES)}
    for artifact in artifacts:
        trend_counts[str(artifact["trend"])] += 1
        delta_counts[str(artifact["delta"])] += 1
    return {
        "report_count": len(scorecards),
        "artifact_kind_count": len(artifacts),
        "first_overall_status": scorecards[0]["overall_status"],
        "last_overall_status": last["overall_status"],
        "overall_trend": overall_trend,
        "last_synthetic_clear_count": int(last["synthetic_clear_count"]),
        "last_manual_review_count": int(last["manual_review_count"]),
        "last_blocked_count": int(last["blocked_count"]),
        "last_missing_count": int(last["missing_count"]),
        "last_pressure_point_count": int(last["pressure_point_count"]),
        "stable_artifact_count": trend_counts["stable"],
        "improving_artifact_count": trend_counts["improving"],
        "worsening_artifact_count": trend_counts["worsening"],
        "mixed_artifact_count": trend_counts["mixed"],
        "single_sample_artifact_count": trend_counts["single_sample"],
        "resolved_pressure_point_count": delta_counts["resolved"],
        "new_pressure_point_count": delta_counts["new_pressure_point"],
        "persistent_pressure_point_count": delta_counts["persistent"] + delta_counts["observed_pressure_point"],
    }


def history_overall_status(last_scorecard_status: str, artifacts: list[dict[str, Any]]) -> str:
    if last_scorecard_status == "blocked":
        return "blocked"
    if any(artifact["trend"] == "worsening" for artifact in artifacts):
        return "blocked"
    if any(artifact["last_status"] in {"blocked", "missing"} for artifact in artifacts):
        return "blocked"
    if last_scorecard_status == "manual_review":
        return "manual_review"
    if any(artifact["trend"] == "mixed" for artifact in artifacts):
        return "manual_review"
    if any(artifact["last_status"] == "manual_review" for artifact in artifacts):
        return "manual_review"
    return "synthetic_clear"


def build_history(reports: list[dict[str, Any]], now_text: str | None = None) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one scorecard report is required")
    for report in reports:
        validate_scorecard_report(report)
    first_report = reports[0]
    for report in reports[1:]:
        if report["fleet_id"] != first_report["fleet_id"]:
            raise ValueError("scorecard report fleet_id mismatch")
        if report["source_agent_id"] != first_report["source_agent_id"]:
            raise ValueError("scorecard report source_agent_id mismatch")
        if report["experiment_scope"] != first_report["experiment_scope"]:
            raise ValueError("scorecard report experiment_scope mismatch")

    ordered = sort_reports(reports)
    scorecards = [scorecard_snapshot(report) for report in ordered]
    overall_trend = trend_for([str(report["overall_status"]) for report in ordered])
    samples_by_kind = artifact_samples_for_reports(ordered)
    artifacts = [
        artifact_history_entry(kind, samples_by_kind[kind])
        for kind in sorted(samples_by_kind)
    ]
    observed_at = now_text or str(ordered[-1]["observed_at"])
    return {
        "schema": SCORECARD_HISTORY_SCHEMA,
        "fleet_id": first_report["fleet_id"],
        "source_agent_id": first_report["source_agent_id"],
        "observed_at": observed_at,
        "experiment_scope": first_report["experiment_scope"],
        "overall_status": history_overall_status(str(ordered[-1]["overall_status"]), artifacts),
        "overall_trend": overall_trend,
        "report_count": len(ordered),
        "first_report_at": str(ordered[0]["observed_at"]),
        "last_report_at": str(ordered[-1]["observed_at"]),
        "first_scorecard_id": str(ordered[0]["scorecard_id"]),
        "last_scorecard_id": str(ordered[-1]["scorecard_id"]),
        "scorecards": scorecards,
        "artifacts": artifacts,
        "pressure_point_deltas": pressure_point_deltas(artifacts),
        "summary": summarize_history(scorecards, artifacts, overall_trend),
        "authority_boundary": [
            "Scorecard history compares synthetic peer-mesh scorecard reports only.",
            "Scorecard history does not approve live work, select endpoints, replay evidence, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Scorecard history does not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    reports = [load_json(Path(path)) for path in args.reports]
    write_json(args.output, build_history(reports, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer scorecard history report.")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    parser.add_argument("reports", nargs="+")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
