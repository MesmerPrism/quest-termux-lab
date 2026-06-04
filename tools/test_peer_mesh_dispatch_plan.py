#!/usr/bin/env python3
"""Tests for configured-peer dispatch-plan dry runs."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DISPATCH_PATH = REPO_ROOT / "tools" / "peer_mesh_dispatch_plan.py"


def load_module():
    sys.path.insert(0, str(DISPATCH_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_dispatch_plan", DISPATCH_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_dispatch_plan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_dispatch_plan"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_dispatch_plan = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


class PeerDispatchPlanTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-route-config.synthetic.json": "quest-termux-lab.peer-route-config.v1",
            "peer-dispatch-plan.synthetic.json": "quest-termux-lab.peer-dispatch-plan.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = load_example(name)
                self.assertEqual(payload["schema"], schema)

    def test_ready_http_dispatch_plan(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        config = load_example("peer-route-config.synthetic.json")
        plan = peer_mesh_dispatch_plan.build_dispatch_plan(state, config, now_text="2026-06-04T10:00:01Z")
        dispatch = plan["dispatches"][0]
        self.assertEqual(dispatch["decision"], "ready")
        self.assertEqual(dispatch["transport_mode"], "loopback_http_simulator")
        self.assertEqual(dispatch["method"], "post_gossip")
        self.assertEqual(dispatch["route_target"], "http://127.0.0.1:8788/api/peer/v1/gossip")
        self.assertEqual(plan["summary"]["ready_count"], 1)

    def test_terminal_delivery_is_skipped(self) -> None:
        state = load_example("peer-delivery-state.accepted.synthetic.json")
        config = load_example("peer-route-config.synthetic.json")
        plan = peer_mesh_dispatch_plan.build_dispatch_plan(state, config, now_text="2026-06-04T10:00:06Z")
        self.assertEqual(plan["dispatches"][0]["decision"], "skipped_terminal")
        self.assertEqual(plan["summary"]["skipped_terminal_count"], 1)

    def test_expired_delivery_is_not_ready(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        config = load_example("peer-route-config.synthetic.json")
        plan = peer_mesh_dispatch_plan.build_dispatch_plan(state, config, now_text="2026-06-04T10:05:01Z")
        self.assertEqual(plan["dispatches"][0]["decision"], "expired")
        self.assertEqual(plan["summary"]["expired_count"], 1)

    def test_missing_route_is_reported(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        config = load_example("peer-route-config.synthetic.json")
        config["routes"] = []
        plan = peer_mesh_dispatch_plan.build_dispatch_plan(state, config, now_text="2026-06-04T10:00:01Z")
        self.assertEqual(plan["dispatches"][0]["decision"], "missing_route")
        self.assertEqual(plan["summary"]["missing_route_count"], 1)

    def test_disabled_route_is_reported(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        config = load_example("peer-route-config.synthetic.json")
        config["routes"][0]["transport_mode"] = "disabled"
        config["routes"][0].pop("gossip_endpoint")
        plan = peer_mesh_dispatch_plan.build_dispatch_plan(state, config, now_text="2026-06-04T10:00:01Z")
        self.assertEqual(plan["dispatches"][0]["decision"], "route_disabled")
        self.assertEqual(plan["summary"]["route_disabled_count"], 1)

    def test_rejects_non_loopback_http_route(self) -> None:
        config = load_example("peer-route-config.synthetic.json")
        config["routes"][0]["gossip_endpoint"] = "http://example.invalid/api/peer/v1/gossip"
        with self.assertRaises(ValueError):
            peer_mesh_dispatch_plan.validate_route_config(config)

    def test_rejects_traversing_file_drop_route(self) -> None:
        config = load_example("peer-route-config.synthetic.json")
        config["routes"][0] = {
            "target_agent_id": "quest-agent-beta",
            "transport_mode": "file_drop_simulator",
            "target_inbox_dir": "../outside",
        }
        with self.assertRaises(ValueError):
            peer_mesh_dispatch_plan.validate_route_config(config)


if __name__ == "__main__":
    unittest.main()
