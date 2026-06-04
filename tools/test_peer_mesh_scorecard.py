#!/usr/bin/env python3
"""Tests for peer mesh scorecards."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCORECARD_PATH = REPO_ROOT / "tools" / "peer_mesh_scorecard.py"


def load_module():
    sys.path.insert(0, str(SCORECARD_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_scorecard", SCORECARD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_scorecard")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_scorecard"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_scorecard = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def clear_readiness() -> dict:
    report = load_example("peer-live-lab-readiness-report.synthetic.json")
    report["overall_status"] = "ready"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["ready_route_count"] = 2
    report["summary"]["not_ready_route_count"] = 0
    return report


def clear_bundle() -> dict:
    report = load_example("peer-lab-bundle-report.synthetic.json")
    report["overall_status"] = "synthetic_ready"
    report["readiness_status"] = "ready"
    report["operator_approval_required"] = False
    report["operator_approval_recorded"] = False
    report["summary"]["ready_route_count"] = 2
    report["summary"]["not_ready_route_count"] = 0
    return report


def clear_trust() -> dict:
    report = load_example("peer-trust-report.synthetic.json")
    report["overall_status"] = "trusted"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    for check in report["checks"]:
        if check["status"] != "passed":
            check["status"] = "passed"
        if check["check_id"] == "lab_bundle_status":
            check["observed"] = "synthetic_ready"
        if check["check_id"] == "operator_review":
            check["observed"] = "recorded flag true"
    return report


def clear_rehearsal() -> dict:
    report = load_example("peer-rehearsal-report.synthetic.json")
    report["overall_status"] = "rehearsal_ready"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["blocked_phase_count"] = 0
    report["summary"]["manual_review_phase_count"] = 0
    for check in report["checks"]:
        check["status"] = "passed"
    for phase in report["phases"]:
        if phase["status"] in {"blocked", "manual_review"}:
            phase["status"] = "ready"
    return report


def clear_intake() -> dict:
    report = load_example("peer-evidence-intake-report.synthetic.json")
    report["overall_status"] = "accepted"
    for artifact in report["artifacts"]:
        artifact["status"] = "accepted"
        artifact["reason"] = "artifact accepted"
    report["summary"]["accepted_artifact_count"] = len(report["artifacts"])
    report["summary"]["rejected_artifact_count"] = 0
    report["summary"]["manual_review_artifact_count"] = 0
    return report


def clear_route_health() -> dict:
    report = load_example("peer-route-health-report.synthetic.json")
    report["routes"][1]["status"] = "healthy"
    report["routes"][1]["reason"] = "synthetic delivery accepted"
    report["summary"]["healthy_count"] = 2
    report["summary"]["unknown_count"] = 0
    report["summary"]["unavailable_count"] = 0
    return report


def clear_route_history() -> dict:
    report = load_example("peer-route-health-history.synthetic.json")
    for route in report["routes"]:
        route["first_status"] = "healthy"
        route["last_status"] = "healthy"
        route["trend"] = "stable"
        route["status_counts"] = {
            "degraded": 0,
            "disabled": 0,
            "healthy": 1,
            "unavailable": 0,
            "unknown": 0,
        }
    report["summary"]["last_healthy_count"] = 2
    report["summary"]["last_unknown_count"] = 0
    report["summary"]["last_unavailable_count"] = 0
    report["summary"]["worsening_count"] = 0
    return report


def clear_cleanup() -> dict:
    report = load_example("peer-cleanup-record.synthetic.json")
    report["cleanup_status"] = "completed"
    return report


def clear_artifacts() -> dict[str, dict]:
    return {
        "readiness_report": clear_readiness(),
        "lab_bundle_report": clear_bundle(),
        "trust_report": clear_trust(),
        "rehearsal_report": clear_rehearsal(),
        "evidence_intake_report": clear_intake(),
        "route_health_report": clear_route_health(),
        "route_history_report": clear_route_history(),
        "cleanup_record": clear_cleanup(),
    }


class PeerMeshScorecardTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-scorecard-manifest.synthetic.json": "quest-termux-lab.peer-scorecard-manifest.v1",
            "peer-scorecard-report.synthetic.json": "quest-termux-lab.peer-scorecard-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked(self) -> None:
        manifest = load_example("peer-scorecard-manifest.synthetic.json")
        report = peer_mesh_scorecard.build_scorecard_report(
            manifest,
            peer_mesh_scorecard.load_artifacts_from_manifest(manifest, REPO_ROOT),
            now_text="2026-06-04T10:00:12Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertGreater(report["summary"]["blocked_count"], 0)

    def test_clear_artifacts_are_synthetic_clear(self) -> None:
        report = peer_mesh_scorecard.build_scorecard_report(
            load_example("peer-scorecard-manifest.synthetic.json"),
            clear_artifacts(),
            now_text="2026-06-04T10:00:12Z",
        )
        self.assertEqual(report["overall_status"], "synthetic_clear")
        self.assertEqual(report["pressure_points"], [])

    def test_unknown_route_health_forces_manual_review(self) -> None:
        artifacts = clear_artifacts()
        artifacts["route_health_report"] = load_example("peer-route-health-report.synthetic.json")
        report = peer_mesh_scorecard.build_scorecard_report(
            load_example("peer-scorecard-manifest.synthetic.json"),
            artifacts,
            now_text="2026-06-04T10:00:12Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        pressure = [point["artifact_kind"] for point in report["pressure_points"]]
        self.assertIn("route_health_report", pressure)

    def test_missing_required_artifact_blocks_scorecard(self) -> None:
        artifacts = clear_artifacts()
        del artifacts["trust_report"]
        report = peer_mesh_scorecard.build_scorecard_report(
            load_example("peer-scorecard-manifest.synthetic.json"),
            artifacts,
            now_text="2026-06-04T10:00:12Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        missing = [entry["artifact_kind"] for entry in report["artifacts"] if entry["status"] == "missing"]
        self.assertIn("trust_report", missing)

    def test_missing_optional_artifact_does_not_block(self) -> None:
        manifest = load_example("peer-scorecard-manifest.synthetic.json")
        manifest["required_artifact_kinds"].remove("cleanup_record")
        manifest["optional_artifact_kinds"] = ["cleanup_record"]
        artifacts = clear_artifacts()
        del artifacts["cleanup_record"]
        report = peer_mesh_scorecard.build_scorecard_report(
            manifest,
            artifacts,
            now_text="2026-06-04T10:00:12Z",
        )
        self.assertEqual(report["overall_status"], "synthetic_clear")

    def test_fleet_mismatch_blocks_artifact(self) -> None:
        artifacts = clear_artifacts()
        artifacts["rehearsal_report"]["fleet_id"] = "other-fleet"
        report = peer_mesh_scorecard.build_scorecard_report(
            load_example("peer-scorecard-manifest.synthetic.json"),
            artifacts,
            now_text="2026-06-04T10:00:12Z",
        )
        self.assertEqual(report["overall_status"], "blocked")

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = load_example("peer-scorecard-manifest.synthetic.json")
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_scorecard.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
