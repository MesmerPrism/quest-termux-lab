#!/usr/bin/env python3
"""Tests for private result placeholder reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_PATH = REPO_ROOT / "tools" / "peer_mesh_private_result_placeholder.py"


def load_module():
    sys.path.insert(0, str(PLACEHOLDER_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_private_result_placeholder", PLACEHOLDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_private_result_placeholder")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_private_result_placeholder"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_private_result_placeholder = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return copy.deepcopy(load_example("peer-private-result-placeholder-manifest.synthetic.json"))


def ready_import(status: str = "import_ready") -> dict:
    report = copy.deepcopy(load_example("peer-private-import-plan-report.synthetic.json"))
    report["overall_status"] = status
    for check in report["checks"]:
        check["status"] = "passed"
        if check["check_id"] == "redaction_status":
            check["observed"] = "redaction_ready" if status == "import_ready" else "manual_review"
            check["reason"] = "redaction plan is ready for sanitized derivative import"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["passed_check_count"] = report["summary"]["check_count"]
    for item in report["import_items"]:
        if item["public_release"] == "sanitized_derivative_only":
            item["import_status"] = "ready_for_public_derivative" if status == "import_ready" else "blocked_until_redaction_ready"
    if status == "manual_review":
        report["checks"][3]["status"] = "manual_review"
        report["summary"]["manual_review_check_count"] = 1
        report["summary"]["passed_check_count"] -= 1
    return report


class PeerPrivateResultPlaceholderTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-private-result-placeholder-manifest.synthetic.json": "quest-termux-lab.peer-private-result-placeholder-manifest.v1",
            "peer-private-result-placeholder-report.synthetic.json": "quest-termux-lab.peer-private-result-placeholder-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked_by_import_plan(self) -> None:
        report = peer_mesh_private_result_placeholder.build_placeholder_report(
            load_example("peer-private-result-placeholder-manifest.synthetic.json"),
            load_example("peer-private-import-plan-report.synthetic.json"),
            now_text="2026-06-04T10:05:06Z",
        )
        self.assertEqual(report["overall_status"], "result_placeholders_blocked")
        self.assertEqual(report["import_plan_status"], "import_blocked")
        self.assertEqual(report["summary"]["private_only_slot_count"], 2)
        self.assertEqual(report["summary"]["blocked_slot_count"], 5)

    def test_ready_import_plan_creates_ready_placeholders(self) -> None:
        report = peer_mesh_private_result_placeholder.build_placeholder_report(
            minimal_manifest(),
            ready_import("import_ready"),
        )
        self.assertEqual(report["overall_status"], "result_placeholders_ready")
        self.assertEqual(report["summary"]["awaiting_derivative_slot_count"], 5)
        self.assertEqual(report["summary"]["private_only_slot_count"], 2)
        self.assertEqual(report["summary"]["blocked_slot_count"], 0)

    def test_manual_import_can_remain_manual_when_not_required_ready(self) -> None:
        manifest = minimal_manifest()
        manifest["require_import_ready"] = False
        report = peer_mesh_private_result_placeholder.build_placeholder_report(
            manifest,
            ready_import("manual_review"),
        )
        self.assertEqual(report["overall_status"], "manual_review")

    def test_missing_derivative_schema_blocks_placeholders(self) -> None:
        import_report = ready_import("import_ready")
        for item in import_report["import_items"]:
            if item["public_release"] == "sanitized_derivative_only":
                item["public_derivative_schema"] = ""
                item["import_status"] = "missing_derivative_schema"
                break
        report = peer_mesh_private_result_placeholder.build_placeholder_report(minimal_manifest(), import_report)
        self.assertEqual(report["overall_status"], "result_placeholders_blocked")
        self.assertEqual(report["summary"]["blocked_slot_count"], 1)

    def test_identity_mismatch_blocks_placeholders(self) -> None:
        import_report = ready_import("import_ready")
        import_report["fleet_id"] = "other-fleet"
        report = peer_mesh_private_result_placeholder.build_placeholder_report(minimal_manifest(), import_report)
        self.assertEqual(report["overall_status"], "result_placeholders_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["import_plan_identity"], "failed")

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_result_placeholder.validate_manifest(manifest)

    def test_absolute_import_plan_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["import_plan_report_path"] = "C:/private/import-plan.json"
        with self.assertRaises(ValueError):
            peer_mesh_private_result_placeholder.validate_manifest(manifest)

    def test_forbidden_import_report_field_is_rejected(self) -> None:
        import_report = ready_import("import_ready")
        import_report["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_result_placeholder.validate_import_plan_report(import_report)

    def test_cli_writes_report(self) -> None:
        report_path = REPO_ROOT / "examples" / "peer-private-result-placeholder-report.synthetic.json"
        exit_code = peer_mesh_private_result_placeholder.main(
            [
                "--manifest",
                str(REPO_ROOT / "examples" / "peer-private-result-placeholder-manifest.synthetic.json"),
                "--artifact-root",
                str(REPO_ROOT),
                "--now",
                "2026-06-04T10:05:06Z",
                "--output",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "result_placeholders_blocked")


if __name__ == "__main__":
    unittest.main()
