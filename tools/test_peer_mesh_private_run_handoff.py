#!/usr/bin/env python3
"""Tests for private-run handoff gates."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = REPO_ROOT / "tools" / "peer_mesh_private_run_handoff.py"


def load_module():
    sys.path.insert(0, str(HANDOFF_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_private_run_handoff", HANDOFF_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_private_run_handoff")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_private_run_handoff"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_private_run_handoff = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-private-run-handoff-manifest.v1",
        "handoff_id": "handoff-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:00:16Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "review_bundle_report_path": "review.json",
        "require_review_ready": True,
        "required_private_evidence_slots": [
            {
                "slot_id": "operator_approval",
                "evidence_kind": "operator_approval_record",
                "expected_schema": "private.peer.operator-approval-record.v1",
                "reason": "operator approval is required outside this public repository",
            }
        ],
        "optional_private_evidence_slots": [],
        "authority_boundary": ["synthetic handoff boundary"],
    }


def review_report(status: str = "review_ready") -> dict:
    return {
        "schema": "quest-termux-lab.peer-review-bundle-report.v1",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:00:15Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "overall_status": status,
        "summary": {
            "entry_count": 1,
            "passed_count": 1 if status == "review_ready" else 0,
            "manual_review_count": 1 if status == "manual_review" else 0,
            "failed_count": 1 if status == "review_blocked" else 0,
        },
    }


class PeerPrivateRunHandoffTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-private-run-handoff-manifest.synthetic.json": "quest-termux-lab.peer-private-run-handoff-manifest.v1",
            "peer-private-run-handoff-report.synthetic.json": "quest-termux-lab.peer-private-run-handoff-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_handoff_blocked(self) -> None:
        report = peer_mesh_private_run_handoff.build_handoff_report(
            load_example("peer-private-run-handoff-manifest.synthetic.json"),
            load_example("peer-review-bundle-report.synthetic.json"),
            now_text="2026-06-04T10:00:16Z",
        )
        self.assertEqual(report["overall_status"], "handoff_blocked")
        self.assertEqual(report["review_bundle_status"], "review_blocked")
        self.assertEqual(report["summary"]["required_evidence_slot_count"], 5)

    def test_review_ready_handoff_is_ready(self) -> None:
        report = peer_mesh_private_run_handoff.build_handoff_report(
            minimal_manifest(),
            review_report("review_ready"),
        )
        self.assertEqual(report["overall_status"], "handoff_ready")
        self.assertEqual(report["summary"]["failed_check_count"], 0)

    def test_manual_review_can_remain_manual_when_allowed(self) -> None:
        manifest = minimal_manifest()
        manifest["require_review_ready"] = False
        report = peer_mesh_private_run_handoff.build_handoff_report(
            manifest,
            review_report("manual_review"),
        )
        self.assertEqual(report["overall_status"], "manual_review")
        self.assertEqual(report["summary"]["manual_review_check_count"], 1)

    def test_manual_review_blocks_when_ready_required(self) -> None:
        report = peer_mesh_private_run_handoff.build_handoff_report(
            minimal_manifest(),
            review_report("manual_review"),
        )
        self.assertEqual(report["overall_status"], "handoff_blocked")

    def test_identity_mismatch_blocks_handoff(self) -> None:
        review = review_report("review_ready")
        review["fleet_id"] = "other-fleet"
        report = peer_mesh_private_run_handoff.build_handoff_report(minimal_manifest(), review)
        self.assertEqual(report["overall_status"], "handoff_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["review_bundle_identity"], "failed")

    def test_duplicate_slot_ids_are_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["optional_private_evidence_slots"] = [
            dict(manifest["required_private_evidence_slots"][0])
        ]
        with self.assertRaises(ValueError):
            peer_mesh_private_run_handoff.validate_manifest(manifest)

    def test_missing_required_slots_are_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["required_private_evidence_slots"] = []
        with self.assertRaises(ValueError):
            peer_mesh_private_run_handoff.validate_manifest(manifest)

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["command"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_run_handoff.validate_manifest(manifest)

    def test_forbidden_review_field_is_rejected(self) -> None:
        review = review_report("review_ready")
        review["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_private_run_handoff.validate_review_bundle_report(review)

    def test_absolute_review_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["review_bundle_report_path"] = "C:/private/review.json"
        with self.assertRaises(ValueError):
            peer_mesh_private_run_handoff.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
