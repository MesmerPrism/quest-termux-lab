#!/usr/bin/env python3
"""Tests for peer mesh cleanup plan reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLEANUP_PLAN_PATH = REPO_ROOT / "tools" / "peer_mesh_cleanup_plan.py"


def load_module():
    sys.path.insert(0, str(CLEANUP_PLAN_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_cleanup_plan", CLEANUP_PLAN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_cleanup_plan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_cleanup_plan"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_cleanup_plan = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-cleanup-plan-manifest.v1",
        "cleanup_plan_id": "cleanup-plan-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:01:20Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "cleanup_steps": [
            {
                "step_id": "operator-review",
                "cleanup_kind": "operator_review",
                "timing": "pre_run",
                "required": True,
                "expected_evidence_kind": "cleanup_record",
                "reason": "operator cleanup review slot exists",
            },
            {
                "step_id": "transport-stopped",
                "cleanup_kind": "confirm_peer_transport_stopped",
                "timing": "post_run",
                "required": True,
                "expected_evidence_kind": "cleanup_record",
                "reason": "transport stop evidence slot exists",
            },
            {
                "step_id": "inbox-clear",
                "cleanup_kind": "clear_ephemeral_inbox",
                "timing": "post_run",
                "required": True,
                "expected_evidence_kind": "cleanup_record",
                "reason": "inbox cleanup evidence slot exists",
            },
            {
                "step_id": "outbox-clear",
                "cleanup_kind": "clear_ephemeral_outbox",
                "timing": "post_run",
                "required": True,
                "expected_evidence_kind": "cleanup_record",
                "reason": "outbox cleanup evidence slot exists",
            },
            {
                "step_id": "cleanup-record",
                "cleanup_kind": "record_cleanup_record",
                "timing": "final_review",
                "required": True,
                "expected_evidence_kind": "cleanup_record",
                "reason": "cleanup record slot exists",
            },
        ],
        "authority_boundary": ["synthetic cleanup plan boundary"],
    }


class PeerCleanupPlanTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-cleanup-plan-manifest.synthetic.json": "quest-termux-lab.peer-cleanup-plan-manifest.v1",
            "peer-cleanup-plan-report.synthetic.json": "quest-termux-lab.peer-cleanup-plan-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_ready(self) -> None:
        report = peer_mesh_cleanup_plan.build_cleanup_plan_report(
            load_example("peer-cleanup-plan-manifest.synthetic.json"),
            now_text="2026-06-04T10:01:20Z",
        )
        self.assertEqual(report["overall_status"], "cleanup_plan_ready")
        self.assertEqual(report["summary"]["missing_required_cleanup_kind_count"], 0)
        self.assertEqual(report["summary"]["missing_step_count"], 0)
        self.assertEqual(report["summary"]["observed_required_cleanup_kind_count"], 5)

    def test_minimal_ready_manifest_passes(self) -> None:
        report = peer_mesh_cleanup_plan.build_cleanup_plan_report(minimal_manifest())
        self.assertEqual(report["overall_status"], "cleanup_plan_ready")

    def test_missing_required_cleanup_kind_blocks_plan(self) -> None:
        manifest = minimal_manifest()
        manifest["cleanup_steps"] = [
            step for step in manifest["cleanup_steps"]
            if step["cleanup_kind"] != "clear_ephemeral_outbox"
        ]
        report = peer_mesh_cleanup_plan.build_cleanup_plan_report(manifest)
        self.assertEqual(report["overall_status"], "cleanup_plan_blocked")
        missing = [entry for entry in report["cleanup_steps"] if entry["status"] == "missing"]
        self.assertEqual(missing[0]["cleanup_kind"], "clear_ephemeral_outbox")

    def test_optional_steps_do_not_satisfy_required_categories(self) -> None:
        manifest = minimal_manifest()
        for step in manifest["cleanup_steps"]:
            if step["cleanup_kind"] == "record_cleanup_record":
                step["required"] = False
        report = peer_mesh_cleanup_plan.build_cleanup_plan_report(manifest)
        self.assertEqual(report["overall_status"], "cleanup_plan_blocked")

    def test_duplicate_step_id_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["cleanup_steps"][1]["step_id"] = manifest["cleanup_steps"][0]["step_id"]
        with self.assertRaises(ValueError):
            peer_mesh_cleanup_plan.validate_manifest(manifest)

    def test_unsupported_cleanup_kind_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["cleanup_steps"][0]["cleanup_kind"] = "wipe_device"
        with self.assertRaises(ValueError):
            peer_mesh_cleanup_plan.validate_manifest(manifest)

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_cleanup_plan.validate_manifest(manifest)

    def test_forbidden_step_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["cleanup_steps"][0]["adb_target"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_cleanup_plan.validate_manifest(manifest)

    def test_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            manifest_path.write_text(json.dumps(minimal_manifest()), encoding="utf-8")
            exit_code = peer_mesh_cleanup_plan.main(
                [
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(report_path),
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "cleanup_plan_ready")


if __name__ == "__main__":
    unittest.main()
