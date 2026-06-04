#!/usr/bin/env python3
"""Tests for the loopback-only peer HTTP simulator."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
HTTP_SIM_PATH = REPO_ROOT / "tools" / "peer_mesh_http_sim.py"


def load_module():
    sys.path.insert(0, str(HTTP_SIM_PATH.parent))
    spec = importlib.util.spec_from_file_location("peer_mesh_http_sim", HTTP_SIM_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load peer_mesh_http_sim")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peer_mesh_http_sim"] = module
    spec.loader.exec_module(module)
    return module


peer_mesh_http_sim = load_module()


def request_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - loopback-only test server.
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class PeerHttpSimTests(unittest.TestCase):
    def setUp(self) -> None:
        state = peer_mesh_http_sim.PeerHttpState(
            fleet_id="synthetic-lab-fleet",
            observer_agent_id="quest-agent-alpha",
        )
        self.server = peer_mesh_http_sim.PeerHttpServer(("127.0.0.1", 0), state, quiet=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}{peer_mesh_http_sim.API_PREFIX}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_config_example_parse(self) -> None:
        expected = {
            "peer-http-node-config.synthetic.json": "quest-termux-lab.peer-http-node-config.v1",
            "peer-http-gossip-receipt.synthetic.json": "quest-termux-lab.peer-http-gossip-receipt.v1",
            "peer-http-summary.synthetic.json": "quest-termux-lab.peer-http-summary.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))
                self.assertEqual(payload["schema"], schema)

    def test_accepts_gossip_and_summarizes(self) -> None:
        gossip = json.loads((REPO_ROOT / "examples" / "peer-gossip-envelope.synthetic.json").read_text(encoding="utf-8"))
        status, accepted = request_json(f"{self.base_url}/gossip", gossip)
        self.assertEqual(status, 200)
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["schema"], "quest-termux-lab.peer-http-gossip-receipt.v1")
        self.assertTrue(accepted["applied"])
        self.assertEqual(accepted["known_peer_count"], 2)

        status, summary = request_json(f"{self.base_url}/summary")
        self.assertEqual(status, 200)
        self.assertEqual(summary["schema"], "quest-termux-lab.peer-http-summary.v1")
        self.assertEqual(summary["peer_summary"]["known_peer_count"], 2)
        self.assertEqual(summary["accepted_message_count"], 1)
        self.assertEqual(summary["duplicate_message_count"], 0)
        self.assertEqual(summary["rejected_message_count"], 0)
        self.assertEqual(summary["seen_message_count"], 1)
        self.assertEqual(summary["transport_scope"], "loopback_http_simulator")

    def test_duplicate_gossip_is_idempotent(self) -> None:
        gossip = json.loads((REPO_ROOT / "examples" / "peer-gossip-envelope.synthetic.json").read_text(encoding="utf-8"))
        first_status, first_receipt = request_json(f"{self.base_url}/gossip", gossip)
        duplicate_status, duplicate_receipt = request_json(f"{self.base_url}/gossip", gossip)
        self.assertEqual(first_status, 200)
        self.assertEqual(first_receipt["status"], "accepted")
        self.assertEqual(duplicate_status, 200)
        self.assertEqual(duplicate_receipt["status"], "duplicate")
        self.assertFalse(duplicate_receipt["applied"])

        status, summary = request_json(f"{self.base_url}/summary")
        self.assertEqual(status, 200)
        self.assertEqual(summary["accepted_message_count"], 1)
        self.assertEqual(summary["duplicate_message_count"], 1)
        self.assertEqual(summary["rejected_message_count"], 0)
        self.assertEqual(summary["seen_message_count"], 1)

    def test_conflicting_replay_is_rejected(self) -> None:
        gossip = json.loads((REPO_ROOT / "examples" / "peer-gossip-envelope.synthetic.json").read_text(encoding="utf-8"))
        replay = json.loads(json.dumps(gossip))
        replay["observations"][0]["battery_percent"] = 55
        status, first = request_json(f"{self.base_url}/gossip", gossip)
        replay_status, rejected = request_json(f"{self.base_url}/gossip", replay)
        self.assertEqual(status, 200)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(replay_status, 400)
        self.assertEqual(rejected["status"], "error")
        self.assertIn("replay conflict", rejected["error"])

        status, summary = request_json(f"{self.base_url}/summary")
        self.assertEqual(status, 200)
        self.assertEqual(summary["accepted_message_count"], 1)
        self.assertEqual(summary["duplicate_message_count"], 0)
        self.assertEqual(summary["rejected_message_count"], 1)

    def test_seen_message_replay_window_expires(self) -> None:
        clock = {"now": 0.0}
        state = peer_mesh_http_sim.PeerHttpState(
            fleet_id="synthetic-lab-fleet",
            observer_agent_id="quest-agent-alpha",
            seen_message_ttl_seconds=1.0,
            now_func=lambda: clock["now"],
        )
        gossip = json.loads((REPO_ROOT / "examples" / "peer-gossip-envelope.synthetic.json").read_text(encoding="utf-8"))
        first = state.accept_gossip(gossip)
        duplicate = state.accept_gossip(gossip)
        clock["now"] = 2.0
        accepted_after_expiry = state.accept_gossip(gossip)
        summary = state.summary()
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(accepted_after_expiry["status"], "accepted")
        self.assertEqual(summary["accepted_message_count"], 2)
        self.assertEqual(summary["duplicate_message_count"], 1)
        self.assertEqual(summary["expired_seen_message_count"], 1)
        self.assertEqual(summary["seen_message_count"], 1)
        self.assertEqual(summary["seen_message_ttl_seconds"], 1.0)

    def test_rejects_heartbeat_and_counts_rejection(self) -> None:
        heartbeat = json.loads((REPO_ROOT / "examples" / "fleet-agent-heartbeat.synthetic.json").read_text(encoding="utf-8"))
        status, rejected = request_json(f"{self.base_url}/gossip", heartbeat)
        self.assertEqual(status, 400)
        self.assertEqual(rejected["status"], "error")

        status, summary = request_json(f"{self.base_url}/summary")
        self.assertEqual(status, 200)
        self.assertEqual(summary["accepted_message_count"], 0)
        self.assertEqual(summary["duplicate_message_count"], 0)
        self.assertEqual(summary["rejected_message_count"], 1)

    def test_rejects_command_like_gossip_payload(self) -> None:
        gossip = json.loads((REPO_ROOT / "examples" / "peer-gossip-envelope.synthetic.json").read_text(encoding="utf-8"))
        gossip["command_id"] = "cmd-peer-shell-not-allowed"
        status, rejected = request_json(f"{self.base_url}/gossip", gossip)
        self.assertEqual(status, 400)
        self.assertIn("command-like", rejected["error"])

    def test_has_no_command_route(self) -> None:
        status, rejected = request_json(f"{self.base_url}/commands", {"schema": "not-supported"})
        self.assertEqual(status, 404)
        self.assertEqual(rejected["status"], "error")


if __name__ == "__main__":
    unittest.main()
