#!/usr/bin/env python3
"""Tests for peer live-run rehearsal reports."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REHEARSAL_PATH = REPO_ROOT / "tools" / "peer_mesh_rehearsal.py"


def load_module():
    sys.path.insert(0, str(REHEARSAL_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_rehearsal", REHEARSAL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_rehearsal"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_rehearsal = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def ready_bundle() -> dict:
    bundle = load_example("peer-lab-bundle-report.synthetic.json")
    bundle["overall_status"] = "synthetic_ready"
    bundle["readiness_status"] = "ready"
    bundle["operator_approval_required"] = False
    bundle["operator_approval_recorded"] = False
    bundle["summary"]["ready_route_count"] = 2
    bundle["summary"]["not_ready_route_count"] = 0
    return bundle


def trusted_report(status: str = "trusted") -> dict:
    trust = load_example("peer-trust-report.synthetic.json")
    trust["overall_status"] = status
    trust["checks"][2]["status"] = "passed"
    trust["checks"][2]["observed"] = "synthetic_ready"
    trust["checks"][2]["reason"] = "bundle preflight is synthetically ready"
    trust["summary"]["failed_check_count"] = 0
    trust["summary"]["passed_check_count"] = 8
    if status == "trusted":
        trust["summary"]["manual_review_check_count"] = 0
    return trust


class PeerMeshRehearsalTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-rehearsal-manifest.synthetic.json": "quest-termux-lab.peer-rehearsal-manifest.v1",
            "peer-rehearsal-report.synthetic.json": "quest-termux-lab.peer-rehearsal-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked_by_bundle_and_trust(self) -> None:
        report = peer_mesh_rehearsal.build_rehearsal_report(
            load_example("peer-rehearsal-manifest.synthetic.json"),
            load_example("peer-lab-bundle-report.synthetic.json"),
            load_example("peer-trust-report.synthetic.json"),
            now_text="2026-06-04T10:00:10Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        failed = [check["check_id"] for check in report["checks"] if check["status"] == "failed"]
        self.assertIn("lab_bundle_status", failed)
        self.assertIn("trust_status", failed)

    def test_rehearsal_ready_when_preflight_is_ready_and_operator_not_required(self) -> None:
        manifest = load_example("peer-rehearsal-manifest.synthetic.json")
        manifest["operator_review_required"] = False
        manifest["operator_review_recorded"] = False
        report = peer_mesh_rehearsal.build_rehearsal_report(
            manifest,
            ready_bundle(),
            trusted_report(),
            now_text="2026-06-04T10:00:10Z",
        )
        self.assertEqual(report["overall_status"], "rehearsal_ready")
        self.assertGreater(report["summary"]["private_only_phase_count"], 0)

    def test_operator_review_forces_manual_review_after_ready_preflight(self) -> None:
        report = peer_mesh_rehearsal.build_rehearsal_report(
            load_example("peer-rehearsal-manifest.synthetic.json"),
            ready_bundle(),
            trusted_report(),
            now_text="2026-06-04T10:00:10Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        manual = [check["check_id"] for check in report["checks"] if check["status"] == "manual_review"]
        self.assertEqual(manual, ["operator_review"])

    def test_manual_trust_status_can_force_manual_review(self) -> None:
        manifest = load_example("peer-rehearsal-manifest.synthetic.json")
        manifest["required_trust_statuses"] = ["trusted", "manual_review"]
        manifest["operator_review_required"] = False
        report = peer_mesh_rehearsal.build_rehearsal_report(
            manifest,
            ready_bundle(),
            trusted_report(status="manual_review"),
            now_text="2026-06-04T10:00:10Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")

    def test_trust_fleet_mismatch_blocks_report(self) -> None:
        trust = trusted_report()
        trust["fleet_id"] = "other-fleet"
        report = peer_mesh_rehearsal.build_rehearsal_report(
            load_example("peer-rehearsal-manifest.synthetic.json"),
            ready_bundle(),
            trust,
            now_text="2026-06-04T10:00:10Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        failed = [check["check_id"] for check in report["checks"] if check["status"] == "failed"]
        self.assertIn("trust_report_valid", failed)

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = load_example("peer-rehearsal-manifest.synthetic.json")
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_rehearsal.validate_manifest(manifest)

    def test_invalid_phase_kind_is_rejected(self) -> None:
        manifest = load_example("peer-rehearsal-manifest.synthetic.json")
        manifest["planned_phases"][0]["evidence_kind"] = "live_socket_probe"
        with self.assertRaises(ValueError):
            peer_mesh_rehearsal.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
