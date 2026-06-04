#!/usr/bin/env python3
"""Tests for peer scorecard history summaries."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "tools" / "peer_mesh_scorecard_history.py"


def load_module():
    sys.path.insert(0, str(HISTORY_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_scorecard_history", HISTORY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_scorecard_history")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_scorecard_history"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_scorecard_history = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def sync_scorecard_summary(report: dict) -> None:
    artifacts = report["artifacts"]
    report["summary"]["artifact_count"] = len(artifacts)
    report["summary"]["required_artifact_count"] = sum(1 for artifact in artifacts if artifact["required"])
    for status in ["synthetic_clear", "manual_review", "blocked", "missing"]:
        report["summary"][f"{status}_count"] = sum(1 for artifact in artifacts if artifact["status"] == status)
    report["pressure_points"] = [
        {
            "artifact_kind": artifact["artifact_kind"],
            "status": artifact["status"],
            "reason": artifact["reason"],
        }
        for artifact in artifacts
        if artifact["status"] in {"manual_review", "blocked", "missing"}
    ]
    if any(artifact["status"] in {"blocked", "missing"} for artifact in artifacts):
        report["overall_status"] = "blocked"
    elif any(artifact["status"] == "manual_review" for artifact in artifacts):
        report["overall_status"] = "manual_review"
    else:
        report["overall_status"] = "synthetic_clear"


def scorecard_variant(
    status_by_kind: dict[str, str],
    observed_at: str,
    scorecard_id: str,
) -> dict:
    report = load_example("peer-scorecard-report.synthetic.json")
    report["observed_at"] = observed_at
    report["scorecard_id"] = scorecard_id
    for artifact in report["artifacts"]:
        status = status_by_kind.get(artifact["artifact_kind"], artifact["status"])
        artifact["status"] = status
        artifact["source_status"] = status
        artifact["reason"] = f"synthetic {status}"
    sync_scorecard_summary(report)
    return report


def all_artifact_status(status: str, observed_at: str, scorecard_id: str) -> dict:
    base = load_example("peer-scorecard-report.synthetic.json")
    return scorecard_variant(
        {artifact["artifact_kind"]: status for artifact in base["artifacts"]},
        observed_at,
        scorecard_id,
    )


class PeerScorecardHistoryTests(unittest.TestCase):
    def test_example_parses(self) -> None:
        payload = load_example("peer-scorecard-history.synthetic.json")
        self.assertEqual(payload["schema"], "quest-termux-lab.peer-scorecard-history.v1")

    def test_single_public_scorecard_is_blocked_single_sample(self) -> None:
        history = peer_mesh_scorecard_history.build_history(
            [load_example("peer-scorecard-report.synthetic.json")],
            now_text="2026-06-04T10:00:13Z",
        )
        self.assertEqual(history["overall_status"], "blocked")
        self.assertEqual(history["overall_trend"], "single_sample")
        self.assertEqual(history["summary"]["single_sample_artifact_count"], 8)
        self.assertEqual(history["summary"]["persistent_pressure_point_count"], 8)

    def test_improving_scorecard_detected_from_ordered_reports(self) -> None:
        older = all_artifact_status("blocked", "2026-06-04T10:00:00Z", "scorecard-old")
        newer = all_artifact_status("synthetic_clear", "2026-06-04T10:00:30Z", "scorecard-new")
        history = peer_mesh_scorecard_history.build_history([newer, older])
        self.assertEqual(history["first_scorecard_id"], "scorecard-old")
        self.assertEqual(history["last_scorecard_id"], "scorecard-new")
        self.assertEqual(history["overall_status"], "synthetic_clear")
        self.assertEqual(history["overall_trend"], "improving")
        self.assertEqual(history["summary"]["resolved_pressure_point_count"], 8)

    def test_worsening_artifact_blocks_history(self) -> None:
        older = all_artifact_status("synthetic_clear", "2026-06-04T10:00:00Z", "scorecard-old")
        newer = all_artifact_status("synthetic_clear", "2026-06-04T10:00:30Z", "scorecard-new")
        for artifact in newer["artifacts"]:
            if artifact["artifact_kind"] == "trust_report":
                artifact["status"] = "blocked"
                artifact["source_status"] = "untrusted"
                artifact["reason"] = "trust regressed"
        sync_scorecard_summary(newer)
        history = peer_mesh_scorecard_history.build_history([older, newer])
        trust = [artifact for artifact in history["artifacts"] if artifact["artifact_kind"] == "trust_report"][0]
        self.assertEqual(history["overall_status"], "blocked")
        self.assertEqual(trust["trend"], "worsening")
        self.assertEqual(trust["delta"], "new_pressure_point")
        self.assertEqual(history["summary"]["new_pressure_point_count"], 1)

    def test_blocked_to_manual_review_is_improved_but_not_clear(self) -> None:
        older = all_artifact_status("blocked", "2026-06-04T10:00:00Z", "scorecard-old")
        newer = all_artifact_status("manual_review", "2026-06-04T10:00:30Z", "scorecard-new")
        history = peer_mesh_scorecard_history.build_history([older, newer])
        self.assertEqual(history["overall_status"], "manual_review")
        self.assertEqual(history["overall_trend"], "improving")
        deltas = {delta["delta"] for delta in history["pressure_point_deltas"]}
        self.assertEqual(deltas, {"improved"})

    def test_missing_artifact_across_reports_blocks_history(self) -> None:
        older = all_artifact_status("synthetic_clear", "2026-06-04T10:00:00Z", "scorecard-old")
        newer = all_artifact_status("synthetic_clear", "2026-06-04T10:00:30Z", "scorecard-new")
        newer["artifacts"] = [
            artifact for artifact in newer["artifacts"] if artifact["artifact_kind"] != "cleanup_record"
        ]
        sync_scorecard_summary(newer)
        history = peer_mesh_scorecard_history.build_history([older, newer])
        cleanup = [artifact for artifact in history["artifacts"] if artifact["artifact_kind"] == "cleanup_record"][0]
        self.assertEqual(history["overall_status"], "blocked")
        self.assertEqual(cleanup["last_status"], "missing")
        self.assertEqual(cleanup["last_source_status"], "absent")

    def test_fleet_mismatch_is_rejected(self) -> None:
        first = load_example("peer-scorecard-report.synthetic.json")
        second = load_example("peer-scorecard-report.synthetic.json")
        second["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_scorecard_history.build_history([first, second])

    def test_forbidden_report_field_is_rejected(self) -> None:
        report = load_example("peer-scorecard-report.synthetic.json")
        report["adb_target"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_scorecard_history.validate_scorecard_report(report)

    def test_empty_history_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            peer_mesh_scorecard_history.build_history([])


if __name__ == "__main__":
    unittest.main()
