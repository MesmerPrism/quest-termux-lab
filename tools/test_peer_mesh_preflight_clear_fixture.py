#!/usr/bin/env python3
"""Tests for peer mesh preflight clear fixture generation."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tools" / "peer_mesh_preflight_clear_fixture.py"


def load_module():
    sys.path.insert(0, str(FIXTURE_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_preflight_clear_fixture", FIXTURE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_preflight_clear_fixture")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_preflight_clear_fixture"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_preflight_clear_fixture = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def temp_manifest() -> dict:
    manifest = copy.deepcopy(load_example("peer-preflight-clear-fixture-manifest.synthetic.json"))
    manifest["route_config_path"] = "route-config.json"
    manifest["topology_manifest_path"] = "topology-manifest.json"
    manifest["readiness_policy_template_path"] = "readiness-policy.json"
    manifest["lab_bundle_manifest_template_path"] = "lab-bundle-manifest.json"
    manifest["output_paths"] = {
        "route_health_reports": [
            "generated/route-health-clear-001.json",
            "generated/route-health-clear-002.json",
        ],
        "route_health_history": "generated/route-history-clear.json",
        "readiness_policy": "generated/readiness-policy-clear.json",
        "readiness_report": "generated/readiness-clear.json",
        "topology_report": "generated/topology-clear.json",
        "lab_bundle_manifest": "generated/lab-bundle-manifest-clear.json",
        "lab_bundle_report": "generated/lab-bundle-clear.json",
    }
    return manifest


def write_temp_inputs(root: Path, manifest: dict) -> Path:
    (root / "route-config.json").write_text(
        json.dumps(load_example("peer-route-config.synthetic.json")),
        encoding="utf-8",
    )
    (root / "topology-manifest.json").write_text(
        json.dumps(load_example("peer-topology-manifest.synthetic.json")),
        encoding="utf-8",
    )
    (root / "readiness-policy.json").write_text(
        json.dumps(load_example("peer-live-lab-readiness-policy.synthetic.json")),
        encoding="utf-8",
    )
    (root / "lab-bundle-manifest.json").write_text(
        json.dumps(load_example("peer-lab-bundle-manifest.synthetic.json")),
        encoding="utf-8",
    )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


class PeerPreflightClearFixtureTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-preflight-clear-fixture-manifest.synthetic.json": "quest-termux-lab.peer-preflight-clear-fixture-manifest.v1",
            "peer-preflight-clear-fixture-report.synthetic.json": "quest-termux-lab.peer-preflight-clear-fixture-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_example_report_declares_ready_clear_preflight(self) -> None:
        report = load_example("peer-preflight-clear-fixture-report.synthetic.json")
        self.assertEqual(report["overall_status"], "fixture_ready")
        self.assertEqual(report["route_health_status"], "clear")
        self.assertEqual(report["route_history_status"], "clear")
        self.assertEqual(report["readiness_status"], "ready")
        self.assertEqual(report["topology_status"], "topology_ready")
        self.assertEqual(report["lab_bundle_status"], "synthetic_ready")
        self.assertEqual(report["summary"]["latest_unknown_route_count"], 0)
        self.assertEqual(report["summary"]["topology_non_ready_edge_count"], 0)

    def test_builds_clear_preflight_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = temp_manifest()
            write_temp_inputs(root, manifest)
            report = peer_mesh_preflight_clear_fixture.build_preflight_clear_fixture(
                manifest,
                load_example("peer-route-config.synthetic.json"),
                load_example("peer-topology-manifest.synthetic.json"),
                load_example("peer-live-lab-readiness-policy.synthetic.json"),
                load_example("peer-lab-bundle-manifest.synthetic.json"),
                root,
            )
            self.assertEqual(report["overall_status"], "fixture_ready")
            self.assertEqual(report["summary"]["latest_healthy_route_count"], 2)
            self.assertEqual(report["summary"]["stable_route_count"], 2)
            latest_health = json.loads((root / manifest["output_paths"]["route_health_reports"][1]).read_text(encoding="utf-8"))
            history = json.loads((root / manifest["output_paths"]["route_health_history"]).read_text(encoding="utf-8"))
            readiness = json.loads((root / manifest["output_paths"]["readiness_report"]).read_text(encoding="utf-8"))
            topology = json.loads((root / manifest["output_paths"]["topology_report"]).read_text(encoding="utf-8"))
            bundle = json.loads((root / manifest["output_paths"]["lab_bundle_report"]).read_text(encoding="utf-8"))
            self.assertEqual(latest_health["summary"]["healthy_count"], 2)
            self.assertEqual(latest_health["summary"]["unknown_count"], 0)
            self.assertEqual(history["summary"]["stable_count"], 2)
            self.assertEqual(readiness["overall_status"], "ready")
            self.assertEqual(topology["overall_status"], "topology_ready")
            self.assertEqual(bundle["overall_status"], "synthetic_ready")

    def test_cli_writes_report_and_declared_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = temp_manifest()
            manifest_path = write_temp_inputs(root, manifest)
            report_path = root / "fixture-report.json"
            exit_code = peer_mesh_preflight_clear_fixture.main(
                [
                    "--manifest",
                    str(manifest_path),
                    "--artifact-root",
                    str(root),
                    "--output",
                    str(report_path),
                ]
            )
            self.assertEqual(exit_code, 0)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["overall_status"], "fixture_ready")
            for entry in report["generated_artifacts"]:
                self.assertEqual(entry["status"], "written")
                self.assertTrue((root / entry["path"]).exists())

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = temp_manifest()
        manifest["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_preflight_clear_fixture.validate_manifest(manifest)

    def test_absolute_output_path_is_rejected(self) -> None:
        manifest = temp_manifest()
        manifest["output_paths"]["route_health_reports"][0] = "C:/private/route-health.json"
        with self.assertRaises(ValueError):
            peer_mesh_preflight_clear_fixture.validate_manifest(manifest)

    def test_mismatched_route_health_output_lengths_are_rejected(self) -> None:
        manifest = temp_manifest()
        manifest["route_health_observed_at"] = manifest["route_health_observed_at"][:1]
        with self.assertRaises(ValueError):
            peer_mesh_preflight_clear_fixture.validate_manifest(manifest)

    def test_template_identity_mismatch_is_rejected(self) -> None:
        policy = load_example("peer-live-lab-readiness-policy.synthetic.json")
        policy["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_preflight_clear_fixture.build_preflight_clear_fixture(
                temp_manifest(),
                load_example("peer-route-config.synthetic.json"),
                load_example("peer-topology-manifest.synthetic.json"),
                policy,
                load_example("peer-lab-bundle-manifest.synthetic.json"),
                REPO_ROOT,
                write_outputs=False,
            )


if __name__ == "__main__":
    unittest.main()
