#!/usr/bin/env python3
"""Outbound-only Termux fleet agent prototype.

The agent posts heartbeats to a central control plane, polls for one command,
executes only allowlisted bounded commands, and posts the result. It uses only
the Python standard library so it can run in a small Termux environment.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


API_PREFIX = "/api/fleet/v1"
HEARTBEAT_SCHEMA = "quest-termux-lab.fleet-agent-heartbeat.v1"
COMMAND_SCHEMA = "quest-termux-lab.fleet-command-request.v1"
RESULT_SCHEMA = "quest-termux-lab.fleet-command-result.v1"
NO_COMMAND_SCHEMA = "quest-termux-lab.fleet-no-command.v1"
AGENT_VERSION = "0.1.0"


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
        "redactions_applied": False,
    }


def reject_result(
    config: dict[str, Any],
    command: dict[str, Any],
    started_at: str,
    start_monotonic: float,
    code: str,
    message: str,
) -> dict[str, Any]:
    result = result_base(config, command, started_at, start_monotonic)
    result["error_code"] = code
    result["error_message"] = message
    result["finished_at"] = utc_now()
    result["duration_ms"] = int((time.monotonic() - start_monotonic) * 1000)
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

    if command.get("requires_local_adb_shell") and not state.local_adb_state.get("available"):
        return reject_result(config, command, started_at, start_monotonic, "local_adb_unavailable", "Local ADB shell is not available.")

    if kind == "agent.status":
        return complete_text(config, command, started_at, start_monotonic, agent_status_text(config, state), "")
    if kind == "agent.capabilities":
        return complete_text(config, command, started_at, start_monotonic, agent_capabilities_text(config), "")
    if kind == "termux.exec_allowlisted":
        return run_alias(config, command, started_at, start_monotonic)
    if kind == "adb.self_check":
        return run_adb_self_check(config, state, command, started_at, start_monotonic)

    return reject_result(config, command, started_at, start_monotonic, "kind_unimplemented", "Command kind is recognized but not implemented in this prototype.")


def agent_status_text(config: dict[str, Any], state: AgentState) -> str:
    return json.dumps(
        {
            "agent_id": config["agent_id"],
            "agent_version": AGENT_VERSION,
            "status": "alive",
            "sequence": state.sequence,
            "python": platform.python_version(),
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
        },
        sort_keys=True,
    )


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
    state.local_adb_state["checked"] = True
    state.local_adb_state["adb_target"] = config.get("local_adb_target", "127.0.0.1:5555")
    if not config.get("local_adb_enabled", False):
        state.local_adb_state["available"] = False
        state.local_adb_state["shell_uid"] = None
        state.local_adb_state["last_failure_reason"] = "local_adb_disabled"
        return reject_result(config, command, started_at, start_monotonic, "local_adb_disabled", "Local ADB is disabled in agent config.")

    adb = str(config.get("adb_executable", "adb"))
    target = str(config.get("local_adb_target", "127.0.0.1:5555"))
    timeout = max(1.0, float(command.get("timeout_ms", 10000)) / 1000.0)
    try:
        connect = subprocess.run([adb, "connect", target], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        ident = subprocess.run([adb, "-s", target, "shell", "id"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        state.local_adb_state["available"] = False
        state.local_adb_state["shell_uid"] = None
        state.local_adb_state["last_failure_reason"] = str(exc)
        return reject_result(config, command, started_at, start_monotonic, "local_adb_check_failed", str(exc))

    stdout = connect.stdout + ident.stdout
    stderr = connect.stderr + ident.stderr
    shell_uid = "2000" if "uid=2000" in stdout else None
    available = ident.returncode == 0 and shell_uid == "2000"
    state.local_adb_state["available"] = available
    state.local_adb_state["shell_uid"] = shell_uid
    state.local_adb_state["last_success_at"] = utc_now() if available else None
    state.local_adb_state["last_failure_reason"] = None if available else "shell_uid_not_available"
    return complete_text(
        config,
        command,
        started_at,
        start_monotonic,
        stdout,
        stderr,
        0 if available else 1,
        local_adb_used=True,
        local_adb_shell_uid=shell_uid,
    )


def run_once(config: dict[str, Any], state: AgentState) -> None:
    heartbeat = make_heartbeat(config, state, central_reachable=False)
    try:
        post_json(central_url(config, f"{API_PREFIX}/heartbeat"), heartbeat)
        heartbeat["central_reachable"] = True
    except URLError as exc:
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
