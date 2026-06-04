#!/usr/bin/env python3
"""Tests for private evidence redaction reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REDACTION_PATH = REPO_ROOT / "tools" / "peer_mesh_private_evidence_redaction.py"


def load_module():
    sys.path.insert(0, str(REDACTION_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_private_evidence_redaction", REDACTION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_private_evidence_redaction")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_private_evidence_redaction"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_private_evidence_redaction = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return copy.deepcopy(load_example("peer-private-evidence-redaction-manifest.synthetic.json"))


def ready_checklist(status: str = "checklist_ready") -> dict:
    report = copy.deepcopy(load_example("peer-private-evidence-checklist-report.synthetic.json"))
    report["overall_status"] = status
    report["handoff_status"] = "handoff_ready" if status == "checklist_ready" else "manual_review"
    for check in report["checks"]:
        check["status"] = "passed"
        if check["check_id"] == "handoff_status":
            check["observed"] = "handoff_ready" if status == "checklist_ready" else "manual_review"
            check["reason"] = "handoff is ready for private evidence collection"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["passed_check_count"] = report["summary"]["check_count"]
    if status == "manual_review":
        report["checks"][1]["status"] = "manual_review"
        report["summary"]["manual_review_check_count"] = 1
        report["summary"]["passed_check_count"] -= 1
    return report


class PeerPrivateEvidenceRedactionTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-private-evidence-redaction-manifest.synthetic.json": "quest-termux-lab.peer-private-evidence-redaction-manifest.v1",
            "peer-private-evidence-redaction-report.synthetic.json": "quest-termux-lab.peer-private-evidence-redaction-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked_by_checklist(self) -> None:
        report = peer_mesh_private_evidence_redaction.build_redaction_report(
            load_example("peer-private-evidence-redaction-manifest.synthetic.json"),
            load_example("peer-private-evidence-checklist-report.synthetic.json"),
            now_text="2026-06-04T10:02:03Z",
        )
        self.assertEqual(report["overall_status"], "redaction_blocked")
        self.assertEqual(report["checklist_status"], "checklist_blocked")
        self.assertEqual(report["summary"]["failed_check_count"], 1)
        self.assertEqual(report["summary"]["private_only_item_count"], 2)
        self.assertEqual(report["summary"]["sanitized_derivative_item_count"], 5)
        self.assertEqual(report["summary"]["ready_derivative_item_count"], 0)

    def test_ready_checklist_creates_ready_redaction_plan(self) -> None:
        report = peer_mesh_private_evidence_redaction.build_redaction_report(
            minimal_manifest(),
            ready_checklist("checklist_ready"),
        )
        self.assertEqual(report["overall_status"], "redaction_ready")
        self.assertEqual(report["summary"]["failed_check_count"], 0)
        self.assertEqual(report["summary"]["ready_derivative_item_count"], 5)
        self.assertEqual(report["summary"]["private_only_item_count"], 2)
        self.assertEqual(report["summary"]["blocked_redaction_item_count"], 0)

    def test_manual_checklist_can_remain_manual_when_not_required_ready(self) -> None:
        manifest = minimal_manifest()
        manifest["require_checklist_ready"] = False
        report = peer_mesh_private_evidence_redaction.build_redaction_report(
            manifest,
            ready_checklist("manual_review"),
        )
        self.assertEqual(report["overall_status"], "manual_review")

    def test_missing_rule_coverage_blocks_redaction(self) -> None:
        manifest = minimal_manifest()
        manifest["evidence_redaction_rules"] = [
            rule
            for rule in manifest["evidence_redaction_rules"]
            if rule["evidence_kind"] != "cleanup_record"
        ]
        report = peer_mesh_private_evidence_redaction.build_redaction_report(
            manifest,
            ready_checklist("checklist_ready"),
        )
        self.assertEqual(report["overall_status"], "redaction_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["rule_coverage"], "failed")
        self.assertEqual(report["summary"]["missing_rule_count"], 1)

    def test_identity_mismatch_blocks_redaction(self) -> None:
        checklist = ready_checklist("checklist_ready")
        checklist["fleet_id"] = "other-fleet"
        report = peer_mesh_private_evidence_redaction.build_redaction_report(minimal_manifest(), checklist)
        self.assertEqual(report["overall_status"], "redaction_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["checklist_identity"], "failed")

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_evidence_redaction.validate_manifest(manifest)

    def test_absolute_checklist_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["checklist_report_path"] = "C:/private/checklist.json"
        with self.assertRaises(ValueError):
            peer_mesh_private_evidence_redaction.validate_manifest(manifest)

    def test_forbidden_checklist_field_is_rejected(self) -> None:
        checklist = ready_checklist("checklist_ready")
        checklist["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_evidence_redaction.validate_checklist_report(checklist)

    def test_sanitized_derivative_rules_require_public_schema(self) -> None:
        manifest = minimal_manifest()
        manifest["evidence_redaction_rules"][2]["public_derivative_schema"] = ""
        with self.assertRaises(ValueError):
            peer_mesh_private_evidence_redaction.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
