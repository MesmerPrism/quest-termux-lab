#!/usr/bin/env python3
"""Tests for peer live-lab readiness reports."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
READINESS_PATH = REPO_ROOT / "tools" / "peer_mesh_live_lab_readiness.py"


def load_module():
    sys.path.insert(0, str(READINESS_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_live_lab_readiness", READINESS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_live_lab_readiness")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_live_lab_readiness"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_live_lab_readiness = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def healthy_history() -> dict:
    history = load_example("peer-route-health-history.synthetic.json")
    history["report_count"] = 2
    history["summary"]["last_unknown_count"] = 0
    history["summary"]["stable_count"] = 2
    history["summary"]["single_sample_count"] = 0
    for route in history["routes"]:
        route["sample_count"] = 2
        route["first_status"] = "healthy"
        route["last_status"] = "healthy"
        route["trend"] = "stable"
        route["status_counts"] = {
            "degraded": 0,
            "disabled": 0,
            "healthy": 2,
            "unavailable": 0,
            "unknown": 0,
        }
        route["last_reason"] = "synthetic delivery accepted"
    return history


class PeerLiveLabReadinessTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-live-lab-readiness-policy.synthetic.json": (
                "quest-termux-lab.peer-live-lab-readiness-policy.v1"
            ),
            "peer-live-lab-readiness-report.synthetic.json": (
                "quest-termux-lab.peer-live-lab-readiness-report.v1"
            ),
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_synthetic_history_is_not_ready_because_unknown_route(self) -> None:
        report = peer_mesh_live_lab_readiness.build_readiness_report(
            load_example("peer-live-lab-readiness-policy.synthetic.json"),
            load_example("peer-route-health-history.synthetic.json"),
            now_text="2026-06-04T10:00:06Z",
        )
        self.assertEqual(report["overall_status"], "not_ready")
        failed = [check["check_id"] for check in report["checks"] if check["status"] == "failed"]
        self.assertIn("no_unknown_routes", failed)

    def test_ready_when_history_satisfies_policy_and_no_operator_gate(self) -> None:
        policy = load_example("peer-live-lab-readiness-policy.synthetic.json")
        policy["operator_approval_required"] = False
        report = peer_mesh_live_lab_readiness.build_readiness_report(
            policy,
            healthy_history(),
            now_text="2026-06-04T10:00:06Z",
        )
        self.assertEqual(report["overall_status"], "ready")
        self.assertEqual(report["summary"]["not_ready_route_count"], 0)

    def test_operator_gate_forces_manual_review_after_passed_checks(self) -> None:
        report = peer_mesh_live_lab_readiness.build_readiness_report(
            load_example("peer-live-lab-readiness-policy.synthetic.json"),
            healthy_history(),
            now_text="2026-06-04T10:00:06Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        manual = [check["check_id"] for check in report["checks"] if check["status"] == "manual_review"]
        self.assertEqual(manual, ["operator_approval"])

    def test_worsening_route_is_not_ready(self) -> None:
        history = healthy_history()
        history["routes"][0]["trend"] = "worsening"
        history["summary"]["worsening_count"] = 1
        report = peer_mesh_live_lab_readiness.build_readiness_report(
            load_example("peer-live-lab-readiness-policy.synthetic.json"),
            history,
            now_text="2026-06-04T10:00:06Z",
        )
        self.assertEqual(report["overall_status"], "not_ready")
        self.assertEqual(report["routes"][0]["readiness_status"], "not_ready")

    def test_history_count_below_policy_is_not_ready(self) -> None:
        policy = load_example("peer-live-lab-readiness-policy.synthetic.json")
        policy["min_history_reports"] = 3
        report = peer_mesh_live_lab_readiness.build_readiness_report(
            policy,
            healthy_history(),
            now_text="2026-06-04T10:00:06Z",
        )
        self.assertEqual(report["overall_status"], "not_ready")
        failed = [check["check_id"] for check in report["checks"] if check["status"] == "failed"]
        self.assertIn("history_report_count", failed)

    def test_fleet_mismatch_is_rejected(self) -> None:
        policy = load_example("peer-live-lab-readiness-policy.synthetic.json")
        history = healthy_history()
        history["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_live_lab_readiness.build_readiness_report(policy, history)

    def test_forbidden_policy_field_is_rejected(self) -> None:
        policy = load_example("peer-live-lab-readiness-policy.synthetic.json")
        policy["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_live_lab_readiness.validate_policy(policy)

    def test_malformed_history_summary_is_rejected(self) -> None:
        history = healthy_history()
        del history["summary"]["tracked_route_count"]
        with self.assertRaises(ValueError):
            peer_mesh_live_lab_readiness.validate_history(history)

    def test_string_history_summary_count_is_rejected(self) -> None:
        history = healthy_history()
        history["summary"]["last_unknown_count"] = "0"
        with self.assertRaises(ValueError):
            peer_mesh_live_lab_readiness.validate_history(history)

    def test_empty_allowed_statuses_rejected(self) -> None:
        policy = load_example("peer-live-lab-readiness-policy.synthetic.json")
        policy["allowed_last_statuses"] = []
        with self.assertRaises(ValueError):
            peer_mesh_live_lab_readiness.validate_policy(policy)


if __name__ == "__main__":
    unittest.main()
