#!/usr/bin/env python3
"""Tests for public-safe peer file-drop inbox intake dry runs."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INTAKE_PATH = REPO_ROOT / "tools" / "peer_mesh_file_drop_inbox_intake.py"


def load_module():
    sys.path.insert(0, str(INTAKE_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_file_drop_inbox_intake", INTAKE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_file_drop_inbox_intake")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_file_drop_inbox_intake"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_file_drop_inbox_intake = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-file-drop-inbox-intake-manifest.v1",
        "intake_id": "file-drop-inbox-intake-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "receiver_agent_id": "quest-agent-gamma",
        "observed_at": "2026-06-04T10:00:04Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "expected_message_schema": "quest-termux-lab.peer-gossip-envelope.v1",
        "inbox_entries": [
            {
                "delivery_id": "delivery-alpha-to-gamma-file-drop-001",
                "target_agent_id": "quest-agent-gamma",
                "message_id": "gossip-alpha-file-drop-001",
                "relative_staging_path": (
                    "runs/peer-mesh-round/peer-round-synthetic-001/quest-agent-gamma/inbox/"
                    "quest-agent-alpha__to__quest-agent-gamma__gossip-alpha-file-drop-001.peer-gossip-envelope.json"
                ),
                "simulated_presence": "simulated_present",
                "envelope_path": "examples/peer-gossip-envelope.file-drop.synthetic.json",
                "reason": "synthetic file-drop envelope fixture is present",
            }
        ],
        "authority_boundary": ["synthetic file-drop inbox intake boundary"],
    }


def minimal_copy_report(status: str = "simulated_copied") -> dict:
    report = load_example("peer-file-drop-copy-dry-run-report.synthetic.json")
    report["actions"][0]["status"] = status
    report["actions"][0]["simulated_result"] = status
    return report


class PeerFileDropInboxIntakeTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-file-drop-inbox-intake-manifest.synthetic.json": (
                "quest-termux-lab.peer-file-drop-inbox-intake-manifest.v1"
            ),
            "peer-gossip-envelope.file-drop.synthetic.json": "quest-termux-lab.peer-gossip-envelope.v1",
            "peer-file-drop-inbox-intake-report.synthetic.json": (
                "quest-termux-lab.peer-file-drop-inbox-intake-report.v1"
            ),
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_ready(self) -> None:
        report = peer_mesh_file_drop_inbox_intake.build_inbox_intake_report(
            load_example("peer-file-drop-copy-dry-run-report.synthetic.json"),
            load_example("peer-file-drop-inbox-intake-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:00:04Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_inbox_intake_ready")
        self.assertEqual(report["summary"]["accepted_count"], 1)
        self.assertEqual(report["summary"]["failed_count"], 0)
        entry = report["intake_entries"][0]
        self.assertEqual(entry["status"], "accepted")
        self.assertEqual(entry["observed_message_schema"], "quest-termux-lab.peer-gossip-envelope.v1")
        self.assertEqual(entry["observed_sender_agent_id"], "quest-agent-alpha")
        self.assertEqual(entry["observed_observation_count"], 1)

    def test_missing_file_presence_blocks_report(self) -> None:
        manifest = minimal_manifest()
        manifest["inbox_entries"][0]["simulated_presence"] = "simulated_missing_file"
        manifest["inbox_entries"][0]["envelope_path"] = None
        report = peer_mesh_file_drop_inbox_intake.build_inbox_intake_report(
            minimal_copy_report(),
            manifest,
            REPO_ROOT,
            now_text="2026-06-04T10:00:04Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_inbox_intake_blocked")
        self.assertEqual(report["summary"]["missing_file_count"], 1)
        self.assertEqual(report["intake_entries"][0]["status"], "missing_file")

    def test_not_copied_action_blocks_intake(self) -> None:
        report = peer_mesh_file_drop_inbox_intake.build_inbox_intake_report(
            minimal_copy_report("simulated_missing_source"),
            minimal_manifest(),
            REPO_ROOT,
            now_text="2026-06-04T10:00:04Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_inbox_intake_blocked")
        self.assertEqual(report["summary"]["not_copied_count"], 1)
        self.assertEqual(report["intake_entries"][0]["status"], "not_copied")

    def test_duplicate_file_is_ready_and_ignored(self) -> None:
        manifest = minimal_manifest()
        manifest["inbox_entries"][0]["simulated_presence"] = "simulated_duplicate_file"
        report = peer_mesh_file_drop_inbox_intake.build_inbox_intake_report(
            minimal_copy_report(),
            manifest,
            REPO_ROOT,
            now_text="2026-06-04T10:00:04Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_inbox_intake_ready")
        self.assertEqual(report["summary"]["duplicate_count"], 1)
        self.assertEqual(report["intake_entries"][0]["status"], "duplicate_ignored")

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_inbox_intake.validate_manifest(manifest)

    def test_unsafe_envelope_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["inbox_entries"][0]["envelope_path"] = "../outside.json"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_inbox_intake.validate_manifest(manifest)

    def test_target_mismatch_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["inbox_entries"][0]["target_agent_id"] = "quest-agent-beta"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_inbox_intake.validate_manifest(manifest)

    def test_unknown_delivery_pair_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["inbox_entries"][0]["delivery_id"] = "unknown-delivery"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_inbox_intake.build_inbox_intake_report(
                minimal_copy_report(),
                manifest,
                REPO_ROOT,
            )

    def test_envelope_message_mismatch_blocks_report(self) -> None:
        manifest = minimal_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            examples = root / "examples"
            examples.mkdir()
            envelope = load_example("peer-gossip-envelope.file-drop.synthetic.json")
            envelope["message_id"] = "other-message"
            (examples / "bad-envelope.json").write_text(json.dumps(envelope), encoding="utf-8")
            manifest["inbox_entries"][0]["envelope_path"] = "examples/bad-envelope.json"
            report = peer_mesh_file_drop_inbox_intake.build_inbox_intake_report(
                minimal_copy_report(),
                manifest,
                root,
            )
        self.assertEqual(report["overall_status"], "file_drop_inbox_intake_blocked")
        self.assertEqual(report["summary"]["invalid_envelope_count"], 1)
        self.assertIn("message_id mismatch", report["intake_entries"][0]["reason"])

    def test_forbidden_envelope_field_blocks_report(self) -> None:
        manifest = minimal_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            examples = root / "examples"
            examples.mkdir()
            envelope = load_example("peer-gossip-envelope.file-drop.synthetic.json")
            envelope["shell"] = "not-public"
            (examples / "bad-envelope.json").write_text(json.dumps(envelope), encoding="utf-8")
            manifest["inbox_entries"][0]["envelope_path"] = "examples/bad-envelope.json"
            report = peer_mesh_file_drop_inbox_intake.build_inbox_intake_report(
                minimal_copy_report(),
                manifest,
                root,
            )
        self.assertEqual(report["overall_status"], "file_drop_inbox_intake_blocked")
        self.assertEqual(report["summary"]["invalid_envelope_count"], 1)
        self.assertIn("credential-like", report["intake_entries"][0]["reason"])

    def test_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            copy_report_path = root / "copy-report.json"
            output_path = root / "report.json"
            examples = root / "examples"
            examples.mkdir()
            (examples / "peer-gossip-envelope.file-drop.synthetic.json").write_text(
                json.dumps(load_example("peer-gossip-envelope.file-drop.synthetic.json")),
                encoding="utf-8",
            )
            manifest_path.write_text(json.dumps(minimal_manifest()), encoding="utf-8")
            copy_report_path.write_text(json.dumps(minimal_copy_report()), encoding="utf-8")
            exit_code = peer_mesh_file_drop_inbox_intake.main(
                [
                    "--copy-report",
                    str(copy_report_path),
                    "--manifest",
                    str(manifest_path),
                    "--artifact-root",
                    str(root),
                    "--output",
                    str(output_path),
                ]
            )
            report = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "file_drop_inbox_intake_ready")


if __name__ == "__main__":
    unittest.main()
