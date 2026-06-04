#!/usr/bin/env python3
"""Tests for peer mesh review bundles."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = REPO_ROOT / "tools" / "peer_mesh_review_bundle.py"


def load_module():
    sys.path.insert(0, str(REVIEW_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_review_bundle", REVIEW_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_review_bundle")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_review_bundle"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_review_bundle = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-review-bundle-manifest.v1",
        "bundle_id": "review-bundle-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:00:15Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "json_artifacts": [
            {
                "artifact_id": "regression_report",
                "path": "regression.json",
                "expected_schema": "quest-termux-lab.peer-scorecard-regression-report.v1",
            }
        ],
        "file_artifacts": [
            {
                "artifact_id": "readme",
                "path": "README.md",
                "artifact_role": "doc",
            }
        ],
        "status_checks": [
            {
                "artifact_id": "regression_report",
                "status_field": "overall_status",
                "accepted_values": ["regression_clear"],
                "manual_review_values": ["manual_review"],
                "blocked_values": ["regression_blocked"],
            }
        ],
        "authority_boundary": ["synthetic review bundle test"],
    }


def regression_payload(status: str = "regression_clear") -> dict:
    return {
        "schema": "quest-termux-lab.peer-scorecard-regression-report.v1",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:00:14Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "overall_status": status,
    }


def write_temp_bundle(root: Path, payload: dict) -> None:
    (root / "regression.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "README.md").write_text("synthetic review doc\n", encoding="utf-8")


class PeerReviewBundleTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-review-bundle-manifest.synthetic.json": "quest-termux-lab.peer-review-bundle-manifest.v1",
            "peer-review-bundle-report.synthetic.json": "quest-termux-lab.peer-review-bundle-report.v1",
            "peer-review-bundle-repeated-scorecard-clear-manifest.synthetic.json": "quest-termux-lab.peer-review-bundle-manifest.v1",
            "peer-review-bundle-repeated-scorecard-clear-report.synthetic.json": "quest-termux-lab.peer-review-bundle-report.v1",
            "peer-review-bundle-preflight-clear-manifest.synthetic.json": "quest-termux-lab.peer-review-bundle-manifest.v1",
            "peer-review-bundle-preflight-clear-report.synthetic.json": "quest-termux-lab.peer-review-bundle-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_review_blocked(self) -> None:
        report = peer_mesh_review_bundle.build_review_bundle_report(
            load_example("peer-review-bundle-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:00:15Z",
        )
        self.assertEqual(report["overall_status"], "review_blocked")
        self.assertGreater(report["summary"]["failed_count"], 0)
        json_artifacts = {entry["artifact_id"]: entry for entry in report["json_artifacts"]}
        file_artifacts = {entry["artifact_id"]: entry for entry in report["file_artifacts"]}
        status_checks = {entry["artifact_id"]: entry for entry in report["status_checks"]}
        self.assertEqual(json_artifacts["topology_report"]["status"], "passed")
        self.assertEqual(status_checks["topology_report"]["observed_value"], "topology_blocked")
        self.assertEqual(status_checks["topology_report"]["status"], "failed")
        self.assertEqual(file_artifacts["topology_tool"]["status"], "passed")
        self.assertEqual(file_artifacts["topology_tests"]["status"], "passed")
        self.assertEqual(file_artifacts["lab_bundle_tool"]["status"], "passed")
        self.assertEqual(file_artifacts["lab_bundle_tests"]["status"], "passed")

    def test_repeated_scorecard_clear_fixture_is_review_ready(self) -> None:
        report = peer_mesh_review_bundle.build_review_bundle_report(
            load_example("peer-review-bundle-repeated-scorecard-clear-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:01:01Z",
        )
        self.assertEqual(report["overall_status"], "review_ready")
        self.assertEqual(report["summary"]["failed_count"], 0)
        self.assertEqual(report["summary"]["manual_review_count"], 0)
        self.assertGreater(report["summary"]["passed_count"], 0)

    def test_preflight_clear_fixture_is_review_ready(self) -> None:
        report = peer_mesh_review_bundle.build_review_bundle_report(
            load_example("peer-review-bundle-preflight-clear-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:01:12Z",
        )
        self.assertEqual(report["overall_status"], "review_ready")
        self.assertEqual(report["summary"]["failed_count"], 0)
        self.assertEqual(report["summary"]["manual_review_count"], 0)
        self.assertGreater(report["summary"]["passed_count"], 0)
        status_checks = {
            (entry["artifact_id"], entry["status_field"]): entry
            for entry in report["status_checks"]
        }
        self.assertEqual(
            status_checks[("preflight_clear_fixture_report", "overall_status")]["observed_value"],
            "fixture_ready",
        )
        self.assertEqual(
            status_checks[("clear_readiness_report", "overall_status")]["observed_value"],
            "ready",
        )
        self.assertEqual(
            status_checks[("clear_topology_report", "overall_status")]["observed_value"],
            "topology_ready",
        )
        self.assertEqual(
            status_checks[("clear_lab_bundle_report", "overall_status")]["observed_value"],
            "synthetic_ready",
        )

    def test_repeated_scorecard_clear_report_example_is_ready(self) -> None:
        report = load_example("peer-review-bundle-repeated-scorecard-clear-report.synthetic.json")
        self.assertEqual(report["overall_status"], "review_ready")
        self.assertEqual(report["summary"]["failed_count"], 0)

    def test_preflight_clear_report_example_is_ready(self) -> None:
        report = load_example("peer-review-bundle-preflight-clear-report.synthetic.json")
        self.assertEqual(report["overall_status"], "review_ready")
        self.assertEqual(report["summary"]["failed_count"], 0)

    def test_clear_bundle_is_review_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_bundle(root, regression_payload("regression_clear"))
            report = peer_mesh_review_bundle.build_review_bundle_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "review_ready")
        self.assertEqual(report["summary"]["failed_count"], 0)

    def test_manual_review_status_surfaces_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_bundle(root, regression_payload("manual_review"))
            report = peer_mesh_review_bundle.build_review_bundle_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "manual_review")
        self.assertEqual(report["summary"]["manual_review_count"], 1)

    def test_blocked_status_blocks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_bundle(root, regression_payload("regression_blocked"))
            report = peer_mesh_review_bundle.build_review_bundle_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "review_blocked")

    def test_missing_file_artifact_blocks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "regression.json").write_text(json.dumps(regression_payload()), encoding="utf-8")
            report = peer_mesh_review_bundle.build_review_bundle_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "review_blocked")
        missing = [entry for entry in report["file_artifacts"] if entry["status"] == "failed"]
        self.assertEqual(missing[0]["artifact_id"], "readme")

    def test_schema_mismatch_blocks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = regression_payload()
            payload["schema"] = "wrong-schema"
            write_temp_bundle(root, payload)
            report = peer_mesh_review_bundle.build_review_bundle_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "review_blocked")
        self.assertIn("schema mismatch", report["json_artifacts"][0]["reason"])

    def test_identity_mismatch_blocks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = regression_payload()
            payload["fleet_id"] = "other-fleet"
            write_temp_bundle(root, payload)
            report = peer_mesh_review_bundle.build_review_bundle_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "review_blocked")
        self.assertIn("fleet_id mismatch", report["json_artifacts"][0]["reason"])

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_review_bundle.validate_manifest(manifest)

    def test_absolute_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["json_artifacts"][0]["path"] = "C:/private/regression.json"
        with self.assertRaises(ValueError):
            peer_mesh_review_bundle.validate_manifest(manifest)

    def test_forbidden_json_artifact_field_blocks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = regression_payload()
            payload["shell"] = "not-public"
            write_temp_bundle(root, payload)
            report = peer_mesh_review_bundle.build_review_bundle_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "review_blocked")
        self.assertIn("credential-like", report["json_artifacts"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
