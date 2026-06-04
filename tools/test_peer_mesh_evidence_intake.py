#!/usr/bin/env python3
"""Tests for peer evidence intake reports."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INTAKE_PATH = REPO_ROOT / "tools" / "peer_mesh_evidence_intake.py"


def load_module():
    sys.path.insert(0, str(INTAKE_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_evidence_intake", INTAKE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_evidence_intake")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_evidence_intake"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_evidence_intake = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def ready_rehearsal() -> dict:
    report = load_example("peer-rehearsal-report.synthetic.json")
    report["overall_status"] = "rehearsal_ready"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["blocked_phase_count"] = 0
    report["summary"]["manual_review_phase_count"] = 0
    for check in report["checks"]:
        check["status"] = "passed"
        if check["check_id"] == "lab_bundle_status":
            check["observed"] = "synthetic_ready"
        if check["check_id"] == "trust_status":
            check["observed"] = "trusted"
        if check["check_id"] == "operator_review":
            check["observed"] = "recorded flag true"
    for phase in report["phases"]:
        if phase["status"] in {"blocked", "manual_review"}:
            phase["status"] = "ready"
    return report


def trusted_report() -> dict:
    report = load_example("peer-trust-report.synthetic.json")
    report["overall_status"] = "trusted"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    for check in report["checks"]:
        if check["status"] in {"failed", "manual_review"}:
            check["status"] = "passed"
            if check["check_id"] == "lab_bundle_status":
                check["observed"] = "synthetic_ready"
            if check["check_id"] == "operator_review":
                check["observed"] = "recorded flag true"
    return report


def healthy_route_health() -> dict:
    report = load_example("peer-route-health-report.synthetic.json")
    report["routes"][1]["status"] = "healthy"
    report["routes"][1]["reason"] = "synthetic delivery accepted"
    report["summary"]["healthy_count"] = 2
    report["summary"]["unknown_count"] = 0
    return report


def healthy_route_history() -> dict:
    report = load_example("peer-route-health-history.synthetic.json")
    for route in report["routes"]:
        route["last_status"] = "healthy"
        route["first_status"] = "healthy"
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
    report["summary"]["stable_count"] = 2
    report["summary"]["single_sample_count"] = 0
    return report


def completed_cleanup() -> dict:
    record = load_example("peer-cleanup-record.synthetic.json")
    record["cleanup_status"] = "completed"
    return record


def ready_artifacts() -> dict[str, list[dict]]:
    return {
        "rehearsal_report": [ready_rehearsal()],
        "trust_report": [trusted_report()],
        "gossip_receipt": [load_example("peer-http-gossip-receipt.synthetic.json")],
        "route_health_report": [healthy_route_health()],
        "route_history_report": [healthy_route_history()],
        "cleanup_record": [completed_cleanup()],
    }


class PeerEvidenceIntakeTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-evidence-intake-manifest.synthetic.json": "quest-termux-lab.peer-evidence-intake-manifest.v1",
            "peer-evidence-intake-report.synthetic.json": "quest-termux-lab.peer-evidence-intake-report.v1",
            "peer-cleanup-record.synthetic.json": "quest-termux-lab.peer-cleanup-record.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_rejected_by_blocked_preflight(self) -> None:
        report = peer_mesh_evidence_intake.build_evidence_report(
            load_example("peer-evidence-intake-manifest.synthetic.json"),
            {
                "rehearsal_report": [load_example("peer-rehearsal-report.synthetic.json")],
                "trust_report": [load_example("peer-trust-report.synthetic.json")],
                "gossip_receipt": [load_example("peer-http-gossip-receipt.synthetic.json")],
                "route_health_report": [load_example("peer-route-health-report.synthetic.json")],
                "route_history_report": [load_example("peer-route-health-history.synthetic.json")],
                "cleanup_record": [load_example("peer-cleanup-record.synthetic.json")],
            },
            now_text="2026-06-04T10:00:11Z",
        )
        self.assertEqual(report["overall_status"], "rejected")
        rejected = [entry["artifact_kind"] for entry in report["artifacts"] if entry["status"] == "rejected"]
        self.assertIn("rehearsal_report", rejected)
        self.assertIn("trust_report", rejected)

    def test_ready_artifacts_are_accepted(self) -> None:
        report = peer_mesh_evidence_intake.build_evidence_report(
            load_example("peer-evidence-intake-manifest.synthetic.json"),
            ready_artifacts(),
            now_text="2026-06-04T10:00:11Z",
        )
        self.assertEqual(report["overall_status"], "accepted")

    def test_unknown_route_health_forces_manual_review(self) -> None:
        artifacts = ready_artifacts()
        artifacts["route_health_report"] = [load_example("peer-route-health-report.synthetic.json")]
        report = peer_mesh_evidence_intake.build_evidence_report(
            load_example("peer-evidence-intake-manifest.synthetic.json"),
            artifacts,
            now_text="2026-06-04T10:00:11Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        manual = [entry["artifact_kind"] for entry in report["artifacts"] if entry["status"] == "manual_review"]
        self.assertIn("route_health_report", manual)

    def test_missing_required_receipt_rejects_report(self) -> None:
        artifacts = ready_artifacts()
        artifacts["gossip_receipt"] = []
        report = peer_mesh_evidence_intake.build_evidence_report(
            load_example("peer-evidence-intake-manifest.synthetic.json"),
            artifacts,
            now_text="2026-06-04T10:00:11Z",
        )
        self.assertEqual(report["overall_status"], "rejected")
        missing = [entry["artifact_kind"] for entry in report["artifacts"] if entry["status"] == "missing"]
        self.assertIn("gossip_receipt", missing)

    def test_fleet_mismatch_rejects_artifact(self) -> None:
        artifacts = ready_artifacts()
        artifacts["route_history_report"][0]["fleet_id"] = "other-fleet"
        report = peer_mesh_evidence_intake.build_evidence_report(
            load_example("peer-evidence-intake-manifest.synthetic.json"),
            artifacts,
            now_text="2026-06-04T10:00:11Z",
        )
        self.assertEqual(report["overall_status"], "rejected")

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = load_example("peer-evidence-intake-manifest.synthetic.json")
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_evidence_intake.validate_manifest(manifest)

    def test_cli_loads_manifest_paths(self) -> None:
        manifest = load_example("peer-evidence-intake-manifest.synthetic.json")
        artifacts = peer_mesh_evidence_intake.load_artifacts_from_manifest(manifest, REPO_ROOT)
        self.assertIn("gossip_receipt", artifacts)
        self.assertEqual(artifacts["gossip_receipt"][0]["schema"], "quest-termux-lab.peer-http-gossip-receipt.v1")


if __name__ == "__main__":
    unittest.main()
