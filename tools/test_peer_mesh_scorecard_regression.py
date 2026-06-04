#!/usr/bin/env python3
"""Tests for peer scorecard regression gates."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REGRESSION_PATH = REPO_ROOT / "tools" / "peer_mesh_scorecard_regression.py"
HISTORY_PATH = REPO_ROOT / "tools" / "peer_mesh_scorecard_history.py"


def load_named_module(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_scorecard_history = load_named_module("peer_mesh_scorecard_history", HISTORY_PATH)
peer_mesh_scorecard_regression = load_named_module("peer_mesh_scorecard_regression", REGRESSION_PATH)


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


def scorecard_with_status(status: str, observed_at: str, scorecard_id: str) -> dict:
    report = load_example("peer-scorecard-report.synthetic.json")
    report["observed_at"] = observed_at
    report["scorecard_id"] = scorecard_id
    for artifact in report["artifacts"]:
        artifact["status"] = status
        artifact["source_status"] = status
        artifact["reason"] = f"synthetic {status}"
    sync_scorecard_summary(report)
    return report


def history_from_scorecards(scorecards: list[dict]) -> dict:
    return peer_mesh_scorecard_history.build_history(scorecards, now_text="2026-06-04T10:00:14Z")


class PeerScorecardRegressionTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-scorecard-regression-policy.synthetic.json": "quest-termux-lab.peer-scorecard-regression-policy.v1",
            "peer-scorecard-regression-report.synthetic.json": "quest-termux-lab.peer-scorecard-regression-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_regression_blocked(self) -> None:
        report = peer_mesh_scorecard_regression.build_regression_report(
            load_example("peer-scorecard-regression-policy.synthetic.json"),
            load_example("peer-scorecard-history.synthetic.json"),
            now_text="2026-06-04T10:00:14Z",
        )
        self.assertEqual(report["overall_status"], "regression_blocked")
        self.assertGreater(report["summary"]["failed_check_count"], 0)

    def test_clear_repeated_history_passes(self) -> None:
        history = history_from_scorecards(
            [
                scorecard_with_status("synthetic_clear", "2026-06-04T10:00:00Z", "scorecard-old"),
                scorecard_with_status("synthetic_clear", "2026-06-04T10:00:30Z", "scorecard-new"),
            ]
        )
        report = peer_mesh_scorecard_regression.build_regression_report(
            load_example("peer-scorecard-regression-policy.synthetic.json"),
            history,
        )
        self.assertEqual(report["overall_status"], "regression_clear")
        self.assertEqual(report["summary"]["failed_check_count"], 0)

    def test_single_sample_can_only_require_manual_review_when_allowed(self) -> None:
        policy = load_example("peer-scorecard-regression-policy.synthetic.json")
        policy["allow_single_sample_review"] = True
        history = history_from_scorecards(
            [scorecard_with_status("synthetic_clear", "2026-06-04T10:00:00Z", "scorecard-one")]
        )
        report = peer_mesh_scorecard_regression.build_regression_report(policy, history)
        self.assertEqual(report["overall_status"], "manual_review")
        self.assertEqual(report["summary"]["failed_check_count"], 0)

    def test_manual_review_history_blocks_when_policy_disallows(self) -> None:
        history = history_from_scorecards(
            [
                scorecard_with_status("manual_review", "2026-06-04T10:00:00Z", "scorecard-old"),
                scorecard_with_status("manual_review", "2026-06-04T10:00:30Z", "scorecard-new"),
            ]
        )
        report = peer_mesh_scorecard_regression.build_regression_report(
            load_example("peer-scorecard-regression-policy.synthetic.json"),
            history,
        )
        self.assertEqual(report["overall_status"], "regression_blocked")
        statuses = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(statuses["history_status"], "failed")

    def test_manual_review_history_can_remain_review_when_allowed(self) -> None:
        policy = load_example("peer-scorecard-regression-policy.synthetic.json")
        policy["allow_manual_review_history"] = True
        policy["max_persistent_pressure_point_count"] = 8
        history = history_from_scorecards(
            [
                scorecard_with_status("manual_review", "2026-06-04T10:00:00Z", "scorecard-old"),
                scorecard_with_status("manual_review", "2026-06-04T10:00:30Z", "scorecard-new"),
            ]
        )
        report = peer_mesh_scorecard_regression.build_regression_report(policy, history)
        self.assertEqual(report["overall_status"], "manual_review")

    def test_worsening_history_blocks(self) -> None:
        history = history_from_scorecards(
            [
                scorecard_with_status("synthetic_clear", "2026-06-04T10:00:00Z", "scorecard-old"),
                scorecard_with_status("blocked", "2026-06-04T10:00:30Z", "scorecard-new"),
            ]
        )
        report = peer_mesh_scorecard_regression.build_regression_report(
            load_example("peer-scorecard-regression-policy.synthetic.json"),
            history,
        )
        self.assertEqual(report["overall_status"], "regression_blocked")
        statuses = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(statuses["overall_trend"], "failed")

    def test_identity_mismatch_is_rejected(self) -> None:
        policy = load_example("peer-scorecard-regression-policy.synthetic.json")
        history = load_example("peer-scorecard-history.synthetic.json")
        history["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_scorecard_regression.build_regression_report(policy, history)

    def test_forbidden_policy_field_is_rejected(self) -> None:
        policy = load_example("peer-scorecard-regression-policy.synthetic.json")
        policy["command"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_scorecard_regression.validate_policy(policy)

    def test_forbidden_history_field_is_rejected(self) -> None:
        history = load_example("peer-scorecard-history.synthetic.json")
        history["adb_target"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_scorecard_regression.validate_history(history)


if __name__ == "__main__":
    unittest.main()
