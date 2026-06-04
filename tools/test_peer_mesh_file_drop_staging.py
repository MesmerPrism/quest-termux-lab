#!/usr/bin/env python3
"""Tests for public-safe peer file-drop staging plans."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STAGING_PATH = REPO_ROOT / "tools" / "peer_mesh_file_drop_staging.py"


def load_module():
    sys.path.insert(0, str(STAGING_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_file_drop_staging", STAGING_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_file_drop_staging")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_file_drop_staging"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_file_drop_staging = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return {
        "schema": "quest-termux-lab.peer-file-drop-staging-manifest.v1",
        "staging_plan_id": "file-drop-staging-test",
        "fleet_id": "synthetic-lab-fleet",
        "source_agent_id": "quest-agent-alpha",
        "observed_at": "2026-06-04T10:00:02Z",
        "experiment_scope": "private_configured_peer_gossip_only",
        "route_config_path": "route-config.json",
        "delivery_state_path": "delivery-state.json",
        "expected_message_schema": "quest-termux-lab.peer-gossip-envelope.v1",
        "authority_boundary": ["synthetic file-drop staging boundary"],
    }


class PeerFileDropStagingTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-delivery-state.file-drop.synthetic.json": "quest-termux-lab.peer-delivery-state.v1",
            "peer-file-drop-staging-manifest.synthetic.json": "quest-termux-lab.peer-file-drop-staging-manifest.v1",
            "peer-file-drop-staging-report.synthetic.json": "quest-termux-lab.peer-file-drop-staging-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_ready(self) -> None:
        report = peer_mesh_file_drop_staging.build_file_drop_staging_report(
            load_example("peer-file-drop-staging-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:00:02Z",
        )
        self.assertEqual(report["overall_status"], "file_drop_staging_ready")
        self.assertEqual(report["summary"]["planned_count"], 1)
        entry = report["staging_entries"][0]
        self.assertEqual(entry["status"], "planned")
        self.assertEqual(entry["transport_mode"], "file_drop_simulator")
        self.assertEqual(entry["method"], "copy_envelope")
        self.assertEqual(entry["target_inbox_dir"], "runs/peer-mesh-round/peer-round-synthetic-001/quest-agent-gamma/inbox")
        self.assertTrue(entry["relative_staging_path"].startswith(entry["target_inbox_dir"] + "/"))
        self.assertTrue(entry["relative_staging_path"].endswith(".peer-gossip-envelope.json"))
        self.assertNotIn("..", Path(entry["relative_staging_path"]).parts)

    def test_loopback_ready_dispatch_is_manual_review(self) -> None:
        manifest = load_example("peer-file-drop-staging-manifest.synthetic.json")
        manifest["delivery_state_path"] = "examples/peer-delivery-state.synthetic.json"
        report = peer_mesh_file_drop_staging.build_file_drop_staging_report(
            manifest,
            REPO_ROOT,
            now_text="2026-06-04T10:00:02Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        self.assertEqual(report["summary"]["planned_count"], 0)
        self.assertEqual(report["summary"]["skipped_non_file_drop_count"], 1)
        self.assertEqual(report["staging_entries"][0]["status"], "skipped_non_file_drop")

    def test_expired_delivery_is_skipped_not_ready(self) -> None:
        report = peer_mesh_file_drop_staging.build_file_drop_staging_report(
            load_example("peer-file-drop-staging-manifest.synthetic.json"),
            REPO_ROOT,
            now_text="2026-06-04T10:05:01Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        self.assertEqual(report["summary"]["planned_count"], 0)
        self.assertEqual(report["summary"]["skipped_not_ready_count"], 1)
        self.assertEqual(report["staging_entries"][0]["status"], "skipped_not_ready")

    def test_safe_filename_strips_path_separators(self) -> None:
        filename = peer_mesh_file_drop_staging.staging_filename(
            "quest/agent/alpha",
            "../target",
            "gossip/../../001",
        )
        self.assertEqual(Path(filename).name, filename)
        self.assertNotIn("..", Path(filename).parts)

    def test_absolute_manifest_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["route_config_path"] = "C:/private/route-config.json"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_staging.validate_manifest(manifest)

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_file_drop_staging.validate_manifest(manifest)

    def test_route_identity_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = minimal_manifest()
            route_config = load_example("peer-route-config.synthetic.json")
            route_config["fleet_id"] = "other-fleet"
            delivery_state = load_example("peer-delivery-state.file-drop.synthetic.json")
            (root / "route-config.json").write_text(json.dumps(route_config), encoding="utf-8")
            (root / "delivery-state.json").write_text(json.dumps(delivery_state), encoding="utf-8")
            with self.assertRaises(ValueError):
                peer_mesh_file_drop_staging.build_file_drop_staging_report(manifest, root)

    def test_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = minimal_manifest()
            route_config = load_example("peer-route-config.synthetic.json")
            delivery_state = load_example("peer-delivery-state.file-drop.synthetic.json")
            (root / "route-config.json").write_text(json.dumps(route_config), encoding="utf-8")
            (root / "delivery-state.json").write_text(json.dumps(delivery_state), encoding="utf-8")
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            exit_code = peer_mesh_file_drop_staging.main(
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
        self.assertEqual(report["overall_status"], "file_drop_staging_ready")


if __name__ == "__main__":
    unittest.main()
