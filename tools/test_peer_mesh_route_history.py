#!/usr/bin/env python3
"""Tests for peer route-health history summaries."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTE_HISTORY_PATH = REPO_ROOT / "tools" / "peer_mesh_route_history.py"


def load_module():
    sys.path.insert(0, str(ROUTE_HISTORY_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_route_history", ROUTE_HISTORY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_route_history")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_route_history"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_route_history = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def report_variant(status: str, observed_at: str, reason: str = "synthetic test") -> dict:
    report = load_example("peer-route-health-report.synthetic.json")
    report["observed_at"] = observed_at
    report["routes"][0]["status"] = status
    report["routes"][0]["reason"] = reason
    return report


class PeerRouteHistoryTests(unittest.TestCase):
    def test_example_parses(self) -> None:
        payload = load_example("peer-route-health-history.synthetic.json")
        self.assertEqual(payload["schema"], "quest-termux-lab.peer-route-health-history.v1")

    def test_single_report_marks_single_sample(self) -> None:
        history = peer_mesh_route_history.build_history(
            [load_example("peer-route-health-report.synthetic.json")],
            now_text="2026-06-04T10:00:05Z",
        )
        beta = [route for route in history["routes"] if route["target_agent_id"] == "quest-agent-beta"][0]
        self.assertEqual(beta["trend"], "single_sample")
        self.assertEqual(beta["last_status"], "healthy")
        self.assertEqual(history["summary"]["single_sample_count"], 2)

    def test_improving_route_detected_from_ordered_reports(self) -> None:
        older = report_variant("degraded", "2026-06-04T10:00:00Z", "synthetic no response")
        newer = report_variant("healthy", "2026-06-04T10:00:30Z", "synthetic accepted")
        history = peer_mesh_route_history.build_history([newer, older])
        beta = [route for route in history["routes"] if route["target_agent_id"] == "quest-agent-beta"][0]
        self.assertEqual(beta["first_status"], "degraded")
        self.assertEqual(beta["last_status"], "healthy")
        self.assertEqual(beta["trend"], "improving")
        self.assertEqual(beta["transition_count"], 1)

    def test_worsening_route_detected(self) -> None:
        older = report_variant("healthy", "2026-06-04T10:00:00Z", "synthetic accepted")
        newer = report_variant("unavailable", "2026-06-04T10:00:30Z", "max attempts reached")
        history = peer_mesh_route_history.build_history([older, newer])
        beta = [route for route in history["routes"] if route["target_agent_id"] == "quest-agent-beta"][0]
        self.assertEqual(beta["trend"], "worsening")
        self.assertEqual(history["summary"]["last_unavailable_count"], 1)

    def test_stable_route_detected(self) -> None:
        first = report_variant("degraded", "2026-06-04T10:00:00Z")
        second = report_variant("degraded", "2026-06-04T10:00:30Z")
        history = peer_mesh_route_history.build_history([first, second])
        beta = [route for route in history["routes"] if route["target_agent_id"] == "quest-agent-beta"][0]
        self.assertEqual(beta["trend"], "stable")
        self.assertEqual(beta["status_counts"]["degraded"], 2)

    def test_mixed_route_detected_when_first_and_last_match(self) -> None:
        first = report_variant("degraded", "2026-06-04T10:00:00Z")
        middle = report_variant("healthy", "2026-06-04T10:00:15Z")
        last = report_variant("degraded", "2026-06-04T10:00:30Z")
        history = peer_mesh_route_history.build_history([last, first, middle])
        beta = [route for route in history["routes"] if route["target_agent_id"] == "quest-agent-beta"][0]
        self.assertEqual(beta["trend"], "mixed")
        self.assertEqual(beta["transition_count"], 2)

    def test_fleet_mismatch_is_rejected(self) -> None:
        first = load_example("peer-route-health-report.synthetic.json")
        second = load_example("peer-route-health-report.synthetic.json")
        second["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_route_history.build_history([first, second])

    def test_forbidden_report_field_is_rejected(self) -> None:
        report = load_example("peer-route-health-report.synthetic.json")
        report["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_route_history.validate_health_report(report)

    def test_empty_history_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            peer_mesh_route_history.build_history([])


if __name__ == "__main__":
    unittest.main()
