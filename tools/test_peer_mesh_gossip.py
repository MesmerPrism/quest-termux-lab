#!/usr/bin/env python3
"""Tests for the peer gossip preparation slice."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOSSIP_PATH = REPO_ROOT / "tools" / "peer_mesh_gossip.py"


def load_module():
    spec = importlib.util.spec_from_file_location("peer_mesh_gossip", GOSSIP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_gossip")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_gossip"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_gossip = load_module()


def envelope(observed_at: str = "2026-06-04T10:00:00Z", sequence: int = 1) -> dict:
    return {
        "schema": "quest-termux-lab.peer-gossip-envelope.v1",
        "fleet_id": "synthetic-lab-fleet",
        "message_id": f"gossip-alpha-{sequence}",
        "sender_agent_id": "quest-agent-alpha",
        "created_at": observed_at,
        "hop_ttl": 2,
        "observations": [
            {
                "agent_id": "quest-agent-alpha",
                "observed_at": observed_at,
                "heard_from_agent_id": "quest-agent-alpha",
                "heartbeat_sequence": sequence,
                "agent_alive": True,
                "central_reachable": True,
                "local_adb_available": False,
                "local_adb_shell_uid": None,
                "battery_percent": 80,
                "last_command_status": "completed",
                "stale_after_seconds": 30,
                "summary_hash": "synthetic",
            }
        ],
        "authority_boundary": ["status only"],
    }


class PeerGossipTests(unittest.TestCase):
    def test_examples_parse(self) -> None:
        expected = {
            "peer-gossip-envelope.synthetic.json": "quest-termux-lab.peer-gossip-envelope.v1",
            "peer-gossip-envelope.from-heartbeat.synthetic.json": "quest-termux-lab.peer-gossip-envelope.v1",
            "peer-mesh-summary.synthetic.json": "quest-termux-lab.peer-mesh-summary.v1",
            "peer-node-config.synthetic.json": "quest-termux-lab.peer-node-config.v1",
            "session-recipe.peer-gossip-status-mesh.json": "quest-termux-lab.session-recipe.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))
                self.assertEqual(payload["schema"], schema)

    def test_merge_keeps_newer_observation(self) -> None:
        state = peer_mesh_gossip.GossipState("synthetic-lab-fleet", "quest-agent-alpha")
        state.merge_envelope(envelope("2026-06-04T10:00:00Z", 1))
        newer = envelope("2026-06-04T10:00:01Z", 2)
        newer["observations"][0]["battery_percent"] = 77
        state.merge_envelope(newer)
        summary = state.summary(now=datetime(2026, 6, 4, 10, 0, 5, tzinfo=timezone.utc))
        self.assertEqual(summary["known_peer_count"], 1)
        self.assertEqual(summary["peers"][0]["battery_percent"], 77)
        self.assertEqual(summary["peers"][0]["status"], "alive")

    def test_stale_status_is_computed(self) -> None:
        state = peer_mesh_gossip.GossipState("synthetic-lab-fleet", "quest-agent-alpha")
        state.merge_envelope(envelope("2026-06-04T10:00:00Z", 1))
        summary = state.summary(now=datetime(2026, 6, 4, 10, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(summary["peers"][0]["status"], "stale")

    def test_rejects_command_like_payload(self) -> None:
        bad = envelope()
        bad["command_id"] = "cmd-cross-peer-shell"
        state = peer_mesh_gossip.GossipState("synthetic-lab-fleet", "quest-agent-alpha")
        with self.assertRaises(ValueError):
            state.merge_envelope(bad)

    def test_envelope_from_heartbeat_strips_command_and_adb_target(self) -> None:
        heartbeat = json.loads((REPO_ROOT / "examples" / "fleet-agent-heartbeat.synthetic.json").read_text(encoding="utf-8"))
        gossip = peer_mesh_gossip.envelope_from_heartbeat(
            heartbeat,
            sender_agent_id="quest-agent-alpha",
            message_id="gossip-from-heartbeat-test",
            hop_ttl=2,
            stale_after_seconds=30,
        )
        text = json.dumps(gossip)
        self.assertNotIn("cmd-agent-status-001", text)
        self.assertNotIn("127.0.0.1:5555", text)
        self.assertEqual(gossip["observations"][0]["heartbeat_sequence"], 42)
        self.assertFalse(gossip["observations"][0]["local_adb_available"])

    def test_relay_decrements_ttl_and_updates_heard_from(self) -> None:
        relayed = peer_mesh_gossip.relay_envelope(envelope(), "quest-agent-beta", "gossip-beta-relay-test")
        self.assertEqual(relayed["hop_ttl"], 1)
        self.assertEqual(relayed["sender_agent_id"], "quest-agent-beta")
        self.assertEqual(relayed["observations"][0]["heard_from_agent_id"], "quest-agent-beta")

    def test_relay_rejects_zero_ttl(self) -> None:
        source = envelope()
        source["hop_ttl"] = 0
        with self.assertRaises(ValueError):
            peer_mesh_gossip.relay_envelope(source, "quest-agent-beta", "gossip-beta-relay-test")

    def test_directory_merge_skips_invalid_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.json").write_text(json.dumps(envelope()), encoding="utf-8")
            bad = envelope()
            bad["command_id"] = "cmd-not-gossip"
            (root / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
            state = peer_mesh_gossip.GossipState("synthetic-lab-fleet", "quest-agent-alpha")
            for path in sorted(root.glob("*.json")):
                try:
                    state.merge_envelope(json.loads(path.read_text(encoding="utf-8")))
                except ValueError:
                    pass
            self.assertEqual(state.summary(now=datetime(2026, 6, 4, 10, 0, 5, tzinfo=timezone.utc))["known_peer_count"], 1)
            self.assertEqual(state.forbidden_message_count, 1)
        self.assertEqual(state.forbidden_message_count, 1)

    def test_rejects_fleet_mismatch(self) -> None:
        bad = envelope()
        bad["fleet_id"] = "other-fleet"
        state = peer_mesh_gossip.GossipState("synthetic-lab-fleet", "quest-agent-alpha")
        with self.assertRaises(ValueError):
            state.merge_envelope(bad)


if __name__ == "__main__":
    unittest.main()
