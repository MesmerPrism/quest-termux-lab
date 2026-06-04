#!/usr/bin/env python3
"""Tests for peer live-lab bundle reports."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = REPO_ROOT / "tools" / "peer_mesh_lab_bundle.py"


def load_module():
    sys.path.insert(0, str(BUNDLE_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_lab_bundle", BUNDLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_lab_bundle")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_lab_bundle"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_lab_bundle = load_module()
peer_mesh_live_lab_readiness = sys.modules["peer_mesh_live_lab_readiness"]
peer_mesh_topology = sys.modules["peer_mesh_topology"]


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def healthy_history() -> dict:
    history = load_example("peer-route-health-history.synthetic.json")
    history["report_count"] = 2
    history["summary"]["last_unknown_count"] = 0
    history["summary"]["stable_count"] = 2
    history["summary"]["single_sample_count"] = 0
    for route in history["routes"]:
        route["sample_count"] = 2
        route["first_status"] = "healthy"
        route["last_status"] = "healthy"
        route["trend"] = "stable"
        route["status_counts"] = {
            "degraded": 0,
            "disabled": 0,
            "healthy": 2,
            "unavailable": 0,
            "unknown": 0,
        }
        route["last_reason"] = "synthetic delivery accepted"
    return history


def ready_readiness(operator_gate: bool = False) -> dict:
    policy = load_example("peer-live-lab-readiness-policy.synthetic.json")
    policy["operator_approval_required"] = operator_gate
    return peer_mesh_live_lab_readiness.build_readiness_report(
        policy,
        healthy_history(),
        now_text="2026-06-04T10:00:07Z",
    )


def ready_topology() -> dict:
    topology = load_example("peer-topology-report.synthetic.json")
    topology["overall_status"] = "topology_ready"
    for check in topology["checks"]:
        check["status"] = "passed"
        if check["check_id"] == "healthy_route_threshold":
            check["observed"] = "2"
        if check["check_id"] == "reachable_agent_threshold":
            check["observed"] = "3"
        if check["check_id"] == "non_ready_route_policy":
            check["observed"] = "0"
    topology["summary"]["reachable_edge_count"] = 2
    topology["summary"]["reachable_agent_count"] = 3
    topology["summary"]["non_ready_edge_count"] = 0
    topology["summary"]["unreachable_edge_count"] = 0
    for edge in topology["edges"]:
        edge["route_health_status"] = "healthy"
        edge["reachability_status"] = "reachable"
        edge["reason"] = "route-health status is healthy"
    return topology


class PeerLabBundleTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-lab-bundle-manifest.synthetic.json": "quest-termux-lab.peer-lab-bundle-manifest.v1",
            "peer-lab-bundle-report.synthetic.json": "quest-termux-lab.peer-lab-bundle-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_synthetic_bundle_is_blocked_by_not_ready_readiness(self) -> None:
        report = peer_mesh_lab_bundle.build_bundle_report(
            load_example("peer-lab-bundle-manifest.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            load_example("peer-topology-report.synthetic.json"),
            load_example("peer-route-health-history.synthetic.json"),
            load_example("peer-live-lab-readiness-report.synthetic.json"),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertEqual(report["topology_status"], "topology_blocked")
        self.assertEqual(report["readiness_status"], "not_ready")

    def test_synthetic_bundle_is_blocked_by_blocked_topology(self) -> None:
        report = peer_mesh_lab_bundle.build_bundle_report(
            load_example("peer-lab-bundle-manifest.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            load_example("peer-topology-report.synthetic.json"),
            healthy_history(),
            ready_readiness(operator_gate=False),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertEqual(report["topology_status"], "topology_blocked")

    def test_ready_readiness_without_operator_gate_is_synthetic_ready(self) -> None:
        manifest = load_example("peer-lab-bundle-manifest.synthetic.json")
        manifest["operator_approval_required"] = False
        manifest["operator_approval_recorded"] = False
        report = peer_mesh_lab_bundle.build_bundle_report(
            manifest,
            load_example("peer-route-config.synthetic.json"),
            ready_topology(),
            healthy_history(),
            ready_readiness(operator_gate=False),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "synthetic_ready")

    def test_manifest_operator_gate_forces_manual_review(self) -> None:
        manifest = load_example("peer-lab-bundle-manifest.synthetic.json")
        manifest["operator_approval_required"] = True
        manifest["operator_approval_recorded"] = False
        report = peer_mesh_lab_bundle.build_bundle_report(
            manifest,
            load_example("peer-route-config.synthetic.json"),
            ready_topology(),
            healthy_history(),
            ready_readiness(operator_gate=False),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")

    def test_recorded_operator_gate_allows_synthetic_ready(self) -> None:
        manifest = load_example("peer-lab-bundle-manifest.synthetic.json")
        manifest["operator_approval_required"] = True
        manifest["operator_approval_recorded"] = True
        report = peer_mesh_lab_bundle.build_bundle_report(
            manifest,
            load_example("peer-route-config.synthetic.json"),
            ready_topology(),
            healthy_history(),
            ready_readiness(operator_gate=False),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "synthetic_ready")

    def test_fleet_mismatch_blocks_report(self) -> None:
        route_config = load_example("peer-route-config.synthetic.json")
        route_config["fleet_id"] = "other-fleet"
        report = peer_mesh_lab_bundle.build_bundle_report(
            load_example("peer-lab-bundle-manifest.synthetic.json"),
            route_config,
            load_example("peer-topology-report.synthetic.json"),
            load_example("peer-route-health-history.synthetic.json"),
            load_example("peer-live-lab-readiness-report.synthetic.json"),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertIn("fleet_id mismatch", report["artifact_checks"][0]["reason"])

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = load_example("peer-lab-bundle-manifest.synthetic.json")
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_lab_bundle.validate_manifest(manifest)

    def test_invalid_route_config_blocks_report(self) -> None:
        route_config = load_example("peer-route-config.synthetic.json")
        route_config["routes"][0]["gossip_endpoint"] = "http://example.invalid/api/peer/v1/gossip"
        report = peer_mesh_lab_bundle.build_bundle_report(
            load_example("peer-lab-bundle-manifest.synthetic.json"),
            route_config,
            load_example("peer-topology-report.synthetic.json"),
            load_example("peer-route-health-history.synthetic.json"),
            load_example("peer-live-lab-readiness-report.synthetic.json"),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertIn("loopback route", report["artifact_checks"][0]["reason"])

    def test_invalid_readiness_status_is_schema_safe_blocked(self) -> None:
        readiness = load_example("peer-live-lab-readiness-report.synthetic.json")
        readiness["overall_status"] = "surprising"
        readiness["summary"]["ready_route_count"] = "1"
        report = peer_mesh_lab_bundle.build_bundle_report(
            load_example("peer-lab-bundle-manifest.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            ready_topology(),
            load_example("peer-route-health-history.synthetic.json"),
            readiness,
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertEqual(report["readiness_status"], "invalid")
        self.assertEqual(report["summary"]["ready_route_count"], 0)

    def test_invalid_topology_status_is_schema_safe_blocked(self) -> None:
        topology = ready_topology()
        topology["overall_status"] = "surprising"
        topology["summary"]["reachable_agent_count"] = "3"
        report = peer_mesh_lab_bundle.build_bundle_report(
            load_example("peer-lab-bundle-manifest.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            topology,
            healthy_history(),
            ready_readiness(operator_gate=False),
            now_text="2026-06-04T10:00:08Z",
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertEqual(report["topology_status"], "invalid")
        self.assertEqual(report["summary"]["topology_reachable_agent_count"], 0)


if __name__ == "__main__":
    unittest.main()
