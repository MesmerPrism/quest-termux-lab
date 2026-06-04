#!/usr/bin/env python3
"""Tests for the peer gossip delivery-state simulator."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_PATH = REPO_ROOT / "tools" / "peer_mesh_delivery.py"


def load_module():
    sys.path.insert(0, str(DELIVERY_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_delivery", DELIVERY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_delivery")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_delivery"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_delivery = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


class PeerDeliveryTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-delivery-state.synthetic.json": "quest-termux-lab.peer-delivery-state.v1",
            "peer-delivery-state.accepted.synthetic.json": "quest-termux-lab.peer-delivery-state.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = load_example(name)
                self.assertEqual(payload["schema"], schema)

    def test_apply_accept_receipt_updates_delivery(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        receipt = load_example("peer-http-gossip-receipt.synthetic.json")
        updated = peer_mesh_delivery.apply_receipt(state, receipt, target_agent_id="quest-agent-beta")
        delivery = updated["deliveries"][0]
        self.assertEqual(delivery["state"], "accepted")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertEqual(delivery["last_receipt_status"], "accepted")
        self.assertEqual(updated["summary"]["accepted_count"], 1)
        self.assertEqual(updated["summary"]["pending_count"], 0)

    def test_duplicate_receipt_sets_duplicate(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        receipt = load_example("peer-http-gossip-receipt.synthetic.json")
        receipt["status"] = "duplicate"
        receipt["applied"] = False
        receipt["reason"] = "message_id already accepted"
        updated = peer_mesh_delivery.apply_receipt(state, receipt, target_agent_id="quest-agent-beta")
        delivery = updated["deliveries"][0]
        self.assertEqual(delivery["state"], "duplicate")
        self.assertEqual(delivery["last_error"], "message_id already accepted")
        self.assertEqual(updated["summary"]["duplicate_count"], 1)

    def test_apply_error_sets_rejected(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        updated = peer_mesh_delivery.apply_error(
            state,
            target_agent_id="quest-agent-beta",
            message_id="gossip-alpha-001",
            reason="http_400_replay_conflict",
            observed_at="2026-06-04T10:00:06Z",
        )
        delivery = updated["deliveries"][0]
        self.assertEqual(delivery["state"], "rejected")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertEqual(delivery["last_error"], "http_400_replay_conflict")
        self.assertEqual(updated["summary"]["rejected_count"], 1)

    def test_expire_pending_delivery(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        expired = peer_mesh_delivery.expire_pending(state, now_text="2026-06-04T10:05:01Z")
        delivery = expired["deliveries"][0]
        self.assertEqual(delivery["state"], "expired")
        self.assertEqual(delivery["last_error"], "delivery expired before receipt")
        self.assertEqual(expired["summary"]["expired_count"], 1)

    def test_rejects_unknown_delivery(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        receipt = load_example("peer-http-gossip-receipt.synthetic.json")
        with self.assertRaises(ValueError):
            peer_mesh_delivery.apply_receipt(state, receipt, target_agent_id="quest-agent-gamma")

    def test_receipt_fleet_mismatch_is_rejected(self) -> None:
        state = load_example("peer-delivery-state.synthetic.json")
        receipt = load_example("peer-http-gossip-receipt.synthetic.json")
        receipt["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_delivery.apply_receipt(state, receipt, target_agent_id="quest-agent-beta")


if __name__ == "__main__":
    unittest.main()
