#!/usr/bin/env python3
"""Outbound-only Termux fleet agent prototype.

The agent posts heartbeats to a central control plane, polls for one command,
executes only allowlisted bounded commands, and posts the result. It uses only
the Python standard library so it can run in a small Termux environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen


API_PREFIX = "/api/fleet/v1"
HEARTBEAT_SCHEMA = "quest-termux-lab.fleet-agent-heartbeat.v1"
COMMAND_SCHEMA = "quest-termux-lab.fleet-command-request.v1"
RESULT_SCHEMA = "quest-termux-lab.fleet-command-result.v1"
NO_COMMAND_SCHEMA = "quest-termux-lab.fleet-no-command.v1"
APK_UPDATE_MANIFEST_SCHEMA = "quest-termux-lab.apk-update-manifest.v1"
AGENT_VERSION = "0.2.5"
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
SAFE_EXTRA_VALUE_RE = re.compile(r"^[A-Za-z0-9_.:, +@-]{0,128}$")
PASSIVE_COMMAND_KINDS = {"agent.status", "agent.capabilities"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


class AgentState:
    def __init__(self, started_at: float):
        self.started_at = started_at
        self.sequence = 0
        self.last_command_id: str | None = None
        self.last_command_status: str | None = None
        self.last_error_code: str | None = None
        self.completed_idempotency: dict[str, dict[str, Any]] = {}
        self.local_adb_state = {
            "checked": False,
            "available": False,
            "adb_target": None,
            "shell_uid": None,
            "last_success_at": None,
            "last_failure_reason": None,
        }


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    required = ["fleet_id", "agent_id", "central_url", "allowed_command_kinds"]
    for key in required:
        if key not in config:
            raise ValueError(f"missing config field {key}")
    return config


def central_url(config: dict[str, Any], path: str) -> str:
    return str(config["central_url"]).rstrip("/") + path


def post_json(url: str, payload: dict[str, Any], timeout_seconds: float = 10.0) -> dict[str, Any]:
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout_seconds) as handle:
        response = json.loads(handle.read().decode("utf-8"))
    if not isinstance(response, dict):
        raise ValueError("response must be a JSON object")
    return response


def get_json(url: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    with urlopen(request, timeout=timeout_seconds) as handle:
        response = json.loads(handle.read().decode("utf-8"))
    if not isinstance(response, dict):
        raise ValueError("response must be a JSON object")
    return response


def write_jsonl(config: dict[str, Any], name: str, payload: dict[str, Any]) -> None:
    root = Path(str(config.get("workspace_root", "runs/fleet-agent")))
    root.mkdir(parents=True, exist_ok=True)
    with (root / name).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def make_heartbeat(config: dict[str, Any], state: AgentState, central_reachable: bool) -> dict[str, Any]:
    workspace = Path(str(config.get("workspace_root", ".")))
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        storage_free = shutil.disk_usage(workspace).free
    except OSError:
        storage_free = None
    heartbeat = {
        "schema": HEARTBEAT_SCHEMA,
        "fleet_id": config["fleet_id"],
        "agent_id": config["agent_id"],
        "sequence": state.sequence,
        "observed_at": utc_now(),
        "agent_uptime_seconds": round(time.monotonic() - state.started_at, 3),
        "central_reachable": central_reachable,
        "battery_percent": None,
        "charging": None,
        "storage_free_bytes": storage_free,
        "process_count": None,
        "active_jobs": 0,
        "last_command_id": state.last_command_id,
        "last_command_status": state.last_command_status,
        "last_error_code": state.last_error_code,
        "local_adb": dict(state.local_adb_state),
        "foreground": None,
    }
    state.sequence += 1
    return heartbeat


def result_base(config: dict[str, Any], command: dict[str, Any], started_at: str, start_monotonic: float) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "fleet_id": config["fleet_id"],
        "agent_id": config["agent_id"],
        "command_id": command.get("command_id", "unknown-command"),
        "idempotency_key": command.get("idempotency_key"),
        "remote_session_lease_id": command.get("remote_session_lease_id"),
        "accepted": False,
        "status": "rejected",
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_ms": int((time.monotonic() - start_monotonic) * 1000),
        "exit_code": None,
        "stdout_tail": None,
        "stderr_tail": None,
        "artifacts": [],
        "local_adb_used": False,
        "local_adb_shell_uid": None,
        "error_code": None,
        "error_message": None,
        "update_report": None,
        "rollback_report": None,
        "recovery_action": None,
        "redactions_applied": False,
    }


def reject_result(
    config: dict[str, Any],
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
    code: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    result = result_base(config, command, started_at, start_monotonic)
    result["error_code"] = code
    result["error_message"] = message
    result["finished_at"] = utc_now()
    result["duration_ms"] = int((time.monotonic() - start_monotonic) * 1000)
    result.update(extra)
    return result


def trim_output(text: str, max_bytes: int) -> str:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return text
    return data[-max_bytes:].decode("utf-8", errors="replace")


def execute_command(config: dict[str, Any], state: AgentState, command: dict[str, Any]) -> dict[str, Any]:
    started_at = utc_now()
    start_monotonic = time.monotonic()
    if command.get("schema") != COMMAND_SCHEMA:
        return reject_result(config, command, started_at, start_monotonic, "unsupported_schema", "Unsupported command schema.")

    if command.get("target_agent_id") != config["agent_id"]:
        return reject_result(config, command, started_at, start_monotonic, "wrong_agent", "Command target does not match this agent.")

    expires_at = command.get("expires_at")
    if not isinstance(expires_at, str) or parse_time(expires_at) <= datetime.now(timezone.utc):
        return reject_result(config, command, started_at, start_monotonic, "expired", "Command is expired.")

    kind = command.get("kind")
    allowed = set(config.get("allowed_command_kinds", []))
    if kind not in allowed:
        return reject_result(config, command, started_at, start_monotonic, "kind_not_allowed", "Command kind is not in the allowlist.")

    lease_error = validate_remote_session_lease(config, command, str(kind))
    if lease_error is not None:
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            lease_error,
            "Command requires an active remote session lease.",
        )

    if kind == "agent.status":
        return complete_text(config, command, started_at, start_monotonic, agent_status_text(config, state), "")
    if kind == "agent.capabilities":
        return complete_text(config, command, started_at, start_monotonic, agent_capabilities_text(config), "")
    if kind == "termux.exec_allowlisted":
        return run_alias(config, command, started_at, start_monotonic)
    if kind == "adb.self_check":
        return run_adb_self_check(config, state, command, started_at, start_monotonic)
    if kind == "apk.update_verified":
        return run_apk_update_verified(config, state, command, started_at, start_monotonic)
    if kind == "app.launch_allowlisted":
        return run_app_launch_allowlisted(config, state, command, started_at, start_monotonic)
    if kind == "android.foreground_snapshot":
        return run_foreground_snapshot(config, state, command, started_at, start_monotonic)
    if kind == "android.logcat_slice":
        return run_logcat_slice(config, state, command, started_at, start_monotonic)
    if kind == "adb.lease_check":
        return run_adb_lease_check(config, state, command, started_at, start_monotonic)
    if kind == "adb.lease_disconnect":
        return run_adb_lease_disconnect(config, state, command, started_at, start_monotonic)
    if kind == "uiautomator.run_allowlisted_scenario":
        return run_uiautomator_allowlisted_scenario(config, state, command, started_at, start_monotonic)
    if kind == "termux.agent.restart_status":
        return run_termux_agent_restart_status(config, state, command, started_at, start_monotonic)
    if kind in {"media_projection.preview_request", "media_projection.preview_stop"}:
        return run_media_projection_preview_boundary(config, command, started_at, start_monotonic, str(kind))

    return reject_result(config, command, started_at, start_monotonic, "kind_unimplemented", "Command kind is recognized but not implemented in this prototype.")


def agent_status_text(config: dict[str, Any], state: AgentState) -> str:
    return json.dumps(
        {
            "agent_id": config["agent_id"],
            "agent_version": AGENT_VERSION,
            "status": "alive",
            "sequence": state.sequence,
            "python": platform.python_version(),
            "last_update_idempotency_keys": sorted(state.completed_idempotency)[-5:],
        },
        sort_keys=True,
    )


def agent_capabilities_text(config: dict[str, Any]) -> str:
    return json.dumps(
        {
            "agent_id": config["agent_id"],
            "allowed_command_kinds": config.get("allowed_command_kinds", []),
            "local_adb_configured": bool(config.get("local_adb_enabled", False)),
            "command_aliases": sorted(dict(config.get("command_aliases", {}))),
            "allowed_update_packages": sorted(dict(config.get("allowed_update_packages", {}))),
            "allowed_launch_components": sorted(config.get("allowed_launch_components", [])),
            "allowed_logcat_tags": sorted(config.get("allowed_logcat_tags", [])),
            "allowed_uiautomator_scenarios": sorted(dict(config.get("allowed_uiautomator_scenarios", {}))),
            "media_projection_preview_configured": bool(config.get("media_projection_preview_enabled", False)),
            "helper_can_restart_agent": bool(config.get("helper_can_restart_agent", False)),
            "requires_remote_session_lease": True,
            "active_remote_session_lease_ids": active_remote_session_lease_ids(config),
        },
        sort_keys=True,
    )


def active_remote_session_lease_ids(config: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for lease in configured_remote_session_leases(config):
        lease_id = lease.get("lease_id")
        if isinstance(lease_id, str):
            ids.append(lease_id)
    return sorted(ids)


def configured_remote_session_leases(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw = config.get("active_remote_session_leases", [])
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def validate_remote_session_lease(config: dict[str, Any], command: dict[str, Any], kind: str) -> str | None:
    if kind in PASSIVE_COMMAND_KINDS:
        return None

    lease_id = command.get("remote_session_lease_id")
    if not isinstance(lease_id, str) or not lease_id:
        return "missing_remote_session_lease"

    matching = [lease for lease in configured_remote_session_leases(config) if lease.get("lease_id") == lease_id]
    if not matching:
        return "remote_session_lease_inactive"
    lease = matching[0]
    if lease.get("revoked"):
        return "remote_session_lease_revoked"
    if lease.get("fleet_id") not in (None, config.get("fleet_id")):
        return "remote_session_lease_wrong_fleet"
    if lease.get("agent_id") not in (None, config.get("agent_id")):
        return "remote_session_lease_wrong_agent"

    expires_at = lease.get("expires_at")
    if not isinstance(expires_at, str):
        return "remote_session_lease_missing_expiry"
    try:
        if parse_time(expires_at) <= datetime.now(timezone.utc):
            return "remote_session_lease_expired"
    except ValueError:
        return "remote_session_lease_bad_expiry"

    scopes = lease.get("command_scopes", [])
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
        return "remote_session_lease_bad_scopes"
    if "*" not in scopes and kind not in set(scopes):
        return "remote_session_lease_scope_denied"

    if command.get("requires_local_adb_shell") and lease.get("requires_local_adb_shell") is False:
        return "remote_session_lease_disallows_adb"
    return None


def complete_text(
    config: dict[str, Any],
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
    stdout: str,
    stderr: str,
    exit_code: int = 0,
    local_adb_used: bool = False,
    local_adb_shell_uid: str | None = None,
    update_report: dict[str, Any] | None = None,
    rollback_report: dict[str, Any] | None = None,
    recovery_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = result_base(config, command, started_at, start_monotonic)
    result.update(
        {
            "accepted": True,
            "status": "completed" if exit_code == 0 else "failed",
            "finished_at": utc_now(),
            "duration_ms": int((time.monotonic() - start_monotonic) * 1000),
            "exit_code": exit_code,
            "stdout_tail": trim_output(stdout, int(command.get("max_stdout_bytes", 4096))),
            "stderr_tail": trim_output(stderr, int(command.get("max_stderr_bytes", 4096))),
            "local_adb_used": local_adb_used,
            "local_adb_shell_uid": local_adb_shell_uid,
            "update_report": update_report,
            "rollback_report": rollback_report,
            "recovery_action": recovery_action,
        }
    )
    return result


def run_alias(config: dict[str, Any], command: dict[str, Any], started_at: str, start_monotonic: float) -> dict[str, Any]:
    payload = command.get("payload", {})
    if not isinstance(payload, dict):
        return reject_result(config, command, started_at, start_monotonic, "invalid_payload", "Payload must be an object.")
    alias = payload.get("alias")
    aliases = config.get("command_aliases", {})
    if not isinstance(alias, str) or alias not in aliases:
        return reject_result(config, command, started_at, start_monotonic, "alias_not_allowed", "Command alias is not allowed.")
    argv = aliases[alias]
    if not isinstance(argv, list) or not all(isinstance(part, str) for part in argv):
        return reject_result(config, command, started_at, start_monotonic, "bad_alias_config", "Command alias is not a string argv list.")
    timeout = max(0.001, float(command.get("timeout_ms", 5000)) / 1000.0)
    try:
        completed = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        return reject_result(config, command, started_at, start_monotonic, "timeout", f"Command timed out after {timeout:.3f}s: {exc}")
    except OSError as exc:
        return reject_result(config, command, started_at, start_monotonic, "exec_failed", str(exc))
    return complete_text(config, command, started_at, start_monotonic, completed.stdout, completed.stderr, completed.returncode)


def run_adb_self_check(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    if not config.get("local_adb_enabled", False):
        mark_local_adb_unavailable(config, state, "local_adb_disabled")
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "local_adb_disabled",
            "Local ADB is disabled in agent config.",
            recovery_action=central_recovery_action("local_adb_disabled"),
        )

    available, stdout, stderr = refresh_local_adb_state(
        config,
        state,
        timeout=max(1.0, float(command.get("timeout_ms", 10000)) / 1000.0),
    )
    return complete_text(
        config,
        command,
        started_at,
        start_monotonic,
        stdout,
        stderr,
        0 if available else 1,
        local_adb_used=True,
        local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
        recovery_action=None if available else central_recovery_action("local_adb_check_failed"),
    )


def run_apk_update_verified(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    manifest_result = normalize_update_manifest(config, command.get("payload", {}))
    if isinstance(manifest_result, str):
        return reject_result(config, command, started_at, start_monotonic, manifest_result, "APK update manifest was rejected.")
    manifest = manifest_result
    update_report = make_update_report(manifest)

    idem = command.get("idempotency_key")
    if isinstance(idem, str) and idem in state.completed_idempotency:
        previous = dict(state.completed_idempotency[idem])
        previous["command_id"] = command.get("command_id", previous.get("command_id"))
        previous["status"] = "skipped"
        previous["finished_at"] = utc_now()
        previous["duration_ms"] = int((time.monotonic() - start_monotonic) * 1000)
        previous["error_code"] = None
        previous["error_message"] = None
        return previous

    available, _, _ = ensure_local_adb_for_command(config, state, command)
    if not available:
        update_report["install_attempted"] = False
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "local_adb_unavailable",
            "Local ADB shell is not available for verified APK update.",
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            update_report=update_report,
            rollback_report=make_rollback_report("not_attempted", None, None, "local_adb_unavailable"),
            recovery_action=central_recovery_action("local_adb_unavailable"),
        )

    previous_version_code, previous_version_name = installed_version(config, manifest["package_name"], command)
    update_report["previous_version_code"] = previous_version_code
    update_report["previous_version_name"] = previous_version_name
    rollback_report = make_rollback_report(
        "previous_version_recorded" if previous_version_code is not None else "previous_version_unknown",
        previous_version_code,
        previous_version_name,
        None,
    )

    if previous_version_code is not None and previous_version_code >= manifest["version_code"]:
        update_report["install_attempted"] = False
        update_report["installed_version_code"] = previous_version_code
        result = complete_text(
            config,
            command,
            started_at,
            start_monotonic,
            "Requested APK is not newer than the installed package.",
            "",
            exit_code=0,
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            update_report=update_report,
            rollback_report=rollback_report,
        )
        result["status"] = "skipped"
        remember_idempotent_result(state, command, result)
        return result

    apk_path = download_verified_apk(config, manifest, command)
    if isinstance(apk_path, str):
        update_report["install_attempted"] = False
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            apk_path,
            "Verified APK download failed.",
            update_report=update_report,
            rollback_report=rollback_report,
        )

    metadata_result = verify_apk_metadata(config, apk_path, manifest, command)
    if isinstance(metadata_result, str):
        apk_path.unlink(missing_ok=True)
        update_report["install_attempted"] = False
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            metadata_result,
            "Downloaded APK metadata did not match the manifest.",
            update_report=update_report,
            rollback_report=rollback_report,
        )

    update_report.update(metadata_result)
    install_stdout, install_stderr, install_code = adb_install(config, apk_path, manifest, command)
    update_report["install_attempted"] = True
    if install_code != 0:
        rollback_report["status"] = "previous_install_retained_or_unknown"
        rollback_report["reason"] = "install_failed"
        return complete_text(
            config,
            command,
            started_at,
            start_monotonic,
            install_stdout,
            install_stderr,
            exit_code=install_code,
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            update_report=update_report,
            rollback_report=rollback_report,
        )

    installed_code, installed_name = installed_version(config, manifest["package_name"], command)
    update_report["installed_version_code"] = installed_code
    update_report["installed_version_name"] = installed_name
    if installed_code != manifest["version_code"]:
        rollback_report["status"] = "post_install_version_mismatch"
        rollback_report["reason"] = "version_readback_mismatch"
        return complete_text(
            config,
            command,
            started_at,
            start_monotonic,
            install_stdout,
            install_stderr,
            exit_code=1,
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            update_report=update_report,
            rollback_report=rollback_report,
        )

    launch_stdout = ""
    launch_stderr = ""
    launch_code = 0
    if manifest.get("launch_after_install"):
        launch_stdout, launch_stderr, launch_code = adb_launch_component(
            config,
            str(manifest.get("launch_component") or ""),
            command,
        )
        update_report["launch_attempted"] = True
        update_report["launch_component"] = manifest.get("launch_component")

    rollback_report["status"] = "not_needed"
    stdout = install_stdout + launch_stdout
    stderr = install_stderr + launch_stderr
    result = complete_text(
        config,
        command,
        started_at,
        start_monotonic,
        stdout,
        stderr,
        exit_code=launch_code,
        local_adb_used=True,
        local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
        update_report=update_report,
        rollback_report=rollback_report,
    )
    remember_idempotent_result(state, command, result)
    return result


def run_app_launch_allowlisted(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    payload = command.get("payload", {})
    component = payload.get("component") if isinstance(payload, dict) else None
    if not isinstance(component, str) or not is_launch_component_allowed(config, component):
        return reject_result(config, command, started_at, start_monotonic, "launch_component_not_allowed", "Launch component is not allowlisted.")
    available, _, _ = ensure_local_adb_for_command(config, state, command)
    if not available:
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "local_adb_unavailable",
            "Local ADB shell is not available for app launch.",
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            recovery_action=central_recovery_action("local_adb_unavailable"),
        )
    stdout, stderr, code = adb_launch_component(config, component, command)
    return complete_text(config, command, started_at, start_monotonic, stdout, stderr, code, True, state.local_adb_state.get("shell_uid"))


def run_foreground_snapshot(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    available, _, _ = ensure_local_adb_for_command(config, state, command)
    if not available:
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "local_adb_unavailable",
            "Local ADB shell is not available for foreground snapshot.",
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            recovery_action=central_recovery_action("local_adb_unavailable"),
        )
    stdout, stderr, code = run_adb_command(config, ["shell", "dumpsys", "window"], command)
    filtered = "\n".join(
        line.strip()
        for line in stdout.splitlines()
        if any(token in line for token in ("mCurrentFocus", "mFocusedApp", "topResumedActivity"))
    )
    return complete_text(config, command, started_at, start_monotonic, filtered, stderr, code, True, state.local_adb_state.get("shell_uid"))


def run_logcat_slice(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    payload = command.get("payload", {})
    tag = payload.get("tag") if isinstance(payload, dict) else None
    if not isinstance(tag, str) or tag not in set(config.get("allowed_logcat_tags", [])):
        return reject_result(config, command, started_at, start_monotonic, "logcat_tag_not_allowed", "Logcat tag is not allowlisted.")
    lines = int(payload.get("lines", 200)) if isinstance(payload, dict) else 200
    lines = min(max(lines, 1), 1000)
    available, _, _ = ensure_local_adb_for_command(config, state, command)
    if not available:
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "local_adb_unavailable",
            "Local ADB shell is not available for logcat slice.",
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            recovery_action=central_recovery_action("local_adb_unavailable"),
        )
    stdout, stderr, code = run_adb_command(config, ["logcat", "-d", "-t", str(lines), "-s", tag], command)
    return complete_text(config, command, started_at, start_monotonic, stdout, stderr, code, True, state.local_adb_state.get("shell_uid"))


def run_adb_lease_check(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    if not config.get("local_adb_enabled", False):
        mark_local_adb_unavailable(config, state, "local_adb_disabled")
        summary = {
            "checked": True,
            "available": False,
            "shell_uid": None,
            "reason": "local_adb_disabled",
        }
        result = complete_text(config, command, started_at, start_monotonic, json.dumps(summary, sort_keys=True), "", 1)
        result["redactions_applied"] = True
        return result

    available, _, _ = refresh_local_adb_state(
        config,
        state,
        timeout=max(1.0, float(command.get("timeout_ms", 10000)) / 1000.0),
    )
    summary = {
        "checked": True,
        "available": available,
        "shell_uid": state.local_adb_state.get("shell_uid"),
        "reason": state.local_adb_state.get("last_failure_reason"),
    }
    result = complete_text(
        config,
        command,
        started_at,
        start_monotonic,
        json.dumps(summary, sort_keys=True),
        "",
        0 if available else 1,
        local_adb_used=True,
        local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
        recovery_action=None if available else central_recovery_action("local_adb_check_failed"),
    )
    result["redactions_applied"] = True
    return result


def run_adb_lease_disconnect(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    if not config.get("local_adb_enabled", False):
        mark_local_adb_unavailable(config, state, "local_adb_disabled")
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "local_adb_disabled",
            "Local ADB is disabled in agent config.",
        )
    target = str(config.get("local_adb_target", "127.0.0.1:5555"))
    stdout, stderr, code = run_adb_client_command(config, ["disconnect", target], command)
    mark_local_adb_unavailable(config, state, "disconnected_by_command")
    summary = {
        "attempted": True,
        "configured_target": "redacted",
        "exit_code": code,
    }
    result = complete_text(
        config,
        command,
        started_at,
        start_monotonic,
        json.dumps(summary, sort_keys=True),
        "" if code == 0 else "ADB disconnect failed; inspect private local evidence for raw client output.",
        code,
        local_adb_used=True,
        local_adb_shell_uid=None,
    )
    result["redactions_applied"] = True
    return result


def run_uiautomator_allowlisted_scenario(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    payload = command.get("payload", {})
    if not isinstance(payload, dict):
        return reject_result(config, command, started_at, start_monotonic, "invalid_payload", "Payload must be an object.")
    scenario = payload.get("scenario")
    scenarios = config.get("allowed_uiautomator_scenarios", {})
    if not isinstance(scenario, str) or not isinstance(scenarios, dict) or scenario not in scenarios:
        return reject_result(config, command, started_at, start_monotonic, "uiautomator_scenario_not_allowed", "UIAutomator scenario is not allowlisted.")
    scenario_config = scenarios.get(scenario)
    if not isinstance(scenario_config, dict):
        return reject_result(config, command, started_at, start_monotonic, "bad_uiautomator_scenario_config", "UIAutomator scenario config must be an object.")
    instrumentation = scenario_config.get("instrumentation")
    if not isinstance(instrumentation, str) or "/" not in instrumentation or len(instrumentation) > 240:
        return reject_result(config, command, started_at, start_monotonic, "bad_uiautomator_instrumentation", "UIAutomator instrumentation target is invalid.")

    extras_result = normalize_uiautomator_extras(scenario, scenario_config, payload.get("extras", {}))
    if isinstance(extras_result, str):
        return reject_result(config, command, started_at, start_monotonic, extras_result, "UIAutomator extras were rejected.")
    extras = extras_result

    available, _, _ = ensure_local_adb_for_command(config, state, command)
    if not available:
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "local_adb_unavailable",
            "Local ADB shell is not available for UIAutomator scenario.",
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
            recovery_action=central_recovery_action("local_adb_unavailable"),
        )

    args = ["shell", "am", "instrument", "-w", "-e", "scenario", scenario]
    for key in sorted(extras):
        args.extend(["-e", key, extras[key]])
    args.append(instrumentation)
    raw_stdout, raw_stderr, code = run_adb_command(config, args, command)
    if config.get("return_raw_uiautomator_output") is True:
        return complete_text(
            config,
            command,
            started_at,
            start_monotonic,
            raw_stdout,
            raw_stderr,
            code,
            local_adb_used=True,
            local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
        )

    summary = {
        "scenario": scenario,
        "extra_keys": sorted(extras),
        "instrumentation": "configured",
        "exit_code": code,
        "evidence_mode": "summary_only",
    }
    stderr = "" if code == 0 else "UIAutomator scenario failed; inspect private local evidence for raw instrumentation output."
    result = complete_text(
        config,
        command,
        started_at,
        start_monotonic,
        json.dumps(summary, sort_keys=True),
        stderr,
        code,
        local_adb_used=True,
        local_adb_shell_uid=state.local_adb_state.get("shell_uid"),
    )
    result["redactions_applied"] = True
    return result


def normalize_uiautomator_extras(
    scenario: str,
    scenario_config: dict[str, Any],
    requested: Any,
) -> dict[str, str] | str:
    if not isinstance(requested, dict):
        return "invalid_uiautomator_extras"
    allowed = scenario_config.get("allowed_extras", [])
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        return "bad_uiautomator_allowed_extras"
    allowed_set = set(allowed)
    defaults = scenario_config.get("default_extras", {})
    if not isinstance(defaults, dict):
        return "bad_uiautomator_default_extras"
    merged: dict[str, Any] = dict(defaults)
    merged.update(requested)
    merged["scenario"] = scenario

    result: dict[str, str] = {}
    for key, value in merged.items():
        if key == "scenario":
            continue
        if key not in allowed_set:
            return "uiautomator_extra_not_allowed"
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,48}", key):
            return "uiautomator_extra_key_invalid"
        if isinstance(value, bool):
            normalized = "true" if value else "false"
        elif isinstance(value, int):
            normalized = str(value)
        elif isinstance(value, str):
            normalized = value
        else:
            return "uiautomator_extra_value_invalid"
        if not SAFE_EXTRA_VALUE_RE.fullmatch(normalized):
            return "uiautomator_extra_value_unsafe"
        result[key] = normalized
    return result


def run_termux_agent_restart_status(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
) -> dict[str, Any]:
    status = {
        "agent_process_status": "running",
        "agent_version": AGENT_VERSION,
        "agent_uptime_seconds": round(time.monotonic() - state.started_at, 3),
        "helper_status": str(config.get("helper_status", "unknown")),
        "helper_can_restart_agent": bool(config.get("helper_can_restart_agent", False)),
        "helper_last_restart_attempt": config.get("helper_last_restart_attempt"),
        "termux_run_command_permission_granted": config.get("termux_run_command_permission_granted"),
        "termux_allow_external_apps_observed": config.get("termux_allow_external_apps_observed"),
    }
    return complete_text(config, command, started_at, start_monotonic, json.dumps(status, sort_keys=True), "")


def run_media_projection_preview_boundary(
    config: dict[str, Any],
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
    kind: str,
) -> dict[str, Any]:
    if not config.get("media_projection_preview_enabled", False):
        return reject_result(
            config,
            command,
            started_at,
            start_monotonic,
            "media_projection_preview_not_configured",
            "MediaProjection preview requires a consented helper app and visible active-session indicator.",
        )
    return reject_result(
        config,
        command,
        started_at,
        start_monotonic,
        "media_projection_preview_helper_required",
        f"{kind} must be delegated to an app-owned MediaProjection helper; the Termux agent does not fabricate or bypass consent tokens.",
    )


def mark_local_adb_unavailable(config: dict[str, Any], state: AgentState, reason: str) -> None:
    state.local_adb_state["checked"] = True
    state.local_adb_state["adb_target"] = config.get("local_adb_target", "127.0.0.1:5555")
    state.local_adb_state["available"] = False
    state.local_adb_state["shell_uid"] = None
    state.local_adb_state["last_success_at"] = None
    state.local_adb_state["last_failure_reason"] = reason


def adb_subprocess_env(config: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    tmpdir = config.get("adb_tmpdir") or env.get("TMPDIR")
    if not tmpdir and env.get("PREFIX"):
        tmpdir = str(Path(env["PREFIX"]) / "tmp")
    if tmpdir:
        Path(str(tmpdir)).mkdir(parents=True, exist_ok=True)
        env["TMPDIR"] = str(tmpdir)
    return env


def refresh_local_adb_state(
    config: dict[str, Any],
    state: AgentState,
    timeout: float = 10.0,
) -> tuple[bool, str, str]:
    adb = str(config.get("adb_executable", "adb"))
    target = str(config.get("local_adb_target", "127.0.0.1:5555"))
    state.local_adb_state["checked"] = True
    state.local_adb_state["adb_target"] = target
    env = adb_subprocess_env(config)
    try:
        connect = subprocess.run(
            [adb, "connect", target],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=env,
        )
        ident = subprocess.run(
            [adb, "-s", target, "shell", "id"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        mark_local_adb_unavailable(config, state, str(exc))
        return False, "", str(exc)

    stdout = connect.stdout + ident.stdout
    stderr = connect.stderr + ident.stderr
    shell_uid = "2000" if "uid=2000" in stdout else None
    available = ident.returncode == 0 and shell_uid == "2000"
    state.local_adb_state["available"] = available
    state.local_adb_state["shell_uid"] = shell_uid
    state.local_adb_state["last_success_at"] = utc_now() if available else None
    state.local_adb_state["last_failure_reason"] = None if available else "shell_uid_not_available"
    return available, stdout, stderr


def ensure_local_adb_for_command(
    config: dict[str, Any],
    state: AgentState,
    command: dict[str, Any],
) -> tuple[bool, str, str]:
    if not config.get("local_adb_enabled", False):
        mark_local_adb_unavailable(config, state, "local_adb_disabled")
        return False, "", "local_adb_disabled"
    if state.local_adb_state.get("available") and state.local_adb_state.get("shell_uid") == "2000":
        return True, "", ""
    return refresh_local_adb_state(
        config,
        state,
        timeout=max(1.0, float(command.get("timeout_ms", 10000)) / 1000.0),
    )


def refresh_local_adb_for_heartbeat(config: dict[str, Any], state: AgentState) -> None:
    if not config.get("local_adb_enabled", False):
        return
    if not config.get("check_local_adb_on_heartbeat", False):
        return
    timeout = max(1.0, float(config.get("heartbeat_local_adb_timeout_ms", 5000)) / 1000.0)
    refresh_local_adb_state(config, state, timeout=timeout)


def run_adb_command(
    config: dict[str, Any],
    args: list[str],
    command: dict[str, Any],
) -> tuple[str, str, int]:
    adb = str(config.get("adb_executable", "adb"))
    target = str(config.get("local_adb_target", "127.0.0.1:5555"))
    timeout = max(1.0, float(command.get("timeout_ms", 30000)) / 1000.0)
    try:
        completed = subprocess.run(
            [adb, "-s", target, *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=adb_subprocess_env(config),
        )
    except subprocess.TimeoutExpired as exc:
        return exc.stdout or "", exc.stderr or str(exc), 124
    except OSError as exc:
        return "", str(exc), 127
    return completed.stdout, completed.stderr, completed.returncode


def run_adb_client_command(
    config: dict[str, Any],
    args: list[str],
    command: dict[str, Any],
) -> tuple[str, str, int]:
    adb = str(config.get("adb_executable", "adb"))
    timeout = max(1.0, float(command.get("timeout_ms", 30000)) / 1000.0)
    try:
        completed = subprocess.run(
            [adb, *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=adb_subprocess_env(config),
        )
    except subprocess.TimeoutExpired as exc:
        return exc.stdout or "", exc.stderr or str(exc), 124
    except OSError as exc:
        return "", str(exc), 127
    return completed.stdout, completed.stderr, completed.returncode


def central_recovery_action(reason: str) -> dict[str, Any]:
    return {
        "kind": "central_direct_adb_recovery",
        "reason": reason,
        "recommended": True,
        "notes": "Use an external approved ADB route to restore or validate the local WiFi ADB lease.",
    }


def normalize_update_manifest(config: dict[str, Any], payload: Any) -> dict[str, Any] | str:
    if not isinstance(payload, dict):
        return "invalid_update_payload"
    manifest = payload.get("manifest", payload)
    if not isinstance(manifest, dict):
        return "invalid_update_manifest"
    if manifest.get("schema") != APK_UPDATE_MANIFEST_SCHEMA:
        return "unsupported_update_manifest_schema"
    package_name = manifest.get("package_name")
    if not isinstance(package_name, str) or not package_name:
        return "package_name_missing"
    package_policy = dict(config.get("allowed_update_packages", {})).get(package_name)
    if not isinstance(package_policy, dict):
        return "package_not_allowed"
    version_code = manifest.get("version_code")
    if not isinstance(version_code, int) or version_code <= 0:
        return "version_code_invalid"
    apk_url = manifest.get("apk_url")
    if not isinstance(apk_url, str) or not is_allowed_apk_url(config, apk_url):
        return "apk_url_not_https"
    sha256 = manifest.get("sha256")
    if not isinstance(sha256, str) or not SHA256_RE.match(sha256):
        return "sha256_invalid"
    signing_cert_sha256 = manifest.get("signing_cert_sha256")
    if not isinstance(signing_cert_sha256, str) or not SHA256_RE.match(signing_cert_sha256):
        return "signing_cert_sha256_invalid"
    expected_signing = package_policy.get("signing_cert_sha256")
    if isinstance(expected_signing, str) and signing_cert_sha256.lower() != expected_signing.lower():
        return "signing_cert_not_allowed"
    rollout_ring = manifest.get("rollout_ring")
    allowed_rings = set(package_policy.get("allowed_rollout_rings", []))
    if not isinstance(rollout_ring, str) or rollout_ring not in allowed_rings:
        return "rollout_ring_not_allowed"
    launch_component = manifest.get("launch_component")
    if manifest.get("launch_after_install") and (
        not isinstance(launch_component, str) or not is_launch_component_allowed(config, launch_component, package_name)
    ):
        return "launch_component_not_allowed"
    return {
        "schema": APK_UPDATE_MANIFEST_SCHEMA,
        "package_name": package_name,
        "version_code": version_code,
        "version_name": str(manifest.get("version_name", "")),
        "apk_url": apk_url,
        "sha256": sha256.lower(),
        "signing_cert_sha256": signing_cert_sha256.lower(),
        "rollout_ring": rollout_ring,
        "launch_after_install": bool(manifest.get("launch_after_install", False)),
        "launch_component": launch_component,
        "allow_downgrade": bool(manifest.get("allow_downgrade", False)),
    }


def is_https_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme == "https" and bool(parsed.netloc)


def is_allowed_apk_url(config: dict[str, Any], value: str) -> bool:
    if is_https_url(value):
        return True
    if not config.get("allow_insecure_loopback_apk_urls", False):
        return False
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def is_launch_component_allowed(config: dict[str, Any], component: str, package_name: str | None = None) -> bool:
    if component in set(config.get("allowed_launch_components", [])):
        return True
    if package_name is None:
        package_name = component.split("/", 1)[0] if "/" in component else None
    if package_name:
        package_policy = dict(config.get("allowed_update_packages", {})).get(package_name, {})
        if component in set(package_policy.get("launch_components", [])):
            return True
    return False


def make_update_report(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "quest-termux-lab.apk-update-report.v1",
        "package_name": manifest["package_name"],
        "requested_version_code": manifest["version_code"],
        "requested_version_name": manifest.get("version_name") or None,
        "rollout_ring": manifest["rollout_ring"],
        "apk_sha256_verified": False,
        "signing_cert_verified": False,
        "apk_package_verified": False,
        "install_attempted": False,
        "installed_version_code": None,
        "installed_version_name": None,
        "previous_version_code": None,
        "previous_version_name": None,
        "launch_attempted": False,
        "launch_component": None,
    }


def make_rollback_report(
    status: str,
    previous_version_code: int | None,
    previous_version_name: str | None,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "schema": "quest-termux-lab.apk-update-rollback-report.v1",
        "status": status,
        "previous_version_code": previous_version_code,
        "previous_version_name": previous_version_name,
        "rollback_attempted": False,
        "reason": reason,
    }


def download_verified_apk(config: dict[str, Any], manifest: dict[str, Any], command: dict[str, Any]) -> Path | str:
    workspace = Path(str(config.get("workspace_root", "runs/fleet-agent")))
    updates_dir = workspace / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    apk_path = updates_dir / f"{manifest['package_name']}-{manifest['version_code']}.apk"
    tmp_path = apk_path.with_suffix(".apk.part")
    digest = hashlib.sha256()
    timeout = max(1.0, float(command.get("timeout_ms", 120000)) / 1000.0)
    try:
        request = Request(manifest["apk_url"], headers={"Accept": "application/vnd.android.package-archive"})
        with urlopen(request, timeout=timeout) as response, tmp_path.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        return "apk_download_failed"
    actual = digest.hexdigest()
    if actual.lower() != manifest["sha256"].lower():
        tmp_path.unlink(missing_ok=True)
        return "sha256_mismatch"
    tmp_path.replace(apk_path)
    return apk_path


def verify_apk_metadata(
    config: dict[str, Any],
    apk_path: Path,
    manifest: dict[str, Any],
    command: dict[str, Any],
) -> dict[str, Any] | str:
    package_name, version_code, version_name = read_apk_badging(config, apk_path, command)
    if package_name != manifest["package_name"]:
        return "apk_package_mismatch"
    if version_code != manifest["version_code"]:
        return "apk_version_code_mismatch"
    signing_digest = read_apk_signing_cert_sha256(config, apk_path, command)
    if signing_digest is None:
        return "apk_signing_cert_unreadable"
    if signing_digest.lower() != manifest["signing_cert_sha256"].lower():
        return "apk_signing_cert_mismatch"
    return {
        "apk_sha256_verified": True,
        "signing_cert_verified": True,
        "apk_package_verified": True,
        "apk_version_name": version_name,
    }


def read_apk_badging(config: dict[str, Any], apk_path: Path, command: dict[str, Any]) -> tuple[str | None, int | None, str | None]:
    timeout = max(1.0, float(command.get("timeout_ms", 30000)) / 1000.0)
    candidates = [
        [str(config.get("aapt2_executable", "aapt2")), "dump", "badging", str(apk_path)],
        [str(config.get("aapt_executable", "aapt")), "dump", "badging", str(apk_path)],
    ]
    for argv in candidates:
        try:
            completed = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if completed.returncode != 0:
            continue
        match = re.search(r"package: name='([^']+)'.*versionCode='(\d+)'.*versionName='([^']*)'", completed.stdout)
        if match:
            return match.group(1), int(match.group(2)), match.group(3)
    return None, None, None


def read_apk_signing_cert_sha256(config: dict[str, Any], apk_path: Path, command: dict[str, Any]) -> str | None:
    timeout = max(1.0, float(command.get("timeout_ms", 30000)) / 1000.0)
    apksigner = str(config.get("apksigner_executable", "apksigner"))
    try:
        completed = subprocess.run(
            [apksigner, "verify", "--print-certs", str(apk_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        if "certificate SHA-256 digest:" in line:
            _, value = line.split(":", 1)
            return value.strip().replace(":", "").lower()
    return None


def installed_version(config: dict[str, Any], package_name: str, command: dict[str, Any]) -> tuple[int | None, str | None]:
    stdout, _, code = run_adb_command(config, ["shell", "dumpsys", "package", package_name], command)
    if code != 0:
        return None, None
    version_code_match = re.search(r"versionCode=(\d+)", stdout)
    version_name_match = re.search(r"versionName=([^\s]+)", stdout)
    version_code = int(version_code_match.group(1)) if version_code_match else None
    version_name = version_name_match.group(1) if version_name_match else None
    return version_code, version_name


def adb_install(config: dict[str, Any], apk_path: Path, manifest: dict[str, Any], command: dict[str, Any]) -> tuple[str, str, int]:
    args = ["install", "-r"]
    if manifest.get("allow_downgrade"):
        args.append("-d")
    args.append(str(apk_path))
    return run_adb_command(config, args, command)


def adb_launch_component(config: dict[str, Any], component: str, command: dict[str, Any]) -> tuple[str, str, int]:
    if not component or not is_launch_component_allowed(config, component):
        return "", "launch component is not allowlisted", 2
    return run_adb_command(config, ["shell", "am", "start", "-W", "-n", component], command)


def remember_idempotent_result(state: AgentState, command: dict[str, Any], result: dict[str, Any]) -> None:
    idem = command.get("idempotency_key")
    if isinstance(idem, str) and idem:
        state.completed_idempotency[idem] = dict(result)


def run_once(config: dict[str, Any], state: AgentState) -> None:
    refresh_local_adb_for_heartbeat(config, state)
    heartbeat = make_heartbeat(config, state, central_reachable=False)
    try:
        heartbeat["central_reachable"] = True
        post_json(central_url(config, f"{API_PREFIX}/heartbeat"), heartbeat)
    except URLError as exc:
        heartbeat["central_reachable"] = False
        state.last_error_code = "heartbeat_failed"
        write_jsonl(config, "errors.jsonl", {"observed_at": utc_now(), "error": str(exc)})
        return
    finally:
        write_jsonl(config, "heartbeats.jsonl", heartbeat)

    command = get_json(central_url(config, f"{API_PREFIX}/agents/{config['agent_id']}/next-command"))
    if command.get("schema") == NO_COMMAND_SCHEMA:
        return
    result = execute_command(config, state, command)
    state.last_command_id = str(result.get("command_id"))
    state.last_command_status = str(result.get("status"))
    state.last_error_code = result.get("error_code") if isinstance(result.get("error_code"), str) else None
    write_jsonl(config, "results.jsonl", result)
    post_json(central_url(config, f"{API_PREFIX}/command-results"), result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an outbound-only Termux fleet agent.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=0)
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    state = AgentState(started_at=time.monotonic())
    interval = max(0.1, float(config.get("poll_interval_seconds", 2.0)))
    count = 0
    while True:
        run_once(config, state)
        count += 1
        if args.once:
            return 0
        if args.max_iterations and count >= args.max_iterations:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
