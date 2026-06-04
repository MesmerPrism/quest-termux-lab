#!/usr/bin/env python3
"""Tests for peer mesh public package readiness reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = REPO_ROOT / "tools" / "peer_mesh_public_package.py"


def load_module():
    sys.path.insert(0, str(PACKAGE_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_public_package", PACKAGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_public_package")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_public_package"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_public_package = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-public-package-manifest.v1",
        "package_index_id": "package-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:03:04Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "required_file_refs": [
            {
                "file_id": "doc",
                "file_role": "doc",
                "path": "doc.md",
                "reason": "doc exists",
            }
        ],
        "status_expectations": [
            {
                "expectation_id": "status_ready",
                "path": "status.json",
                "expected_schema": "example.status.v1",
                "status_field": "overall_status",
                "expected_status_class": "ready",
                "ready_values": ["ready"],
                "manual_review_values": ["manual_review"],
                "blocked_values": ["blocked"],
                "reason": "status should be ready",
            }
        ],
        "declared_validation_slots": [
            {
                "validation_id": "unit_tests",
                "observed_status": "passed",
                "evidence_note": "synthetic validation passed",
                "reason": "tests pass",
            }
        ],
        "authority_boundary": ["synthetic package boundary"],
    }


def write_temp_artifacts(root: Path, status: str = "ready") -> None:
    (root / "doc.md").write_text("# doc\n", encoding="utf-8")
    (root / "status.json").write_text(
        json.dumps(
            {
                "schema": "example.status.v1",
                "fleet_id": "synthetic-lab-fleet",
                "source_agent_id": "quest-agent-alpha",
                "experiment_scope": "private_configured_peer_gossip_only",
                "overall_status": status,
            }
        ),
        encoding="utf-8",
    )


class PeerPublicPackageTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-public-package-manifest.synthetic.json": "quest-termux-lab.peer-public-package-manifest.v1",
            "peer-public-package-report.synthetic.json": "quest-termux-lab.peer-public-package-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_package_fixture_is_ready_for_public_review(self) -> None:
        report = peer_mesh_public_package.build_package_report(
            load_example("peer-public-package-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:03:04Z",
        )
        self.assertEqual(report["overall_status"], "package_ready")
        self.assertEqual(report["summary"]["missing_file_count"], 0)
        self.assertEqual(report["summary"]["status_expectation_failed_count"], 0)
        self.assertEqual(report["summary"]["declared_validation_failed_count"], 0)
        required_files = {entry["file_id"]: entry for entry in report["required_files"]}
        expectations = {entry["expectation_id"]: entry for entry in report["status_expectations"]}
        self.assertEqual(required_files["route_health_tool"]["status"], "passed")
        self.assertEqual(required_files["route_health_tests"]["status"], "passed")
        self.assertEqual(required_files["route_history_tool"]["status"], "passed")
        self.assertEqual(required_files["route_history_tests"]["status"], "passed")
        self.assertEqual(required_files["live_lab_readiness_tool"]["status"], "passed")
        self.assertEqual(required_files["live_lab_readiness_tests"]["status"], "passed")
        self.assertEqual(required_files["topology_tool"]["status"], "passed")
        self.assertEqual(required_files["topology_tests"]["status"], "passed")
        self.assertEqual(required_files["lab_bundle_tool"]["status"], "passed")
        self.assertEqual(required_files["lab_bundle_tests"]["status"], "passed")
        self.assertEqual(required_files["preflight_clear_fixture_tool"]["status"], "passed")
        self.assertEqual(required_files["preflight_clear_fixture_tests"]["status"], "passed")
        self.assertEqual(required_files["preflight_clear_readiness_report"]["status"], "passed")
        self.assertEqual(required_files["preflight_clear_topology_report"]["status"], "passed")
        self.assertEqual(required_files["preflight_clear_lab_bundle_report"]["status"], "passed")
        self.assertEqual(required_files["preflight_clear_review_bundle_manifest"]["status"], "passed")
        self.assertEqual(required_files["preflight_clear_review_bundle_report"]["status"], "passed")
        self.assertEqual(required_files["cleanup_plan_tool"]["status"], "passed")
        self.assertEqual(required_files["cleanup_plan_tests"]["status"], "passed")
        self.assertEqual(required_files["cleanup_plan_manifest_schema"]["status"], "passed")
        self.assertEqual(required_files["cleanup_plan_report_schema"]["status"], "passed")
        self.assertEqual(required_files["cleanup_plan_manifest_example"]["status"], "passed")
        self.assertEqual(required_files["cleanup_plan_report_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_staging_tool"]["status"], "passed")
        self.assertEqual(required_files["file_drop_staging_tests"]["status"], "passed")
        self.assertEqual(required_files["file_drop_staging_manifest_schema"]["status"], "passed")
        self.assertEqual(required_files["file_drop_staging_report_schema"]["status"], "passed")
        self.assertEqual(required_files["file_drop_delivery_state_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_staging_manifest_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_staging_report_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_copy_dry_run_tool"]["status"], "passed")
        self.assertEqual(required_files["file_drop_copy_dry_run_tests"]["status"], "passed")
        self.assertEqual(required_files["file_drop_copy_outcomes_schema"]["status"], "passed")
        self.assertEqual(required_files["file_drop_copy_dry_run_report_schema"]["status"], "passed")
        self.assertEqual(required_files["file_drop_copy_outcomes_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_copy_dry_run_report_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_inbox_intake_tool"]["status"], "passed")
        self.assertEqual(required_files["file_drop_inbox_intake_tests"]["status"], "passed")
        self.assertEqual(required_files["file_drop_inbox_intake_manifest_schema"]["status"], "passed")
        self.assertEqual(required_files["file_drop_inbox_intake_report_schema"]["status"], "passed")
        self.assertEqual(required_files["file_drop_inbox_intake_manifest_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_inbox_intake_envelope_example"]["status"], "passed")
        self.assertEqual(required_files["file_drop_inbox_intake_report_example"]["status"], "passed")
        self.assertEqual(expectations["route_health_unknown_baseline"]["observed_status_class"], "blocked")
        self.assertEqual(expectations["route_history_unknown_baseline"]["observed_status_class"], "blocked")
        self.assertEqual(expectations["live_lab_readiness_not_ready"]["observed_status_class"], "blocked")
        self.assertEqual(expectations["topology_baseline_blocked"]["observed_status_class"], "blocked")
        self.assertEqual(expectations["topology_aware_lab_bundle_blocked"]["observed_status_class"], "blocked")
        self.assertEqual(expectations["clear_preflight_fixture_ready"]["observed_status_class"], "ready")
        self.assertEqual(expectations["preflight_clear_review_bundle_ready"]["observed_status_class"], "ready")
        self.assertEqual(expectations["cleanup_plan_ready"]["observed_status_class"], "ready")
        self.assertEqual(expectations["file_drop_staging_ready"]["observed_status_class"], "ready")
        self.assertEqual(expectations["file_drop_copy_dry_run_ready"]["observed_status_class"], "ready")
        self.assertEqual(expectations["file_drop_inbox_intake_ready"]["observed_status_class"], "ready")
        self.assertEqual(expectations["private_evidence_redaction_blocked"]["observed_status_class"], "blocked")
        self.assertEqual(expectations["fixture_index_ready"]["observed_status_class"], "ready")

    def test_minimal_ready_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_artifacts(root, "ready")
            report = peer_mesh_public_package.build_package_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "package_ready")

    def test_missing_required_file_blocks_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_artifacts(root, "ready")
            (root / "doc.md").unlink()
            report = peer_mesh_public_package.build_package_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "package_blocked")
        self.assertEqual(report["summary"]["missing_file_count"], 1)

    def test_unexpected_status_class_blocks_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_artifacts(root, "blocked")
            report = peer_mesh_public_package.build_package_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "package_blocked")
        self.assertEqual(report["summary"]["status_expectation_failed_count"], 1)

    def test_manual_validation_yields_manual_review(self) -> None:
        manifest = minimal_manifest()
        manifest["declared_validation_slots"][0]["observed_status"] = "manual_review"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_artifacts(root, "ready")
            report = peer_mesh_public_package.build_package_report(manifest, root)
        self.assertEqual(report["overall_status"], "manual_review")

    def test_not_run_validation_blocks_package(self) -> None:
        manifest = minimal_manifest()
        manifest["declared_validation_slots"][0]["observed_status"] = "not_run"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_artifacts(root, "ready")
            report = peer_mesh_public_package.build_package_report(manifest, root)
        self.assertEqual(report["overall_status"], "package_blocked")

    def test_identity_mismatch_blocks_status_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_artifacts(root, "ready")
            data = json.loads((root / "status.json").read_text(encoding="utf-8"))
            data["fleet_id"] = "other-fleet"
            (root / "status.json").write_text(json.dumps(data), encoding="utf-8")
            report = peer_mesh_public_package.build_package_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "package_blocked")
        self.assertIn("fleet_id mismatch", report["status_expectations"][0]["reason"])

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_public_package.validate_manifest(manifest)

    def test_absolute_file_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["required_file_refs"][0]["path"] = "C:/private/doc.md"
        with self.assertRaises(ValueError):
            peer_mesh_public_package.validate_manifest(manifest)

    def test_forbidden_status_artifact_field_blocks_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_temp_artifacts(root, "ready")
            data = json.loads((root / "status.json").read_text(encoding="utf-8"))
            data["shell"] = "not-public"
            (root / "status.json").write_text(json.dumps(data), encoding="utf-8")
            report = peer_mesh_public_package.build_package_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "package_blocked")
        self.assertIn("credential-like", report["status_expectations"][0]["reason"])

    def test_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = minimal_manifest()
            write_temp_artifacts(root, "ready")
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            exit_code = peer_mesh_public_package.main(
                [
                    "--manifest",
                    str(manifest_path),
                    "--artifact-root",
                    str(root),
                    "--output",
                    str(report_path),
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "package_ready")


if __name__ == "__main__":
    unittest.main()
