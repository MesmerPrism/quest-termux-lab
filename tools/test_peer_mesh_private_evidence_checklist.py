#!/usr/bin/env python3
"""Tests for private evidence checklist reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_PATH = REPO_ROOT / "tools" / "peer_mesh_private_evidence_checklist.py"


def load_module():
    sys.path.insert(0, str(CHECKLIST_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_private_evidence_checklist", CHECKLIST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_private_evidence_checklist")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_private_evidence_checklist"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_private_evidence_checklist = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-private-evidence-checklist-manifest.v1",
        "checklist_id": "checklist-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:01:02Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "handoff_report_path": "handoff.json",
        "require_handoff_ready": True,
        "authority_boundary": ["synthetic checklist boundary"],
    }


def ready_handoff(status: str = "handoff_ready") -> dict:
    report = copy.deepcopy(load_example("peer-private-run-handoff-report.synthetic.json"))
    report["overall_status"] = status
    for check in report["checks"]:
        check["status"] = "passed"
        if check["check_id"] == "review_bundle_status":
            check["observed"] = "review_ready" if status == "handoff_ready" else "manual_review"
    report["summary"]["failed_check_count"] = 0
    report["summary"]["manual_review_check_count"] = 0
    report["summary"]["passed_check_count"] = report["summary"]["check_count"]
    if status == "manual_review":
        report["checks"][1]["status"] = "manual_review"
        report["summary"]["manual_review_check_count"] = 1
        report["summary"]["passed_check_count"] -= 1
    return report


class PeerPrivateEvidenceChecklistTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-private-evidence-checklist-manifest.synthetic.json": "quest-termux-lab.peer-private-evidence-checklist-manifest.v1",
            "peer-private-evidence-checklist-report.synthetic.json": "quest-termux-lab.peer-private-evidence-checklist-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked_by_handoff(self) -> None:
        report = peer_mesh_private_evidence_checklist.build_checklist_report(
            load_example("peer-private-evidence-checklist-manifest.synthetic.json"),
            load_example("peer-private-run-handoff-report.synthetic.json"),
            now_text="2026-06-04T10:01:02Z",
        )
        self.assertEqual(report["overall_status"], "checklist_blocked")
        self.assertEqual(report["handoff_status"], "handoff_blocked")
        self.assertEqual(report["summary"]["required_private_evidence_item_count"], 5)
        self.assertEqual(report["summary"]["optional_private_evidence_item_count"], 2)

    def test_ready_handoff_creates_ready_checklist(self) -> None:
        report = peer_mesh_private_evidence_checklist.build_checklist_report(
            minimal_manifest(),
            ready_handoff("handoff_ready"),
        )
        self.assertEqual(report["overall_status"], "checklist_ready")
        self.assertEqual(report["summary"]["failed_check_count"], 0)
        self.assertEqual({item["collection_status"] for item in report["private_evidence_items"]}, {"pending_private_run", "optional_pending_private_run"})

    def test_manual_handoff_can_remain_manual_when_not_required_ready(self) -> None:
        manifest = minimal_manifest()
        manifest["require_handoff_ready"] = False
        report = peer_mesh_private_evidence_checklist.build_checklist_report(
            manifest,
            ready_handoff("manual_review"),
        )
        self.assertEqual(report["overall_status"], "manual_review")

    def test_identity_mismatch_blocks_checklist(self) -> None:
        handoff = ready_handoff("handoff_ready")
        handoff["fleet_id"] = "other-fleet"
        report = peer_mesh_private_evidence_checklist.build_checklist_report(minimal_manifest(), handoff)
        self.assertEqual(report["overall_status"], "checklist_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["handoff_identity"], "failed")

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_evidence_checklist.validate_manifest(manifest)

    def test_absolute_handoff_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["handoff_report_path"] = "C:/private/handoff.json"
        with self.assertRaises(ValueError):
            peer_mesh_private_evidence_checklist.validate_manifest(manifest)

    def test_forbidden_handoff_field_is_rejected(self) -> None:
        handoff = ready_handoff("handoff_ready")
        handoff["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_evidence_checklist.validate_handoff_report(handoff)


if __name__ == "__main__":
    unittest.main()
