#!/usr/bin/env python3
"""Tests for the peer mesh file-drop round simulator."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUND_PATH = REPO_ROOT / "tools" / "peer_mesh_round.py"


def load_module():
    sys.path.insert(0, str(ROUND_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_round", ROUND_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_round")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_round"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_round = load_module()


class PeerMeshRoundTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "fleet-agent-heartbeat.beta.synthetic.json": "quest-termux-lab.fleet-agent-heartbeat.v1",
            "fleet-agent-heartbeat.gamma.synthetic.json": "quest-termux-lab.fleet-agent-heartbeat.v1",
            "peer-mesh-round-scenario.synthetic.json": "quest-termux-lab.peer-mesh-round-scenario.v1",
            "peer-mesh-round-report.synthetic.json": "quest-termux-lab.peer-mesh-round-report.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))
                self.assertEqual(payload["schema"], schema)

    def test_round_relays_status_without_command_or_adb_target(self) -> None:
        scenario = json.loads((REPO_ROOT / "examples" / "peer-mesh-round-scenario.synthetic.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            report = peer_mesh_round.simulate_round(scenario, repo_root=REPO_ROOT, output_root=Path(tmp))
            self.assertEqual(report["node_count"], 3)
            self.assertEqual(report["direct_delivery_count"], 2)
            self.assertEqual(report["relayed_envelope_count"], 1)

            gamma_summary = json.loads(
                (Path(tmp) / scenario["round_id"] / "quest-agent-gamma" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(gamma_summary["known_peer_count"], 3)
            alpha = next(peer for peer in gamma_summary["peers"] if peer["agent_id"] == "quest-agent-alpha")
            self.assertEqual(alpha["heard_from_agent_id"], "quest-agent-beta")

            for path in (Path(tmp) / scenario["round_id"]).rglob("*.json"):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("cmd-agent-status-001", text)
                self.assertNotIn("cmd-beta-status-001", text)
                self.assertNotIn("cmd-gamma-status-001", text)
                self.assertNotIn("127.0.0.1:5555", text)

    def test_scenario_rejects_absolute_heartbeat_path(self) -> None:
        scenario = json.loads((REPO_ROOT / "examples" / "peer-mesh-round-scenario.synthetic.json").read_text(encoding="utf-8"))
        scenario["heartbeats"][0]["path"] = str(REPO_ROOT / "examples" / "fleet-agent-heartbeat.synthetic.json")
        with self.assertRaises(ValueError):
            peer_mesh_round.validate_scenario(scenario)

    def test_scenario_rejects_parent_traversal_heartbeat_path(self) -> None:
        scenario = json.loads((REPO_ROOT / "examples" / "peer-mesh-round-scenario.synthetic.json").read_text(encoding="utf-8"))
        scenario["heartbeats"][0]["path"] = "../outside.json"
        with self.assertRaises(ValueError):
            peer_mesh_round.validate_scenario(scenario)


if __name__ == "__main__":
    unittest.main()
