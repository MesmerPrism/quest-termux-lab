#!/usr/bin/env python3
"""Tests for peer route-health inference."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTE_HEALTH_PATH = REPO_ROOT / "tools" / "peer_mesh_route_health.py"


def load_module():
    sys.path.insert(0, str(ROUTE_HEALTH_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_route_health", ROUTE_HEALTH_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_route_health")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_route_health"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_route_health = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


class PeerRouteHealthTests(unittest.TestCase):
    def test_example_parses(self) -> None:
        payload = load_example("peer-route-health-report.synthetic.json")
        self.assertEqual(payload["schema"], "quest-termux-lab.peer-route-health-report.v1")

    def test_accepted_send_outcome_marks_route_healthy(self) -> None:
        report = peer_mesh_route_health.build_route_health_report(
            load_example("peer-route-config.synthetic.json"),
            send_report=load_example("peer-send-dry-run-report.synthetic.json"),
            retry_plan=load_example("peer-retry-plan.synthetic.json"),
            now_text="2026-06-04T10:00:05Z",
        )
        self.assertEqual(report["routes"][0]["status"], "healthy")
        self.assertEqual(report["routes"][0]["latest_simulated_outcome"], "accepted")
        self.assertEqual(report["summary"]["healthy_count"], 1)
        self.assertEqual(report["summary"]["unknown_count"], 1)

    def test_no_response_with_waiting_retry_is_degraded(self) -> None:
        send_report = load_example("peer-send-dry-run-report.synthetic.json")
        send_report["actions"][0]["simulated_outcome"] = "no_response"
        send_report["actions"][0]["delivery_state_after"] = "pending"
        retry_plan = load_example("peer-retry-plan.synthetic.json")
        retry_plan["retries"][0]["decision"] = "waiting_backoff"
        retry_plan["retries"][0]["next_attempt_at"] = "2026-06-04T10:00:15Z"
        report = peer_mesh_route_health.build_route_health_report(
            load_example("peer-route-config.synthetic.json"),
            send_report=send_report,
            retry_plan=retry_plan,
            now_text="2026-06-04T10:00:10Z",
        )
        self.assertEqual(report["routes"][0]["status"], "degraded")
        self.assertEqual(report["routes"][0]["retry_decision"], "waiting_backoff")

    def test_rejected_with_max_attempts_is_unavailable(self) -> None:
        send_report = load_example("peer-send-dry-run-report.synthetic.json")
        send_report["actions"][0]["simulated_outcome"] = "rejected"
        send_report["actions"][0]["delivery_state_after"] = "rejected"
        retry_plan = load_example("peer-retry-plan.synthetic.json")
        retry_plan["retries"][0]["decision"] = "max_attempts_reached"
        report = peer_mesh_route_health.build_route_health_report(
            load_example("peer-route-config.synthetic.json"),
            send_report=send_report,
            retry_plan=retry_plan,
            now_text="2026-06-04T10:00:30Z",
        )
        self.assertEqual(report["routes"][0]["status"], "unavailable")

    def test_disabled_route_is_disabled_without_probe(self) -> None:
        config = load_example("peer-route-config.synthetic.json")
        config["routes"].append({"target_agent_id": "quest-agent-delta", "transport_mode": "disabled"})
        report = peer_mesh_route_health.build_route_health_report(config, now_text="2026-06-04T10:00:05Z")
        delta = [route for route in report["routes"] if route["target_agent_id"] == "quest-agent-delta"][0]
        self.assertEqual(delta["status"], "disabled")
        self.assertEqual(report["summary"]["disabled_count"], 1)

    def test_unconfigured_action_is_counted_not_added_as_route(self) -> None:
        send_report = load_example("peer-send-dry-run-report.synthetic.json")
        action = dict(send_report["actions"][0])
        action["target_agent_id"] = "quest-agent-unconfigured"
        send_report["actions"].append(action)
        report = peer_mesh_route_health.build_route_health_report(
            load_example("peer-route-config.synthetic.json"),
            send_report=send_report,
            now_text="2026-06-04T10:00:05Z",
        )
        self.assertEqual(report["summary"]["unconfigured_action_count"], 1)
        self.assertNotIn("quest-agent-unconfigured", [route["target_agent_id"] for route in report["routes"]])

    def test_retry_only_due_now_is_degraded(self) -> None:
        report = peer_mesh_route_health.build_route_health_report(
            load_example("peer-route-config.synthetic.json"),
            retry_plan=load_example("peer-retry-plan.synthetic.json"),
            now_text="2026-06-04T10:00:01Z",
        )
        self.assertEqual(report["routes"][0]["status"], "degraded")
        self.assertEqual(report["routes"][0]["retry_decision"], "due_now")

    def test_fleet_mismatch_is_rejected(self) -> None:
        send_report = load_example("peer-send-dry-run-report.synthetic.json")
        send_report["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_route_health.build_route_health_report(
                load_example("peer-route-config.synthetic.json"),
                send_report=send_report,
                now_text="2026-06-04T10:00:05Z",
            )

    def test_forbidden_send_report_field_is_rejected(self) -> None:
        send_report = load_example("peer-send-dry-run-report.synthetic.json")
        send_report["shell_command"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_route_health.validate_send_report(send_report)


if __name__ == "__main__":
    unittest.main()
