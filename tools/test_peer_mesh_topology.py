#!/usr/bin/env python3
"""Tests for peer topology coverage reports."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_PATH = REPO_ROOT / "tools" / "peer_mesh_topology.py"


def load_module():
    sys.path.insert(0, str(TOPOLOGY_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_topology", TOPOLOGY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_topology")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_topology"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_topology = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def minimal_manifest() -> dict:
    return copy.deepcopy(load_example("peer-topology-manifest.synthetic.json"))


def route_config() -> dict:
    return copy.deepcopy(load_example("peer-route-config.synthetic.json"))


def route_health(status: str = "healthy") -> dict:
    report = copy.deepcopy(load_example("peer-route-health-report.synthetic.json"))
    for route in report["routes"]:
        route["status"] = status
        if status == "healthy":
            route["latest_simulated_outcome"] = "accepted"
            route["retry_decision"] = "terminal"
            route["reason"] = "synthetic delivery accepted"
        elif status == "degraded":
            route["latest_simulated_outcome"] = "no_response"
            route["retry_decision"] = "due_now"
            route["reason"] = "synthetic no response"
        elif status == "unavailable":
            route["latest_simulated_outcome"] = "rejected"
            route["retry_decision"] = "max_attempts_reached"
            route["reason"] = "synthetic rejection"
    report["summary"]["healthy_count"] = sum(1 for route in report["routes"] if route["status"] == "healthy")
    report["summary"]["degraded_count"] = sum(1 for route in report["routes"] if route["status"] == "degraded")
    report["summary"]["unavailable_count"] = sum(1 for route in report["routes"] if route["status"] == "unavailable")
    report["summary"]["unknown_count"] = sum(1 for route in report["routes"] if route["status"] == "unknown")
    return report


class PeerTopologyTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-topology-manifest.synthetic.json": "quest-termux-lab.peer-topology-manifest.v1",
            "peer-topology-report.synthetic.json": "quest-termux-lab.peer-topology-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_blocked_by_unknown_route(self) -> None:
        report = peer_mesh_topology.build_topology_report(
            load_example("peer-topology-manifest.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            load_example("peer-route-health-report.synthetic.json"),
            now_text="2026-06-04T10:00:06Z",
        )
        self.assertEqual(report["overall_status"], "topology_blocked")
        self.assertEqual(report["summary"]["reachable_edge_count"], 1)
        self.assertEqual(report["summary"]["non_ready_edge_count"], 1)
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["healthy_route_threshold"], "failed")
        self.assertEqual(checks["non_ready_route_policy"], "failed")

    def test_all_healthy_routes_create_ready_topology(self) -> None:
        report = peer_mesh_topology.build_topology_report(
            minimal_manifest(),
            route_config(),
            route_health("healthy"),
        )
        self.assertEqual(report["overall_status"], "topology_ready")
        self.assertEqual(report["summary"]["reachable_agent_count"], 3)
        self.assertEqual(report["summary"]["reachable_edge_count"], 2)
        self.assertEqual(report["summary"]["non_ready_edge_count"], 0)

    def test_degraded_route_can_remain_manual_when_policy_allows(self) -> None:
        manifest = minimal_manifest()
        manifest["require_no_unhealthy_routes"] = False
        manifest["min_healthy_route_count"] = 0
        manifest["min_reachable_agent_count"] = 1
        report = peer_mesh_topology.build_topology_report(manifest, route_config(), route_health("degraded"))
        self.assertEqual(report["overall_status"], "manual_review")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["non_ready_route_policy"], "manual_review")

    def test_missing_expected_route_blocks_topology(self) -> None:
        config = route_config()
        config["routes"] = config["routes"][:1]
        health = route_health("healthy")
        health["routes"] = health["routes"][:1]
        report = peer_mesh_topology.build_topology_report(minimal_manifest(), config, health)
        self.assertEqual(report["overall_status"], "topology_blocked")
        self.assertEqual(report["summary"]["missing_route_count"], 1)

    def test_missing_health_yields_manual_review_if_thresholds_allow(self) -> None:
        manifest = minimal_manifest()
        manifest["require_no_unhealthy_routes"] = False
        manifest["min_healthy_route_count"] = 1
        manifest["min_reachable_agent_count"] = 2
        health = route_health("healthy")
        health["routes"] = health["routes"][:1]
        report = peer_mesh_topology.build_topology_report(manifest, route_config(), health)
        self.assertEqual(report["overall_status"], "manual_review")
        self.assertEqual(report["summary"]["missing_health_count"], 1)

    def test_identity_mismatch_blocks_topology(self) -> None:
        health = route_health("healthy")
        health["fleet_id"] = "other-fleet"
        report = peer_mesh_topology.build_topology_report(minimal_manifest(), route_config(), health)
        self.assertEqual(report["overall_status"], "topology_blocked")
        checks = {check["check_id"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks["route_health_identity"], "failed")

    def test_forbidden_manifest_field_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_topology.validate_manifest(manifest)

    def test_absolute_route_config_path_is_rejected(self) -> None:
        manifest = minimal_manifest()
        manifest["route_config_path"] = "C:/private/route-config.json"
        with self.assertRaises(ValueError):
            peer_mesh_topology.validate_manifest(manifest)

    def test_forbidden_route_health_field_is_rejected(self) -> None:
        health = route_health("healthy")
        health["shell"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_topology.validate_route_health_report(health)

    def test_cli_writes_report(self) -> None:
        report_path = REPO_ROOT / "examples" / "peer-topology-report.synthetic.json"
        exit_code = peer_mesh_topology.main(
            [
                "--manifest",
                str(REPO_ROOT / "examples" / "peer-topology-manifest.synthetic.json"),
                "--artifact-root",
                str(REPO_ROOT),
                "--now",
                "2026-06-04T10:00:06Z",
                "--output",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["overall_status"], "topology_blocked")


if __name__ == "__main__":
    unittest.main()
