#!/usr/bin/env python3
"""Tests for peer mesh fixture index reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "tools" / "peer_mesh_fixture_index.py"


def load_module():
    sys.path.insert(0, str(INDEX_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_fixture_index", INDEX_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_fixture_index")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_fixture_index"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_fixture_index = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-fixture-index-manifest.v1",
        "index_id": "fixture-index-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:01:03Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "fixture_groups": [
            {
                "group_id": "ready-group",
                "group_role": "clear_repeated_scorecard",
                "expected_group_status": "ready",
                "artifact_refs": [
                    {
                        "artifact_id": "ready_doc",
                        "path": "ready.json",
                        "expected_schema": "example.ready.v1",
                    }
                ],
                "status_checks": [
                    {
                        "artifact_id": "ready_doc",
                        "status_field": "overall_status",
                        "accepted_values": ["ready"],
                        "manual_review_values": ["manual_review"],
                        "blocked_values": ["blocked"],
                    }
                ],
                "reason": "ready fixture",
            }
        ],
        "authority_boundary": ["synthetic fixture index boundary"],
    }


def write_ready_doc(root: Path, status: str = "ready") -> None:
    (root / "ready.json").write_text(
        json.dumps(
            {
                "schema": "example.ready.v1",
                "fleet_id": "synthetic-lab-fleet",
                "source_agent_id": "quest-agent-alpha",
                "experiment_scope": "private_configured_peer_gossip_only",
                "overall_status": status,
            }
        ),
        encoding="utf-8",
    )


class PeerFixtureIndexTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-fixture-index-manifest.synthetic.json": "quest-termux-lab.peer-fixture-index-manifest.v1",
            "peer-fixture-index-report.synthetic.json": "quest-termux-lab.peer-fixture-index-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_index_is_ready_with_expected_blocked_lanes(self) -> None:
        report = peer_mesh_fixture_index.build_fixture_index_report(
            load_example("peer-fixture-index-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:01:03Z",
        )
        self.assertEqual(report["overall_status"], "fixture_index_ready")
        self.assertEqual(report["summary"]["expectation_failed_count"], 0)
        groups = {group["group_id"]: group for group in report["fixture_groups"]}
        self.assertEqual(groups["blocked-public-baseline"]["observed_group_status"], "blocked")
        self.assertEqual(groups["clear-repeated-scorecard-fixture"]["observed_group_status"], "ready")
        self.assertEqual(groups["clear-preflight-fixture"]["observed_group_status"], "ready")
        self.assertEqual(groups["cleanup-plan-fixture"]["observed_group_status"], "ready")
        self.assertEqual(groups["file-drop-staging-fixture"]["observed_group_status"], "ready")
        self.assertEqual(groups["file-drop-copy-dry-run-fixture"]["observed_group_status"], "ready")
        self.assertEqual(groups["file-drop-inbox-intake-fixture"]["observed_group_status"], "ready")
        self.assertEqual(groups["private-handoff-placeholders"]["observed_group_status"], "blocked")
        preflight_group = groups["clear-preflight-fixture"]
        preflight_artifacts = {entry["artifact_id"]: entry for entry in preflight_group["artifacts"]}
        preflight_statuses = {
            (entry["artifact_id"], entry["status_field"]): entry
            for entry in preflight_group["status_checks"]
        }
        self.assertEqual(preflight_artifacts["preflight_clear_review_bundle"]["status"], "passed")
        self.assertEqual(
            preflight_statuses[("preflight_clear_review_bundle", "overall_status")]["observed_value"],
            "review_ready",
        )
        cleanup_group = groups["cleanup-plan-fixture"]
        cleanup_statuses = {
            (entry["artifact_id"], entry["status_field"]): entry
            for entry in cleanup_group["status_checks"]
        }
        self.assertEqual(
            cleanup_statuses[("cleanup_plan_report", "overall_status")]["observed_value"],
            "cleanup_plan_ready",
        )
        staging_group = groups["file-drop-staging-fixture"]
        staging_statuses = {
            (entry["artifact_id"], entry["status_field"]): entry
            for entry in staging_group["status_checks"]
        }
        self.assertEqual(
            staging_statuses[("file_drop_staging_report", "overall_status")]["observed_value"],
            "file_drop_staging_ready",
        )
        copy_group = groups["file-drop-copy-dry-run-fixture"]
        copy_statuses = {
            (entry["artifact_id"], entry["status_field"]): entry
            for entry in copy_group["status_checks"]
        }
        self.assertEqual(
            copy_statuses[("file_drop_copy_dry_run_report", "overall_status")]["observed_value"],
            "file_drop_copy_dry_run_ready",
        )
        intake_group = groups["file-drop-inbox-intake-fixture"]
        intake_statuses = {
            (entry["artifact_id"], entry["status_field"]): entry
            for entry in intake_group["status_checks"]
        }
        self.assertEqual(
            intake_statuses[("file_drop_inbox_intake_report", "overall_status")]["observed_value"],
            "file_drop_inbox_intake_ready",
        )

    def test_ready_group_passes_when_expected_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_doc(root, "ready")
            report = peer_mesh_fixture_index.build_fixture_index_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "fixture_index_ready")
        self.assertEqual(report["fixture_groups"][0]["expectation_status"], "passed")

    def test_unexpected_group_status_blocks_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_doc(root, "blocked")
            report = peer_mesh_fixture_index.build_fixture_index_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "fixture_index_blocked")
        self.assertEqual(report["fixture_groups"][0]["observed_group_status"], "blocked")
        self.assertEqual(report["fixture_groups"][0]["expectation_status"], "failed")

    def test_missing_artifact_blocks_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = peer_mesh_fixture_index.build_fixture_index_report(minimal_manifest(), Path(tmp))
        self.assertEqual(report["overall_status"], "fixture_index_blocked")
        self.assertEqual(report["summary"]["artifact_failed_count"], 1)

    def test_identity_mismatch_blocks_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_doc(root, "ready")
            data = json.loads((root / "ready.json").read_text(encoding="utf-8"))
            data["fleet_id"] = "other-fleet"
            (root / "ready.json").write_text(json.dumps(data), encoding="utf-8")
            report = peer_mesh_fixture_index.build_fixture_index_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "fixture_index_blocked")
        self.assertIn("fleet_id mismatch", report["fixture_groups"][0]["artifacts"][0]["reason"])

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_fixture_index.validate_manifest(manifest)

    def test_absolute_artifact_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["fixture_groups"][0]["artifact_refs"][0]["path"] = "C:/private/ready.json"
        with self.assertRaises(ValueError):
            peer_mesh_fixture_index.validate_manifest(manifest)

    def test_forbidden_artifact_field_blocks_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_ready_doc(root, "ready")
            data = json.loads((root / "ready.json").read_text(encoding="utf-8"))
            data["token"] = "not-public"
            (root / "ready.json").write_text(json.dumps(data), encoding="utf-8")
            report = peer_mesh_fixture_index.build_fixture_index_report(minimal_manifest(), root)
        self.assertEqual(report["overall_status"], "fixture_index_blocked")
        self.assertIn("credential-like", report["fixture_groups"][0]["artifacts"][0]["reason"])

    def test_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = minimal_manifest()
            write_ready_doc(root, "ready")
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            exit_code = peer_mesh_fixture_index.main(
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
        self.assertEqual(report["overall_status"], "fixture_index_ready")


if __name__ == "__main__":
    unittest.main()
