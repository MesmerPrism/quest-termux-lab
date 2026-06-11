#!/usr/bin/env python3
"""Tests for the public-safe fleet control-plane prototype."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = REPO_ROOT / "tools" / "fleet_control_plane.py"
AGENT_PATH = REPO_ROOT / "scripts" / "termux_fleet_agent.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fleet_control_plane = load_module("fleet_control_plane", CONTROL_PATH)


def load_agent_module():
    return load_module("termux_fleet_agent", AGENT_PATH)


def future_time(seconds: int = 300) -> str:
    value = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def command(agent_id: str = "quest-agent-alpha", kind: str = "agent.status") -> dict:
    return {
        "schema": "quest-termux-lab.fleet-command-request.v1",
        "fleet_id": "synthetic-lab-fleet",
        "command_id": f"cmd-{kind.replace('.', '-')}-test",
        "target_agent_id": agent_id,
        "issued_at": future_time(-1),
        "expires_at": future_time(300),
        "idempotency_key": f"idem-{kind}",
        "kind": kind,
        "requires_local_adb_shell": False,
        "timeout_ms": 5000,
        "max_stdout_bytes": 4096,
        "max_stderr_bytes": 4096,
        "payload": {},
        "sensitivity": "public_safe",
        "requested_by": "unit-test",
        "reason": "unit test command",
    }


def update_manifest(package_name: str = "org.questtermuxlab.synthetic.panel") -> dict:
    digest = "a" * 64
    signing = "b" * 64
    return {
        "schema": "quest-termux-lab.apk-update-manifest.v1",
        "package_name": package_name,
        "version_code": 2,
        "version_name": "0.2.0",
        "apk_url": "https://example.invalid/quest-termux-lab/synthetic-panel.apk",
        "sha256": digest,
        "signing_cert_sha256": signing,
        "rollout_ring": "lab",
        "launch_after_install": True,
        "launch_component": "org.questtermuxlab.synthetic.panel/.MainActivity",
    }


def heartbeat(agent_id: str = "quest-agent-alpha") -> dict:
    return {
        "schema": "quest-termux-lab.fleet-agent-heartbeat.v1",
        "fleet_id": "synthetic-lab-fleet",
        "agent_id": agent_id,
        "sequence": 1,
        "observed_at": future_time(0),
        "agent_uptime_seconds": 1.0,
        "central_reachable": True,
        "battery_percent": None,
        "charging": None,
        "storage_free_bytes": None,
        "process_count": None,
        "active_jobs": 0,
        "last_command_id": None,
        "last_command_status": None,
        "last_error_code": None,
        "local_adb": {
            "checked": False,
            "available": False,
            "adb_target": None,
            "shell_uid": None,
            "last_success_at": None,
            "last_failure_reason": None,
        },
        "foreground": None,
    }


class FleetStateTests(unittest.TestCase):
    def test_queue_and_deliver_command_once(self) -> None:
        state = fleet_control_plane.FleetState()
        queued = state.queue_command(command())
        self.assertEqual(queued["status"], "queued")

        first = state.next_command("quest-agent-alpha")
        self.assertEqual(first["schema"], "quest-termux-lab.fleet-command-request.v1")
        self.assertEqual(first["kind"], "agent.status")

        second = state.next_command("quest-agent-alpha")
        self.assertEqual(second["schema"], "quest-termux-lab.fleet-no-command.v1")

    def test_rejects_expired_command(self) -> None:
        state = fleet_control_plane.FleetState()
        expired = command()
        expired["expires_at"] = future_time(-10)
        with self.assertRaises(ValueError):
            state.queue_command(expired)

    def test_heartbeat_summary(self) -> None:
        state = fleet_control_plane.FleetState()
        state.record_heartbeat(heartbeat())
        summary = state.summary()
        self.assertEqual(summary["agent_count"], 1)
        self.assertEqual(summary["agents"], ["quest-agent-alpha"])

    def test_duplicate_idempotency_key_is_not_queued_twice(self) -> None:
        state = fleet_control_plane.FleetState()
        first = command()
        second = command()
        second["command_id"] = "cmd-agent-status-duplicate"
        self.assertEqual(state.queue_command(first)["status"], "queued")
        duplicate = state.queue_command(second)
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(duplicate["existing_command_id"], first["command_id"])
        self.assertEqual(len(state.commands["quest-agent-alpha"]), 1)

    def test_summary_reports_local_adb_recovery_candidates(self) -> None:
        state = fleet_control_plane.FleetState()
        payload = heartbeat()
        payload["local_adb"] = {
            "checked": True,
            "available": False,
            "adb_target": "127.0.0.1:5555",
            "shell_uid": None,
            "last_success_at": None,
            "last_failure_reason": "shell_uid_not_available",
        }
        state.record_heartbeat(payload)
        summary = state.summary()
        self.assertEqual(summary["recovery_candidates"][0]["agent_id"], "quest-agent-alpha")
        self.assertEqual(
            summary["recovery_candidates"][0]["recommended_action"],
            "central_direct_adb_recovery",
        )


class AgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = load_agent_module()
        self.config = {
            "fleet_id": "synthetic-lab-fleet",
            "agent_id": "quest-agent-alpha",
            "central_url": "http://127.0.0.1:8787",
            "workspace_root": "runs/test-agent",
            "allowed_command_kinds": [
                "agent.status",
                "agent.capabilities",
                "termux.exec_allowlisted",
                "adb.self_check",
                "apk.update_verified",
                "app.launch_allowlisted",
                "android.foreground_snapshot",
                "android.logcat_slice",
            ],
            "command_aliases": {"python_version": ["python", "--version"]},
            "local_adb_enabled": False,
            "allowed_update_packages": {
                "org.questtermuxlab.synthetic.panel": {
                    "signing_cert_sha256": "b" * 64,
                    "allowed_rollout_rings": ["lab"],
                    "launch_components": [
                        "org.questtermuxlab.synthetic.panel/.MainActivity",
                    ],
                }
            },
            "allowed_launch_components": [
                "org.questtermuxlab.synthetic.panel/.MainActivity",
            ],
            "allowed_logcat_tags": ["QuestTermuxLab"],
        }
        self.state = self.agent.AgentState(started_at=time.monotonic())

    def test_agent_status_command(self) -> None:
        result = self.agent.execute_command(self.config, self.state, command())
        self.assertTrue(result["accepted"])
        self.assertEqual(result["status"], "completed")
        self.assertIn("quest-agent-alpha", result["stdout_tail"])
        self.assertFalse(result["local_adb_used"])

    def test_rejects_non_allowlisted_kind(self) -> None:
        limited = dict(self.config)
        limited["allowed_command_kinds"] = ["agent.status"]
        request = command(kind="termux.exec_allowlisted")
        request["payload"] = {"alias": "python_version"}
        result = self.agent.execute_command(limited, self.state, request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "kind_not_allowed")

    def test_rejects_local_adb_when_disabled(self) -> None:
        request = command(kind="adb.self_check")
        result = self.agent.execute_command(self.config, self.state, request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "local_adb_disabled")

    def test_update_manifest_rejects_unallowed_package(self) -> None:
        request = command(kind="apk.update_verified")
        request["requires_local_adb_shell"] = True
        request["payload"] = {"manifest": update_manifest(package_name="org.example.other")}
        result = self.agent.execute_command(self.config, self.state, request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "package_not_allowed")

    def test_update_reports_recovery_when_local_adb_disabled(self) -> None:
        request = command(kind="apk.update_verified")
        request["requires_local_adb_shell"] = True
        request["payload"] = {"manifest": update_manifest()}
        result = self.agent.execute_command(self.config, self.state, request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "local_adb_unavailable")
        self.assertEqual(result["update_report"]["package_name"], "org.questtermuxlab.synthetic.panel")
        self.assertEqual(result["recovery_action"]["kind"], "central_direct_adb_recovery")

    def test_rejects_http_apk_url_by_default(self) -> None:
        request = command(kind="apk.update_verified")
        request["requires_local_adb_shell"] = True
        manifest = update_manifest()
        manifest["apk_url"] = "http://127.0.0.1:8790/synthetic-panel.apk"
        request["payload"] = {"manifest": manifest}
        result = self.agent.execute_command(self.config, self.state, request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "apk_url_not_https")

    def test_allows_http_loopback_apk_url_only_when_enabled(self) -> None:
        config = dict(self.config)
        config["allow_insecure_loopback_apk_urls"] = True
        manifest = update_manifest()
        manifest["apk_url"] = "http://127.0.0.1:8790/synthetic-panel.apk"
        accepted = self.agent.normalize_update_manifest(config, {"manifest": manifest})
        self.assertIsInstance(accepted, dict)

        manifest["apk_url"] = "http://example.invalid/synthetic-panel.apk"
        rejected = self.agent.normalize_update_manifest(config, {"manifest": manifest})
        self.assertEqual(rejected, "apk_url_not_https")

    def test_rejects_disallowed_launch_component(self) -> None:
        request = command(kind="app.launch_allowlisted")
        request["requires_local_adb_shell"] = True
        request["payload"] = {"component": "org.example.other/.MainActivity"}
        result = self.agent.execute_command(self.config, self.state, request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "launch_component_not_allowed")

    def test_rejects_disallowed_logcat_tag(self) -> None:
        request = command(kind="android.logcat_slice")
        request["requires_local_adb_shell"] = True
        request["payload"] = {"tag": "PrivateTag", "lines": 20}
        result = self.agent.execute_command(self.config, self.state, request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "logcat_tag_not_allowed")

    def test_adb_subprocess_env_creates_configured_tmpdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adb_tmpdir = Path(tmp) / "termux-prefix" / "tmp"
            config = dict(self.config)
            config["adb_tmpdir"] = str(adb_tmpdir)
            env = self.agent.adb_subprocess_env(config)
            self.assertEqual(env["TMPDIR"], str(adb_tmpdir))
            self.assertTrue(adb_tmpdir.is_dir())

    def test_heartbeat_can_refresh_local_adb_state_when_enabled(self) -> None:
        config = dict(self.config)
        config["local_adb_enabled"] = True
        config["check_local_adb_on_heartbeat"] = True
        with mock.patch.object(self.agent, "refresh_local_adb_state", return_value=(True, "", "")) as refresh:
            self.agent.refresh_local_adb_for_heartbeat(config, self.state)
        refresh.assert_called_once()


class EndToEndTests(unittest.TestCase):
    def test_agent_posts_heartbeat_gets_command_and_posts_result(self) -> None:
        agent = load_agent_module()
        with tempfile.TemporaryDirectory() as tmp:
            state = fleet_control_plane.FleetState(log_dir=Path(tmp) / "controller")
            server = fleet_control_plane.FleetServer(("127.0.0.1", 0), state, quiet=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                config = {
                    "fleet_id": "synthetic-lab-fleet",
                    "agent_id": "quest-agent-alpha",
                    "central_url": f"http://127.0.0.1:{port}",
                    "workspace_root": str(Path(tmp) / "agent"),
                    "allowed_command_kinds": ["agent.status"],
                    "command_aliases": {},
                    "local_adb_enabled": False,
                }
                state.queue_command(command())
                agent_state = agent.AgentState(started_at=time.monotonic())
                agent.run_once(config, agent_state)
                self.assertIn("quest-agent-alpha", state.heartbeats)
                self.assertTrue(state.heartbeats["quest-agent-alpha"]["central_reachable"])
                self.assertEqual(len(state.results), 1)
                self.assertEqual(state.results[0]["command_id"], "cmd-agent-status-test")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class ExampleTests(unittest.TestCase):
    def test_new_examples_parse_and_have_expected_schema(self) -> None:
        expected = {
            "fleet-agent-manifest.synthetic.json": "quest-termux-lab.fleet-agent-manifest.v1",
            "fleet-agent-heartbeat.synthetic.json": "quest-termux-lab.fleet-agent-heartbeat.v1",
            "fleet-command-request.synthetic.json": "quest-termux-lab.fleet-command-request.v1",
            "fleet-command-result.synthetic.json": "quest-termux-lab.fleet-command-result.v1",
            "apk-update-manifest.synthetic.json": "quest-termux-lab.apk-update-manifest.v1",
            "fleet-command-request.apk-update.synthetic.json": "quest-termux-lab.fleet-command-request.v1",
            "fleet-command-result.apk-update-recovery.synthetic.json": "quest-termux-lab.fleet-command-result.v1",
            "adb-shell-lease-state.synthetic.json": "quest-termux-lab.adb-shell-lease-state.v1",
            "session-recipe.outbound-fleet-agent.json": "quest-termux-lab.session-recipe.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))
                self.assertEqual(payload["schema"], schema)


if __name__ == "__main__":
    unittest.main()
