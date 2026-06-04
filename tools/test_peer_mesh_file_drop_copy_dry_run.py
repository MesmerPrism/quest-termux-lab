#!/usr/bin/env python3
"""Tests for public-safe peer file-drop copy dry runs."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DRY_RUN_PATH = REPO_ROOT / "tools" / "peer_mesh_file_drop_copy_dry_run.py"


def load_module():
    sys.path.insert(0, str(DRY_RUN_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_file_drop_copy_dry_run", DRY_RUN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_file_drop_copy_dry_run")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_file_drop_copy_dry_run"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_file_drop_copy_dry_run = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_outcomes() -> dict:
    return {
        "schema": "quest-termux-lab.peer-file-drop-copy-outcomes.v1",
        "outcomes_id": "copy-outcomes-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:00:03Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "outcomes": [
            {
                "delivery_id": "delivery-alpha-to-gamma-file-drop-001",
                "target_agent_id": "quest-agent-gamma",
                "message_id": "gossip-alpha-file-drop-001",
                "simulated_result": "simulated_copied",
                "reason": "synthetic copied outcome",
            }
        ],
        "authority_boundary": ["synthetic file-drop copy outcome boundary"],
    }


class PeerFileDropCopyDryRunTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-file-drop-copy-outcomes.synthetic.json": "quest-termux-lab.peer-file-drop-copy-outcomes.v1",
            "peer-file-drop-copy-dry-run-report.synthetic.json": (
                "quest-termux-lab.peer-file-drop-copy-dry-run-report.v1"
            ),
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_ready(self) -> None:
        report = peer_mesh_file_drop_copy_dry_run.build_copy_dry_run_report(
            load_example("peer-file-drop-staging-report.synthetic.json"),
            load_example("peer-file-drop-copy-outcomes.synthetic.json"),
            now_text="2026-06-04T10:00:03Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_copy_dry_run_ready")
        self.assertEqual(report["summary"]["planned_action_count"], 1)
        self.assertEqual(report["summary"]["copied_count"], 1)
        self.assertEqual(report["summary"]["failed_count"], 0)
        action = report["actions"][0]
        self.assertEqual(action["status"], "simulated_copied")
        self.assertEqual(action["simulated_result"], "simulated_copied")
        self.assertEqual(
            action["relative_staging_path"],
            "runs/peer-mesh-round/peer-round-synthetic-001/quest-agent-gamma/inbox/"
            "quest-agent-alpha__to__quest-agent-gamma__gossip-alpha-file-drop-001.peer-gossip-envelope.json",
        )

    def test_missing_outcome_blocks_planned_copy(self) -> None:
        outcomes = minimal_outcomes()
        outcomes["outcomes"] = []
        report = peer_mesh_file_drop_copy_dry_run.build_copy_dry_run_report(
            load_example("peer-file-drop-staging-report.synthetic.json"),
            outcomes,
            now_text="2026-06-04T10:00:03Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_copy_dry_run_blocked")
        self.assertEqual(report["summary"]["missing_outcome_count"], 1)
        self.assertEqual(report["summary"]["failed_count"], 1)
        self.assertEqual(report["actions"][0]["status"], "missing_outcome")

    def test_non_planned_staging_entry_is_manual_review(self) -> None:
        staging_report = load_example("peer-file-drop-staging-report.synthetic.json")
        entry = staging_report["staging_entries"][0]
        entry["status"] = "skipped_not_ready"
        entry["dispatch_decision"] = "expired"
        entry["target_inbox_dir"] = None
        entry["staging_filename"] = None
        entry["relative_staging_path"] = None
        entry["reason"] = "delivery expired"
        outcomes = minimal_outcomes()
        report = peer_mesh_file_drop_copy_dry_run.build_copy_dry_run_report(
            staging_report,
            outcomes,
            now_text="2026-06-04T10:00:03Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        self.assertEqual(report["summary"]["not_planned_count"], 1)
        self.assertEqual(report["actions"][0]["status"], "not_planned")

    def test_write_blocked_outcome_blocks_report(self) -> None:
        outcomes = minimal_outcomes()
        outcomes["outcomes"][0]["simulated_result"] = "simulated_write_blocked"
        outcomes["outcomes"][0]["reason"] = "synthetic write blocked"
        report = peer_mesh_file_drop_copy_dry_run.build_copy_dry_run_report(
            load_example("peer-file-drop-staging-report.synthetic.json"),
            outcomes,
            now_text="2026-06-04T10:00:03Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_copy_dry_run_blocked")
        self.assertEqual(report["summary"]["write_blocked_count"], 1)
        self.assertEqual(report["summary"]["failed_count"], 1)

    def test_duplicate_outcome_pairs_are_rejected(self) -> None:
        outcomes = minimal_outcomes()
        outcomes["outcomes"].append(dict(outcomes["outcomes"][0]))
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_copy_dry_run.validate_outcomes(outcomes)

    def test_forbidden_outcome_field_is_rejected(self) -> None:
        outcomes = minimal_outcomes()
        outcomes["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_copy_dry_run.validate_outcomes(outcomes)

    def test_identity_mismatch_is_rejected(self) -> None:
        outcomes = minimal_outcomes()
        outcomes["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_copy_dry_run.build_copy_dry_run_report(
                load_example("peer-file-drop-staging-report.synthetic.json"),
                outcomes,
            )

    def test_unsafe_staging_path_is_rejected(self) -> None:
        staging_report = load_example("peer-file-drop-staging-report.synthetic.json")
        staging_report["staging_entries"][0]["relative_staging_path"] = "../outside.json"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_copy_dry_run.validate_staging_report(staging_report)

    def test_outcome_for_unknown_delivery_is_rejected(self) -> None:
        outcomes = minimal_outcomes()
        outcomes["outcomes"][0]["delivery_id"] = "unknown-delivery"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_copy_dry_run.build_copy_dry_run_report(
                load_example("peer-file-drop-staging-report.synthetic.json"),
                outcomes,
            )

    def test_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging_path = root / "staging.json"
            outcomes_path = root / "outcomes.json"
            report_path = root / "report.json"
            staging_path.write_text(
                json.dumps(load_example("peer-file-drop-staging-report.synthetic.json")),
                encoding="utf-8",
            )
            outcomes_path.write_text(json.dumps(minimal_outcomes()), encoding="utf-8")
            exit_code = peer_mesh_file_drop_copy_dry_run.main(
                [
                    "--staging-report",
                    str(staging_path),
                    "--outcomes",
                    str(outcomes_path),
                    "--output",
                    str(report_path),
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "file_drop_copy_dry_run_ready")


if __name__ == "__main__":
    unittest.main()
