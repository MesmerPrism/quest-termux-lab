#!/usr/bin/env python3
"""Tests for private evidence import plan reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
IMPORT_PATH = REPO_ROOT / "tools" / "peer_mesh_private_import_plan.py"


def load_module():
    sys.path.insert(0, str(IMPORT_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_private_import_plan", IMPORT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_private_import_plan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_private_import_plan"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_private_import_plan = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return copy.deepcopy(load_example("peer-private-import-plan-manifest.synthetic.json"))


def ready_package(status: str = "package_ready") -> dict:
    report = copy.deepcopy(load_example("peer-public-package-report.synthetic.json"))
    report["overall_status"] = status
    return report


def ready_redaction(status: str = "redaction_ready") -> dict:
    report = copy.deepcopy(load_example("peer-private-evidence-redaction-report.synthetic.json"))
    report["overall_status"] = status
    for check in report["checks"]:
        check["status"] = "passed"
        if check["check_id"] == "checklist_status":
            check["observed"] = "checklist_ready" if status == "redaction_ready" else "manual_review"
            check["reason"] = "checklist is ready for redaction planning"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["passed_check_count"] = report["summary"]["check_count"]
    for item in report["redaction_items"]:
        if item["public_release"] == "sanitized_derivative_only":
            item["redaction_status"] = "ready_for_sanitized_derivative" if status == "redaction_ready" else "blocked_until_private_evidence"
    if status == "manual_review":
        report["checks"][1]["status"] = "manual_review"
        report["summary"]["manual_review_check_count"] = 1
        report["summary"]["passed_check_count"] -= 1
    return report


class PeerPrivateImportPlanTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-private-import-plan-manifest.synthetic.json": "quest-termux-lab.peer-private-import-plan-manifest.v1",
            "peer-private-import-plan-report.synthetic.json": "quest-termux-lab.peer-private-import-plan-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked_by_redaction(self) -> None:
        report = peer_mesh_private_import_plan.build_import_plan_report(
            load_example("peer-private-import-plan-manifest.synthetic.json"),
            load_example("peer-public-package-report.synthetic.json"),
            load_example("peer-private-evidence-redaction-report.synthetic.json"),
            now_text="2026-06-04T10:04:05Z",
        )
        self.assertEqual(report["overall_status"], "import_blocked")
        self.assertEqual(report["package_status"], "package_ready")
        self.assertEqual(report["redaction_status"], "redaction_blocked")
        self.assertEqual(report["summary"]["private_only_item_count"], 2)
        self.assertEqual(report["summary"]["blocked_derivative_item_count"], 5)

    def test_ready_package_and_redaction_create_ready_import_plan(self) -> None:
        report = peer_mesh_private_import_plan.build_import_plan_report(
            minimal_manifest(),
            ready_package("package_ready"),
            ready_redaction("redaction_ready"),
        )
        self.assertEqual(report["overall_status"], "import_ready")
        self.assertEqual(report["summary"]["ready_derivative_item_count"], 5)
        self.assertEqual(report["summary"]["private_only_item_count"], 2)

    def test_manual_redaction_can_remain_manual_when_not_required_ready(self) -> None:
        manifest = minimal_manifest()
        manifest["require_redaction_ready"] = False
        report = peer_mesh_private_import_plan.build_import_plan_report(
            manifest,
            ready_package("package_ready"),
            ready_redaction("manual_review"),
        )
        self.assertEqual(report["overall_status"], "manual_review")

    def test_blocked_package_blocks_import_plan(self) -> None:
        report = peer_mesh_private_import_plan.build_import_plan_report(
            minimal_manifest(),
            ready_package("package_blocked"),
            ready_redaction("redaction_ready"),
        )
        self.assertEqual(report["overall_status"], "import_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["package_status"], "failed")

    def test_identity_mismatch_blocks_import_plan(self) -> None:
        package = ready_package("package_ready")
        package["fleet_id"] = "other-fleet"
        report = peer_mesh_private_import_plan.build_import_plan_report(
            minimal_manifest(),
            package,
            ready_redaction("redaction_ready"),
        )
        self.assertEqual(report["overall_status"], "import_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["package_identity"], "failed")

    def test_missing_derivative_schema_blocks_import_plan(self) -> None:
        redaction = ready_redaction("redaction_ready")
        for item in redaction["redaction_items"]:
            if item["public_release"] == "sanitized_derivative_only":
                item["public_derivative_schema"] = ""
                break
        report = peer_mesh_private_import_plan.build_import_plan_report(
            minimal_manifest(),
            ready_package("package_ready"),
            redaction,
        )
        self.assertEqual(report["overall_status"], "import_blocked")
        self.assertEqual(report["summary"]["missing_derivative_schema_count"], 1)

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_import_plan.validate_manifest(manifest)

    def test_absolute_report_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["package_report_path"] = "C:/private/package.json"
        with self.assertRaises(ValueError):
            peer_mesh_private_import_plan.validate_manifest(manifest)

    def test_forbidden_redaction_field_is_rejected(self) -> None:
        redaction = ready_redaction("redaction_ready")
        redaction["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_import_plan.validate_redaction_report(redaction)

    def test_cli_writes_report(self) -> None:
        report_path = REPO_ROOT / "examples" / "peer-private-import-plan-report.synthetic.json"
        exit_code = peer_mesh_private_import_plan.main(
            [
                "--manifest",
                str(REPO_ROOT / "examples" / "peer-private-import-plan-manifest.synthetic.json"),
                "--artifact-root",
                str(REPO_ROOT),
                "--now",
                "2026-06-04T10:04:05Z",
                "--output",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "import_blocked")


if __name__ == "__main__":
    unittest.main()
