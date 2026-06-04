#!/usr/bin/env python3
"""Tests for the no-send peer sender dry-run simulator."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SEND_PATH = REPO_ROOT / "tools" / "peer_mesh_send_dry_run.py"


def load_module():
    sys.path.insert(0, str(SEND_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_send_dry_run", SEND_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_send_dry_run")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_send_dry_run"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_send_dry_run = load_module()


def load_example(name: str) -> dict:
    return json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))


class PeerSendDryRunTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-send-dry-run-outcomes.synthetic.json": "quest-termux-lab.peer-send-dry-run-outcomes.v1",
            "peer-send-dry-run-report.synthetic.json": "quest-termux-lab.peer-send-dry-run-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = load_example(name)
                self.assertEqual(payload["schema"], schema)

    def test_accepted_outcome_updates_delivery_state(self) -> None:
        report = peer_mesh_send_dry_run.run_dry_run(
            load_example("peer-delivery-state.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            load_example("peer-send-dry-run-outcomes.synthetic.json"),
            now_text="2026-06-04T10:00:05Z",
        )
        action = report["actions"][0]
        delivery = report["updated_delivery_state"]["deliveries"][0]
        self.assertEqual(action["simulated_outcome"], "accepted")
        self.assertEqual(action["delivery_state_after"], "accepted")
        self.assertEqual(delivery["state"], "accepted")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertEqual(report["summary"]["accepted_count"], 1)

    def test_missing_outcome_records_no_response(self) -> None:
        outcomes = load_example("peer-send-dry-run-outcomes.synthetic.json")
        outcomes["outcomes"] = []
        report = peer_mesh_send_dry_run.run_dry_run(
            load_example("peer-delivery-state.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            outcomes,
            now_text="2026-06-04T10:00:05Z",
        )
        action = report["actions"][0]
        delivery = report["updated_delivery_state"]["deliveries"][0]
        self.assertEqual(action["simulated_outcome"], "no_response")
        self.assertEqual(delivery["state"], "pending")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertEqual(delivery["last_error"], "no synthetic outcome configured")

    def test_rejected_outcome_updates_delivery_state(self) -> None:
        outcomes = load_example("peer-send-dry-run-outcomes.synthetic.json")
        outcomes["outcomes"][0]["result"] = "rejected"
        outcomes["outcomes"][0]["reason"] = "http_400_replay_conflict"
        report = peer_mesh_send_dry_run.run_dry_run(
            load_example("peer-delivery-state.synthetic.json"),
            load_example("peer-route-config.synthetic.json"),
            outcomes,
            now_text="2026-06-04T10:00:05Z",
        )
        delivery = report["updated_delivery_state"]["deliveries"][0]
        self.assertEqual(delivery["state"], "rejected")
        self.assertEqual(delivery["last_error"], "http_400_replay_conflict")
        self.assertEqual(report["summary"]["rejected_count"], 1)

    def test_non_ready_dispatch_is_not_sent(self) -> None:
        state = load_example("peer-delivery-state.accepted.synthetic.json")
        report = peer_mesh_send_dry_run.run_dry_run(
            state,
            load_example("peer-route-config.synthetic.json"),
            load_example("peer-send-dry-run-outcomes.synthetic.json"),
            now_text="2026-06-04T10:00:06Z",
        )
        self.assertEqual(report["actions"][0]["simulated_outcome"], "not_sent")
        self.assertEqual(report["actions"][0]["dispatch_decision"], "skipped_terminal")
        self.assertEqual(report["summary"]["not_sent_count"], 1)

    def test_outcome_fleet_mismatch_is_rejected(self) -> None:
        outcomes = load_example("peer-send-dry-run-outcomes.synthetic.json")
        outcomes["fleet_id"] = "other-fleet"
        with self.assertRaises(ValueError):
            peer_mesh_send_dry_run.run_dry_run(
                load_example("peer-delivery-state.synthetic.json"),
                load_example("peer-route-config.synthetic.json"),
                outcomes,
                now_text="2026-06-04T10:00:05Z",
            )

    def test_duplicate_outcome_target_message_is_rejected(self) -> None:
        outcomes = load_example("peer-send-dry-run-outcomes.synthetic.json")
        outcomes["outcomes"].append(dict(outcomes["outcomes"][0]))
        with self.assertRaises(ValueError):
            peer_mesh_send_dry_run.validate_outcomes(outcomes)


if __name__ == "__main__":
    unittest.main()
