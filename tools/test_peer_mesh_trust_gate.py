#!/usr/bin/env python3
"""Tests for configured-peer trust reports."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRUST_PATH = REPO_ROOT / "tools" / "peer_mesh_trust_gate.py"


def load_module():
    sys.path.insert(0, str(TRUST_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_trust_gate", TRUST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_trust_gate")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_trust_gate"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_trust_gate = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


def synthetic_ready_bundle() -> dict:
    bundle = load_example("peer-lab-bundle-report.synthetic.json")
    bundle["overall_status"] = "synthetic_ready"
    bundle["readiness_status"] = "ready"
    bundle["operator_approval_required"] = False
    bundle["operator_approval_recorded"] = False
    bundle["summary"]["ready_route_count"] = 2
    bundle["summary"]["not_ready_route_count"] = 0
    return bundle


class PeerTrustGateTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-trust-policy.synthetic.json": "quest-termux-lab.peer-trust-policy.v1",
            "peer-trust-report.synthetic.json": "quest-termux-lab.peer-trust-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                self.assertEqual(load_example(name)["schema"], schema)

    def test_public_fixture_is_untrusted_because_bundle_blocked(self) -> None:
        report = peer_mesh_trust_gate.build_trust_report(
            load_example("peer-trust-policy.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            load_example("peer-lab-bundle-report.synthetic.json"),
            [load_example("peer-gossip-envelope.synthetic.json")],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "untrusted")
        failed = [check["check_id"] for check in report["checks"] if check["status"] == "failed"]
        self.assertIn("lab_bundle_status", failed)

    def test_synthetic_ready_bundle_without_operator_review_is_trusted(self) -> None:
        policy = load_example("peer-trust-policy.synthetic.json")
        policy["operator_review_required"] = False
        report = peer_mesh_trust_gate.build_trust_report(
            policy,
            load_example("peer-route-config.synthetic.json"),
            synthetic_ready_bundle(),
            [load_example("peer-gossip-envelope.synthetic.json")],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "trusted")

    def test_operator_review_forces_manual_review_after_passed_checks(self) -> None:
        report = peer_mesh_trust_gate.build_trust_report(
            load_example("peer-trust-policy.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            synthetic_ready_bundle(),
            [load_example("peer-gossip-envelope.synthetic.json")],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "manual_review")
        manual = [check["check_id"] for check in report["checks"] if check["status"] == "manual_review"]
        self.assertEqual(manual, ["operator_review"])

    def test_unlisted_route_target_is_untrusted(self) -> None:
        policy = load_example("peer-trust-policy.synthetic.json")
        policy["operator_review_required"] = False
        policy["allowed_agent_ids"] = ["quest-agent-alpha", "quest-agent-beta"]
        report = peer_mesh_trust_gate.build_trust_report(
            policy,
            load_example("peer-route-config.synthetic.json"),
            synthetic_ready_bundle(),
            [load_example("peer-gossip-envelope.synthetic.json")],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "untrusted")
        self.assertEqual(report["configured_peers"][1]["trust_status"], "untrusted")

    def test_sample_ttl_above_policy_is_untrusted(self) -> None:
        policy = load_example("peer-trust-policy.synthetic.json")
        policy["operator_review_required"] = False
        envelope = load_example("peer-gossip-envelope.synthetic.json")
        envelope["hop_ttl"] = 4
        report = peer_mesh_trust_gate.build_trust_report(
            policy,
            load_example("peer-route-config.synthetic.json"),
            synthetic_ready_bundle(),
            [envelope],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "untrusted")
        self.assertEqual(report["sample_envelopes"][0]["trust_status"], "untrusted")

    def test_missing_sample_envelope_is_untrusted(self) -> None:
        policy = load_example("peer-trust-policy.synthetic.json")
        policy["operator_review_required"] = False
        report = peer_mesh_trust_gate.build_trust_report(
            policy,
            load_example("peer-route-config.synthetic.json"),
            synthetic_ready_bundle(),
            [],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "untrusted")
        failed = [check["check_id"] for check in report["checks"] if check["status"] == "failed"]
        self.assertIn("sample_envelope_count", failed)

    def test_command_like_sample_envelope_is_untrusted_not_crash(self) -> None:
        policy = load_example("peer-trust-policy.synthetic.json")
        policy["operator_review_required"] = False
        envelope = load_example("peer-gossip-envelope.synthetic.json")
        envelope["command_id"] = "cmd-not-gossip"
        report = peer_mesh_trust_gate.build_trust_report(
            policy,
            load_example("peer-route-config.synthetic.json"),
            synthetic_ready_bundle(),
            [envelope],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "untrusted")
        self.assertEqual(report["sample_envelopes"][0]["trust_status"], "untrusted")

    def test_invalid_transport_mode_is_reported_schema_safely(self) -> None:
        policy = load_example("peer-trust-policy.synthetic.json")
        policy["operator_review_required"] = False
        route_config = load_example("peer-route-config.synthetic.json")
        route_config["routes"][0]["transport_mode"] = "bluetooth"
        route_config["routes"][0].pop("gossip_endpoint")
        report = peer_mesh_trust_gate.build_trust_report(
            policy,
            route_config,
            synthetic_ready_bundle(),
            [load_example("peer-gossip-envelope.synthetic.json")],
            now_text="2026-06-04T10:00:09Z",
        )
        self.assertEqual(report["overall_status"], "untrusted")
        self.assertEqual(report["configured_peers"][0]["transport_mode"], "bluetooth")

    def test_forbidden_policy_field_is_rejected(self) -> None:
        policy = load_example("peer-trust-policy.synthetic.json")
        policy["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_trust_gate.validate_policy(policy)


if __name__ == "__main__":
    unittest.main()
