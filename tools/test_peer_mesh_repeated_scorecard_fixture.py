#!/usr/bin/env python3
"""Tests for repeated scorecard fixture generation."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tools" / "peer_mesh_repeated_scorecard_fixture.py"


def load_module():
    sys.path.insert(0, str(FIXTURE_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_repeated_scorecard_fixture", FIXTURE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_repeated_scorecard_fixture")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_repeated_scorecard_fixture"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_repeated_scorecard_fixture = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def temp_manifest() -> dict:
    manifest = copy.deepcopy(load_example("peer-repeated-scorecard-fixture-manifest.synthetic.json"))
    manifest["scorecard_template_path"] = "template.json"
    manifest["regression_policy_path"] = "policy.json"
    manifest["output_paths"] = {
        "scorecard_reports": [
            "generated/scorecard-clear-001.json",
            "generated/scorecard-clear-002.json",
        ],
        "scorecard_history": "generated/history-clear.json",
        "scorecard_regression_report": "generated/regression-clear.json",
    }
    return manifest


def write_temp_inputs(root: Path, manifest: dict) -> Path:
    (root / "template.json").write_text(
        json.dumps(load_example("peer-scorecard-report.synthetic.json")),
        encoding="utf-8",
    )
    (root / "policy.json").write_text(
        json.dumps(load_example("peer-scorecard-regression-policy.synthetic.json")),
        encoding="utf-8",
    )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


class PeerRepeatedScorecardFixtureTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-repeated-scorecard-fixture-manifest.synthetic.json": "quest-termux-lab.peer-repeated-scorecard-fixture-manifest.v1",
            "peer-repeated-scorecard-fixture-report.synthetic.json": "quest-termux-lab.peer-repeated-scorecard-fixture-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_example_report_declares_ready_clear_path(self) -> None:
        report = load_example("peer-repeated-scorecard-fixture-report.synthetic.json")
        self.assertEqual(report["overall_status"], "fixture_ready")
        self.assertEqual(report["history_status"], "synthetic_clear")
        self.assertEqual(report["history_trend"], "stable")
        self.assertEqual(report["regression_status"], "regression_clear")
        self.assertEqual(report["summary"]["regression_failed_check_count"], 0)

    def test_builds_clear_repeated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = temp_manifest()
            write_temp_inputs(root, manifest)
            report = peer_mesh_repeated_scorecard_fixture.build_repeated_fixture(
                manifest,
                load_example("peer-scorecard-report.synthetic.json"),
                load_example("peer-scorecard-regression-policy.synthetic.json"),
                root,
            )
            self.assertEqual(report["overall_status"], "fixture_ready")
            for path in manifest["output_paths"]["scorecard_reports"]:
                scorecard = json.loads((root / path).read_text(encoding="utf-8"))
                self.assertEqual(scorecard["overall_status"], "synthetic_clear")
                self.assertEqual(scorecard["pressure_points"], [])
                self.assertEqual(scorecard["summary"]["synthetic_clear_count"], 8)
            history = json.loads((root / manifest["output_paths"]["scorecard_history"]).read_text(encoding="utf-8"))
            regression = json.loads((root / manifest["output_paths"]["scorecard_regression_report"]).read_text(encoding="utf-8"))
            self.assertEqual(history["overall_status"], "synthetic_clear")
            self.assertEqual(history["overall_trend"], "stable")
            self.assertEqual(history["report_count"], 2)
            self.assertEqual(regression["overall_status"], "regression_clear")

    def test_cli_writes_report_and_declared_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = temp_manifest()
            manifest_path = write_temp_inputs(root, manifest)
            report_path = root / "fixture-report.json"
            exit_code = peer_mesh_repeated_scorecard_fixture.main(
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
            peer_mesh_repeated_scorecard_fixture.validate_manifest(manifest)

    def test_absolute_output_path_is_rejected(self) -> None:
        manifest = temp_manifest()
        manifest["output_paths"]["scorecard_reports"][0] = "C:/private/scorecard.json"
        with self.assertRaises(ValueError):
            peer_mesh_repeated_scorecard_fixture.validate_manifest(manifest)

    def test_mismatched_scorecard_lengths_are_rejected(self) -> None:
        manifest = temp_manifest()
        manifest["scorecard_observed_at"] = manifest["scorecard_observed_at"][:1]
        with self.assertRaises(ValueError):
            peer_mesh_repeated_scorecard_fixture.validate_manifest(manifest)

    def test_duplicate_scorecard_ids_are_rejected(self) -> None:
        manifest = temp_manifest()
        manifest["scorecard_ids"][1] = manifest["scorecard_ids"][0]
        with self.assertRaises(ValueError):
            peer_mesh_repeated_scorecard_fixture.validate_manifest(manifest)

    def test_damaged_template_schema_is_rejected(self) -> None:
        template = load_example("peer-scorecard-report.synthetic.json")
        template["schema"] = "wrong"
        with self.assertRaises(ValueError):
            peer_mesh_repeated_scorecard_fixture.build_repeated_fixture(
                temp_manifest(),
                template,
                load_example("peer-scorecard-regression-policy.synthetic.json"),
                REPO_ROOT,
                write_outputs=False,
            )

    def test_policy_identity_mismatch_is_rejected(self) -> None:
        policy = load_example("peer-scorecard-regression-policy.synthetic.json")
        policy["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_repeated_scorecard_fixture.build_repeated_fixture(
                temp_manifest(),
                load_example("peer-scorecard-report.synthetic.json"),
                policy,
                REPO_ROOT,
                write_outputs=False,
            )


if __name__ == "__main__":
    unittest.main()
