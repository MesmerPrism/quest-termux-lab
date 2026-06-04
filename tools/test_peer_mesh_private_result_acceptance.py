#!/usr/bin/env python3
"""Tests for private result acceptance reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_PATH = REPO_ROOT / "tools" / "peer_mesh_private_result_acceptance.py"


def load_module():
    sys.path.insert(0, str(ACCEPTANCE_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_private_result_acceptance", ACCEPTANCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_private_result_acceptance")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_private_result_acceptance"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_private_result_acceptance = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return copy.deepcopy(load_example("peer-private-result-acceptance-manifest.synthetic.json"))


def ready_placeholder(status: str = "result_placeholders_ready") -> dict:
    report = copy.deepcopy(load_example("peer-private-result-placeholder-report.synthetic.json"))
    report["overall_status"] = status
    for check in report["checks"]:
        check["status"] = "passed"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["passed_check_count"] = report["summary"]["check_count"]
    if status == "manual_review":
        report["checks"][1]["status"] = "manual_review"
        report["summary"]["manual_review_check_count"] = 1
        report["summary"]["passed_check_count"] -= 1
    for slot in report["placeholder_slots"]:
        if slot["public_release"] == "sanitized_derivative_only":
            slot["placeholder_status"] = (
                "awaiting_sanitized_derivative_artifact"
                if status == "result_placeholders_ready"
                else "blocked_until_import_ready"
            )
            slot["source_import_status"] = (
                "ready_for_public_derivative"
                if status == "result_placeholders_ready"
                else "blocked_until_redaction_ready"
            )
    report["summary"]["awaiting_derivative_slot_count"] = sum(
        1
        for slot in report["placeholder_slots"]
        if slot["placeholder_status"] == "awaiting_sanitized_derivative_artifact"
    )
    report["summary"]["blocked_slot_count"] = sum(
        1
        for slot in report["placeholder_slots"]
        if slot["placeholder_status"] in {"blocked_until_import_ready", "blocked_missing_derivative_schema"}
    )
    return report


class PeerPrivateResultAcceptanceTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-private-result-acceptance-manifest.synthetic.json": "quest-termux-lab.peer-private-result-acceptance-manifest.v1",
            "peer-private-result-acceptance-report.synthetic.json": "quest-termux-lab.peer-private-result-acceptance-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked_by_placeholder_status(self) -> None:
        report = peer_mesh_private_result_acceptance.build_acceptance_report(
            load_example("peer-private-result-acceptance-manifest.synthetic.json"),
            load_example("peer-private-result-placeholder-report.synthetic.json"),
            now_text="2026-06-04T10:06:07Z",
        )
        self.assertEqual(report["overall_status"], "acceptance_blocked")
        self.assertEqual(report["placeholder_status"], "result_placeholders_blocked")
        self.assertEqual(report["summary"]["private_only_item_count"], 2)
        self.assertEqual(report["summary"]["blocked_item_count"], 5)

    def test_ready_placeholders_create_ready_acceptance(self) -> None:
        report = peer_mesh_private_result_acceptance.build_acceptance_report(
            minimal_manifest(),
            ready_placeholder("result_placeholders_ready"),
        )
        self.assertEqual(report["overall_status"], "acceptance_ready")
        self.assertEqual(report["summary"]["ready_to_accept_item_count"], 5)
        self.assertEqual(report["summary"]["private_only_item_count"], 2)
        self.assertEqual(report["summary"]["blocked_item_count"], 0)

    def test_manual_placeholder_can_remain_manual_when_not_required_ready(self) -> None:
        manifest = minimal_manifest()
        manifest["require_placeholders_ready"] = False
        report = peer_mesh_private_result_acceptance.build_acceptance_report(
            manifest,
            ready_placeholder("manual_review"),
        )
        self.assertEqual(report["overall_status"], "manual_review")

    def test_blocked_placeholder_blocks_acceptance(self) -> None:
        report = peer_mesh_private_result_acceptance.build_acceptance_report(
            minimal_manifest(),
            load_example("peer-private-result-placeholder-report.synthetic.json"),
        )
        self.assertEqual(report["overall_status"], "acceptance_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["placeholder_status"], "failed")

    def test_identity_mismatch_blocks_acceptance(self) -> None:
        placeholder_report = ready_placeholder("result_placeholders_ready")
        placeholder_report["fleet_id"] = "other-fleet"
        report = peer_mesh_private_result_acceptance.build_acceptance_report(minimal_manifest(), placeholder_report)
        self.assertEqual(report["overall_status"], "acceptance_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["placeholder_identity"], "failed")

    def test_missing_derivative_schema_blocks_acceptance(self) -> None:
        placeholder_report = ready_placeholder("result_placeholders_ready")
        for slot in placeholder_report["placeholder_slots"]:
            if slot["public_release"] == "sanitized_derivative_only":
                slot["public_derivative_schema"] = ""
                break
        report = peer_mesh_private_result_acceptance.build_acceptance_report(minimal_manifest(), placeholder_report)
        self.assertEqual(report["overall_status"], "acceptance_blocked")
        self.assertEqual(report["summary"]["blocked_missing_derivative_schema_count"], 1)

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_result_acceptance.validate_manifest(manifest)

    def test_absolute_placeholder_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["placeholder_report_path"] = "C:/private/placeholders.json"
        with self.assertRaises(ValueError):
            peer_mesh_private_result_acceptance.validate_manifest(manifest)

    def test_forbidden_placeholder_report_field_is_rejected(self) -> None:
        placeholder_report = ready_placeholder("result_placeholders_ready")
        placeholder_report["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_result_acceptance.validate_placeholder_report(placeholder_report)

    def test_cli_writes_report(self) -> None:
        report_path = REPO_ROOT / "examples" / "peer-private-result-acceptance-report.synthetic.json"
        exit_code = peer_mesh_private_result_acceptance.main(
            [
                "--manifest",
                str(REPO_ROOT / "examples" / "peer-private-result-acceptance-manifest.synthetic.json"),
                "--artifact-root",
                str(REPO_ROOT),
                "--now",
                "2026-06-04T10:06:07Z",
                "--output",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "acceptance_blocked")


if __name__ == "__main__":
    unittest.main()
