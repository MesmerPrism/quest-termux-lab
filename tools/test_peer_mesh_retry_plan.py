#!/usr/bin/env python3
"""Tests for peer gossip retry/backoff planning."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RETRY_PATH = REPO_ROOT / "tools" / "peer_mesh_retry_plan.py"


def load_module():
    sys.path.insert(0, str(RETRY_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_retry_plan", RETRY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_retry_plan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_retry_plan"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_retry_plan = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


class PeerRetryPlanTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-retry-policy.synthetic.json": "quest-termux-lab.peer-retry-policy.v1",
            "peer-retry-plan.synthetic.json": "quest-termux-lab.peer-retry-plan.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = load_example(name)
                self.assertEqual(payload["schema"], schema)

    def test_no_previous_attempt_is_due_now(self) -> None:
        plan = peer_mesh_retry_plan.build_retry_plan(
            load_example("peer-delivery-state.synthetic.json"),
            load_example("peer-retry-policy.synthetic.json"),
            now_text="2026-06-04T10:00:01Z",
        )
        retry = plan["retries"][0]
        self.assertEqual(retry["decision"], "due_now")
        self.assertEqual(retry["next_attempt_at"], "2026-06-04T10:00:01Z")
        self.assertEqual(plan["summary"]["due_now_count"], 1)

    def test_backoff_waits_until_due(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        delivery = state["deliveries"][0]
        delivery["attempt_count"] = 1
        delivery["last_attempt_at"] = "2026-06-04T10:00:05Z"
        delivery["last_error"] = "synthetic no response"
        plan = peer_mesh_retry_plan.build_retry_plan(
            state,
            load_example("peer-retry-policy.synthetic.json"),
            now_text="2026-06-04T10:00:10Z",
        )
        retry = plan["retries"][0]
        self.assertEqual(retry["decision"], "waiting_backoff")
        self.assertEqual(retry["next_attempt_at"], "2026-06-04T10:00:15Z")
        self.assertEqual(retry["backoff_delay_seconds"], 10)

    def test_backoff_elapsed_is_due_now(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        delivery = state["deliveries"][0]
        delivery["attempt_count"] = 1
        delivery["last_attempt_at"] = "2026-06-04T10:00:05Z"
        delivery["last_error"] = "synthetic no response"
        plan = peer_mesh_retry_plan.build_retry_plan(
            state,
            load_example("peer-retry-policy.synthetic.json"),
            now_text="2026-06-04T10:00:15Z",
        )
        self.assertEqual(plan["retries"][0]["decision"], "due_now")

    def test_max_attempts_reached(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        delivery = state["deliveries"][0]
        delivery["attempt_count"] = 3
        delivery["last_attempt_at"] = "2026-06-04T10:00:05Z"
        delivery["last_error"] = "synthetic no response"
        plan = peer_mesh_retry_plan.build_retry_plan(
            state,
            load_example("peer-retry-policy.synthetic.json"),
            now_text="2026-06-04T10:00:30Z",
        )
        self.assertEqual(plan["retries"][0]["decision"], "max_attempts_reached")

    def test_non_retryable_error_is_not_due(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        delivery = state["deliveries"][0]
        delivery["attempt_count"] = 1
        delivery["last_attempt_at"] = "2026-06-04T10:00:05Z"
        delivery["last_error"] = "permanent_route_error"
        plan = peer_mesh_retry_plan.build_retry_plan(
            state,
            load_example("peer-retry-policy.synthetic.json"),
            now_text="2026-06-04T10:00:30Z",
        )
        self.assertEqual(plan["retries"][0]["decision"], "non_retryable_error")

    def test_terminal_delivery_is_not_retried(self) -> None:
        plan = peer_mesh_retry_plan.build_retry_plan(
            load_example("peer-delivery-state.accepted.synthetic.json"),
            load_example("peer-retry-policy.synthetic.json"),
            now_text="2026-06-04T10:00:30Z",
        )
        self.assertEqual(plan["retries"][0]["decision"], "terminal")
        self.assertEqual(plan["summary"]["terminal_count"], 1)

    def test_expired_delivery_is_not_retried(self) -> None:
        plan = peer_mesh_retry_plan.build_retry_plan(
            load_example("peer-delivery-state.synthetic.json"),
            load_example("peer-retry-policy.synthetic.json"),
            now_text="2026-06-04T10:06:00Z",
        )
        self.assertEqual(plan["retries"][0]["decision"], "expired")
        self.assertEqual(plan["summary"]["expired_count"], 1)

    def test_policy_mismatch_is_rejected(self) -> None:
        policy = load_example("peer-retry-policy.synthetic.json")
        policy["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_retry_plan.build_retry_plan(
                load_example("peer-delivery-state.synthetic.json"),
                policy,
                now_text="2026-06-04T10:00:01Z",
            )

    def test_forbidden_policy_field_is_rejected(self) -> None:
        policy = load_example("peer-retry-policy.synthetic.json")
        policy["token"] = "not-public"
        with self.assertRaises(ValueError):
            peer_mesh_retry_plan.validate_policy(policy)


if __name__ == "__main__":
    unittest.main()
