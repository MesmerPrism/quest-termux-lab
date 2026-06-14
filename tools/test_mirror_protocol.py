#!/usr/bin/env python3
"""Tests for the public-safe mirror command protocol slice."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = REPO_ROOT / "tools" / "fleet_control_plane.py"
AGENT_PATH = REPO_ROOT / "scripts" / "termux_fleet_agent.py"
LEASE_ID = "mirror-alpha-to-beta-001"
FLEET_ID = "synthetic-lab-fleet"
SOURCE_ID = "quest-agent-alpha"
TARGET_ID = "quest-agent-beta"
PANEL_COMPONENT = "org.questtermuxlab.synthetic.panel/.MainActivity"
MIRROR_KINDS = [
    "agent.status",
    "agent.capabilities",
    "adb.lease_check",
    "android.foreground_snapshot",
    "app.launch_allowlisted",
    "uiautomator.run_allowlisted_scenario",
    "adb.lease_disconnect",
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fleet_control_plane = load_module("fleet_control_plane_mirror_tests", CONTROL_PATH)


def load_agent_module():
    return load_module("termux_fleet_agent_mirror_tests", AGENT_PATH)


def future_time(seconds: int = 300) -> str:
    value = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def mirror_lease(
    *,
    source_agent_id: str = SOURCE_ID,
    target_agent_id: str = TARGET_ID,
    expires_in: int = 300,
    revoked: bool = False,
    allowed_kinds: list[str] | None = None,
    fleet_id: str = FLEET_ID,
) -> dict:
    return {
        "schema": "quest-termux-lab.mirror-session-lease.v1",
        "fleet_id": fleet_id,
        "lease_id": LEASE_ID,
        "operator_id": "synthetic-operator",
        "source_agent_id": source_agent_id,
        "target_agent_id": target_agent_id,
        "purpose": "Unit-test two-Quest mirror rehearsal.",
        "issued_at": future_time(-1),
        "expires_at": future_time(expires_in),
        "consent_mode": "operator_visible_lab",
        "allowed_command_kinds": allowed_kinds or list(MIRROR_KINDS),
        "requires_target_consent": True,
        "requires_local_adb_shell_for_adb_commands": True,
        "active_indicator_required": True,
        "emergency_stop_supported": True,
        "sensitivity": "local_only",
        "revoked": revoked,
        "revoked_at": None,
        "revoked_by": None,
        "synthetic": True,
    }


def mirror_intent(
    *,
    mirror_intent_id: str = "alpha-status-001",
    source_agent_id: str = SOURCE_ID,
    target_agent_id: str = TARGET_ID,
    kind: str = "agent.status",
    payload: dict | None = None,
    requires_adb: bool = False,
    idempotency_key: str = "alpha-status-v1",
    expires_in: int = 30,
) -> dict:
    return {
        "schema": "quest-termux-lab.mirror-command-intent.v1",
        "fleet_id": FLEET_ID,
        "mirror_intent_id": mirror_intent_id,
        "lease_id": LEASE_ID,
        "source_agent_id": source_agent_id,
        "target_agent_id": target_agent_id,
        "issued_at": future_time(-1),
        "expires_at": future_time(expires_in),
        "idempotency_key": idempotency_key,
        "kind": kind,
        "requires_local_adb_shell": requires_adb,
        "timeout_ms": 5000,
        "max_stdout_bytes": 4096,
        "max_stderr_bytes": 4096,
        "payload": payload or {},
        "sensitivity": "local_only",
        "reason": "Unit test mirror command.",
        "synthetic": True,
    }


def remote_session_lease() -> dict:
    return {
        "schema": "quest-termux-lab.remote-session-lease.v1",
        "lease_id": LEASE_ID,
        "fleet_id": FLEET_ID,
        "agent_id": TARGET_ID,
        "operator_id": "synthetic-operator",
        "purpose": "Unit-test bounded mirror operation.",
        "created_at": future_time(-1),
        "expires_at": future_time(300),
        "consent_mode": "operator_visible_lab",
        "command_scopes": list(MIRROR_KINDS),
        "requires_visual_confirmation": False,
        "requires_local_adb_shell": True,
        "active_indicator_required": True,
        "emergency_stop_supported": True,
        "revoked": False,
        "synthetic": True,
    }


def target_config(
    *,
    policy_kinds: list[str] | None = None,
    local_adb_enabled: bool = False,
    operator_visible_session_active: bool = True,
    remote_lease: dict | None = None,
) -> dict:
    return {
        "fleet_id": FLEET_ID,
        "agent_id": TARGET_ID,
        "central_url": "http://127.0.0.1:8787",
        "workspace_root": "runs/test-mirror-agent",
        "allowed_command_kinds": list(MIRROR_KINDS),
        "command_aliases": {},
        "local_adb_enabled": local_adb_enabled,
        "allowed_launch_components": [PANEL_COMPONENT],
        "allowed_logcat_tags": ["QuestTermuxLab"],
        "allowed_uiautomator_scenarios": {
            "settingsRecoveryProbe": {
                "instrumentation": "org.questtermuxlab.synthetic.test/androidx.test.runner.AndroidJUnitRunner",
                "allowed_extras": ["retryCount"],
                "default_extras": {"retryCount": 1},
            }
        },
        "active_remote_session_leases": [remote_lease or remote_session_lease()],
        "operator_visible_session_active": operator_visible_session_active,
        "mirror_bindings": {
            SOURCE_ID: {
                "enabled": True,
                "allowed_lease_ids": [LEASE_ID],
                "allowed_command_kinds": policy_kinds or list(MIRROR_KINDS),
                "allowed_launch_components": [PANEL_COMPONENT],
                "allowed_uiautomator_scenarios": ["settingsRecoveryProbe"],
                "max_command_ttl_seconds": 60,
                "require_local_adb_shell": True,
                "require_operator_visible_session": True,
            }
        },
    }


class MirrorControllerTests(unittest.TestCase):
    def test_accepts_status_intent_and_maps_result(self) -> None:
        agent = load_agent_module()
        state = fleet_control_plane.FleetState()
        self.assertEqual(state.create_mirror_lease(mirror_lease())["status"], "accepted")
        queued = state.submit_mirror_intent(mirror_intent())
        self.assertEqual(queued["status"], "queued_for_target")

        command = state.next_command(TARGET_ID)
        self.assertEqual(command["kind"], "agent.status")
        self.assertEqual(command["origin"], "mirror")
        self.assertEqual(command["source_agent_id"], SOURCE_ID)
        self.assertEqual(command["mirror_intent_id"], "alpha-status-001")

        result = agent.execute_command(target_config(), agent.AgentState(time.monotonic()), command)
        self.assertTrue(result["accepted"])
        state.record_result(result)

        status = state.mirror_intent_status("alpha-status-001")
        self.assertEqual(status["state"], "completed")
        self.assertEqual(status["target_result"]["command_id"], "mirror-alpha-status-001")
        events = state.mirror_session_events(LEASE_ID)
        self.assertEqual(events["event_count"], 2)
        self.assertEqual(events["events"][-1]["state"], "completed")

    def test_rejects_missing_lease(self) -> None:
        state = fleet_control_plane.FleetState()
        rejected = state.submit_mirror_intent(mirror_intent())
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "mirror_lease_missing")
        self.assertEqual(state.mirror_intent_status("alpha-status-001")["state"], "rejected")
        events = state.mirror_session_events(LEASE_ID)
        self.assertEqual(events["events"][-1]["state"], "rejected")

    def test_rejects_expired_lease(self) -> None:
        state = fleet_control_plane.FleetState()
        with self.assertRaisesRegex(ValueError, "already expired"):
            state.create_mirror_lease(mirror_lease(expires_in=-1))
        state.mirror_leases[LEASE_ID] = mirror_lease(expires_in=-1)
        rejected = state.submit_mirror_intent(mirror_intent(mirror_intent_id="alpha-expired-lease-001"))
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "mirror_lease_expired")

    def test_rejects_wrong_source(self) -> None:
        state = fleet_control_plane.FleetState()
        state.create_mirror_lease(mirror_lease())
        rejected = state.submit_mirror_intent(mirror_intent(source_agent_id="quest-agent-gamma"))
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "mirror_source_not_allowed")

    def test_revoke_lease_rejects_new_intent(self) -> None:
        state = fleet_control_plane.FleetState()
        state.create_mirror_lease(mirror_lease())
        self.assertEqual(state.revoke_mirror_lease(LEASE_ID)["status"], "revoked")
        rejected = state.submit_mirror_intent(mirror_intent())
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "mirror_lease_revoked")

    def test_rejects_source_equal_target_lease(self) -> None:
        state = fleet_control_plane.FleetState()
        with self.assertRaisesRegex(ValueError, "mirror source and target must differ"):
            state.create_mirror_lease(mirror_lease(target_agent_id=SOURCE_ID))

    def test_rejects_wrong_fleet_id(self) -> None:
        state = fleet_control_plane.FleetState()
        state.create_mirror_lease(mirror_lease(fleet_id="other-fleet"))
        rejected = state.submit_mirror_intent(mirror_intent())
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "mirror_lease_fleet_mismatch")

    def test_rejects_kind_not_allowed_by_lease(self) -> None:
        state = fleet_control_plane.FleetState()
        state.create_mirror_lease(mirror_lease(allowed_kinds=["agent.status"]))
        rejected = state.submit_mirror_intent(
            mirror_intent(kind="agent.capabilities", mirror_intent_id="alpha-capabilities-lease-001")
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "mirror_kind_not_allowed")

    def test_duplicate_idempotency_key_maps_to_existing_command(self) -> None:
        agent = load_agent_module()
        state = fleet_control_plane.FleetState()
        state.create_mirror_lease(mirror_lease())
        first = state.submit_mirror_intent(
            mirror_intent(mirror_intent_id="alpha-status-001", idempotency_key="same-status")
        )
        second = state.submit_mirror_intent(
            mirror_intent(mirror_intent_id="alpha-status-002", idempotency_key="same-status")
        )
        self.assertEqual(first["command_id"], second["command_id"])
        self.assertEqual(len(state.commands[TARGET_ID]), 1)

        command = state.next_command(TARGET_ID)
        result = agent.execute_command(target_config(), agent.AgentState(time.monotonic()), command)
        state.record_result(result)
        self.assertEqual(state.mirror_intent_status("alpha-status-001")["state"], "completed")
        self.assertEqual(state.mirror_intent_status("alpha-status-002")["state"], "completed")


class MirrorAgentPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = load_agent_module()
        self.state = self.agent.AgentState(time.monotonic())

    def test_rejects_wrong_target(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(target_agent_id="quest-agent-gamma")
        )
        result = self.agent.execute_command(target_config(), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "wrong_agent")

    def test_rejects_disallowed_mirror_kind(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(kind="agent.capabilities", mirror_intent_id="alpha-capabilities-001")
        )
        result = self.agent.execute_command(target_config(policy_kinds=["agent.status"]), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_kind_not_allowed")

    def test_rejects_mirror_origin_without_source(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(mirror_intent())
        command.pop("source_agent_id")
        result = self.agent.execute_command(target_config(), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_source_missing")

    def test_rejects_mirror_origin_without_intent_id(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(mirror_intent())
        command.pop("mirror_intent_id")
        result = self.agent.execute_command(target_config(), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_intent_missing")

    def test_rejects_mirror_metadata_without_origin(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(mirror_intent())
        command.pop("origin")
        result = self.agent.execute_command(target_config(), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_origin_missing")

    def test_rejects_intent_beyond_binding_ttl(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(mirror_intent_id="alpha-long-ttl-001", expires_in=120)
        )
        result = self.agent.execute_command(target_config(), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_ttl_exceeded")

    def test_rejects_operator_visible_session_inactive(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(mirror_intent())
        result = self.agent.execute_command(
            target_config(operator_visible_session_active=False),
            self.state,
            command,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_operator_consent_missing")

    def test_rejects_adb_required_command_when_local_adb_unavailable(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(
                kind="app.launch_allowlisted",
                mirror_intent_id="alpha-launch-001",
                payload={"component": PANEL_COMPONENT},
                requires_adb=True,
            )
        )
        result = self.agent.execute_command(target_config(local_adb_enabled=False), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "local_adb_required_but_unavailable")

    def test_rejects_disallowed_launch_component_by_mirror_policy(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(
                kind="app.launch_allowlisted",
                mirror_intent_id="alpha-launch-002",
                payload={"component": "org.questtermuxlab.other/.MainActivity"},
                requires_adb=True,
            )
        )
        config = target_config(local_adb_enabled=True)
        result = self.agent.execute_command(config, self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_launch_component_not_allowed")

    def test_rejects_disallowed_uiautomator_scenario_by_mirror_policy(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(
                kind="uiautomator.run_allowlisted_scenario",
                mirror_intent_id="alpha-uiautomator-001",
                payload={"scenario": "rawShell", "extras": {}},
                requires_adb=True,
            )
        )
        result = self.agent.execute_command(target_config(local_adb_enabled=True), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "mirror_uiautomator_scenario_not_allowed")

    def test_rejects_uiautomator_extra_key_not_allowed(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(
                kind="uiautomator.run_allowlisted_scenario",
                mirror_intent_id="alpha-uiautomator-002",
                payload={"scenario": "settingsRecoveryProbe", "extras": {"badExtra": "1"}},
                requires_adb=True,
            )
        )
        result = self.agent.execute_command(target_config(local_adb_enabled=True), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "uiautomator_extra_not_allowed")

    def test_rejects_uiautomator_extra_value_unsafe(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(
                kind="uiautomator.run_allowlisted_scenario",
                mirror_intent_id="alpha-uiautomator-003",
                payload={"scenario": "settingsRecoveryProbe", "extras": {"retryCount": "bad/value"}},
                requires_adb=True,
            )
        )
        result = self.agent.execute_command(target_config(local_adb_enabled=True), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "uiautomator_extra_value_unsafe")

    def test_adb_lease_check_diagnostic_when_local_adb_disabled(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(kind="adb.lease_check", mirror_intent_id="alpha-lease-check-001")
        )
        result = self.agent.execute_command(target_config(local_adb_enabled=False), self.state, command)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["status"], "completed")
        self.assertIn('"available": false', result["stdout_tail"])

    def test_adb_lease_disconnect_best_effort_when_local_adb_disabled(self) -> None:
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(kind="adb.lease_disconnect", mirror_intent_id="alpha-disconnect-001")
        )
        result = self.agent.execute_command(target_config(local_adb_enabled=False), self.state, command)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["status"], "completed")
        self.assertIn('"attempted": false', result["stdout_tail"])

    def test_rejects_revoked_remote_session_lease(self) -> None:
        lease = remote_session_lease()
        lease["revoked"] = True
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(kind="app.launch_allowlisted", payload={"component": PANEL_COMPONENT}, requires_adb=True)
        )
        result = self.agent.execute_command(target_config(remote_lease=lease, local_adb_enabled=True), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "remote_session_lease_revoked")

    def test_rejects_wrong_agent_remote_session_lease(self) -> None:
        lease = remote_session_lease()
        lease["agent_id"] = "quest-agent-gamma"
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(kind="app.launch_allowlisted", payload={"component": PANEL_COMPONENT}, requires_adb=True)
        )
        result = self.agent.execute_command(target_config(remote_lease=lease, local_adb_enabled=True), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "remote_session_lease_wrong_agent")

    def test_rejects_scope_denied_remote_session_lease(self) -> None:
        lease = remote_session_lease()
        lease["command_scopes"] = ["agent.status"]
        command = fleet_control_plane.mirror_intent_to_fleet_command(
            mirror_intent(kind="app.launch_allowlisted", payload={"component": PANEL_COMPONENT}, requires_adb=True)
        )
        result = self.agent.execute_command(target_config(remote_lease=lease, local_adb_enabled=True), self.state, command)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error_code"], "remote_session_lease_scope_denied")


class MirrorExampleTests(unittest.TestCase):
    def test_examples_parse_and_have_expected_schema(self) -> None:
        expected = {
            "mirror-session-lease.synthetic.json": "quest-termux-lab.mirror-session-lease.v1",
            "mirror-binding-policy.synthetic.json": "quest-termux-lab.mirror-binding-policy.v1",
            "mirror-command-intent.launch.synthetic.json": "quest-termux-lab.mirror-command-intent.v1",
            "mirror-command-event.completed.synthetic.json": "quest-termux-lab.mirror-command-event.v1",
            "mirror-commander-config.synthetic.json": None,
            "session-recipe.mirror-two-quest.json": "quest-termux-lab.session-recipe.v1",
        }
        for name, schema in expected.items():
            with self.subTest(name=name):
                payload = json.loads((REPO_ROOT / "examples" / name).read_text(encoding="utf-8"))
                self.assertTrue(payload.get("synthetic") is True or name.startswith("session-recipe."))
                if schema is not None:
                    self.assertEqual(payload["schema"], schema)


if __name__ == "__main__":
    unittest.main()
