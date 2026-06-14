#!/usr/bin/env python3
"""Minimal outbound fleet control-plane prototype.

This is a public-safe simulator/controller for Termux fleet agents. It keeps
all state in memory and optional JSONL logs. It does not use ADB, discover
devices, install APKs, or talk to a headset by itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


API_PREFIX = "/api/fleet/v1"
MIRROR_API_PREFIX = "/api/mirror/v1"
NO_COMMAND_SCHEMA = "quest-termux-lab.fleet-no-command.v1"
HEARTBEAT_SCHEMA = "quest-termux-lab.fleet-agent-heartbeat.v1"
COMMAND_SCHEMA = "quest-termux-lab.fleet-command-request.v1"
RESULT_SCHEMA = "quest-termux-lab.fleet-command-result.v1"
MIRROR_LEASE_SCHEMA = "quest-termux-lab.mirror-session-lease.v1"
MIRROR_INTENT_SCHEMA = "quest-termux-lab.mirror-command-intent.v1"
MIRROR_EVENT_SCHEMA = "quest-termux-lab.mirror-command-event.v1"
MIRROR_SESSION_SUMMARY_SCHEMA = "quest-termux-lab.mirror-session-summary.v1"
PASSIVE_COMMAND_KINDS = {"agent.status", "agent.capabilities"}
MIRROR_ADB_ACTION_KINDS = {
    "android.foreground_snapshot",
    "app.launch_allowlisted",
    "uiautomator.run_allowlisted_scenario",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def response(status: str, **extra: Any) -> dict[str, Any]:
    data = {"status": status, "observed_at": utc_now()}
    data.update(extra)
    return data


@dataclass
class FleetState:
    """In-memory fleet state with optional JSONL audit output."""

    log_dir: Path | None = None
    heartbeats: dict[str, dict[str, Any]] = field(default_factory=dict)
    commands: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    idempotency_index: dict[str, str] = field(default_factory=dict)
    mirror_leases: dict[str, dict[str, Any]] = field(default_factory=dict)
    mirror_intents: dict[str, dict[str, Any]] = field(default_factory=dict)
    mirror_events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    mirror_command_index: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.log_dir is not None:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        if self.log_dir is None:
            return
        path = self.log_dir / name
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def record_heartbeat(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("schema") != HEARTBEAT_SCHEMA:
            raise ValueError("unsupported heartbeat schema")
        agent_id = require_text(payload, "agent_id")
        self.heartbeats[agent_id] = dict(payload)
        self._append_jsonl("heartbeats.jsonl", payload)
        return response("accepted", agent_id=agent_id)

    def queue_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("schema") != COMMAND_SCHEMA:
            raise ValueError("unsupported command schema")
        command_id = require_text(payload, "command_id")
        target_agent_id = require_text(payload, "target_agent_id")
        idempotency_key = require_text(payload, "idempotency_key")
        if is_expired(payload):
            raise ValueError("command is already expired")
        kind = require_text(payload, "kind")
        if kind not in PASSIVE_COMMAND_KINDS:
            require_text(payload, "remote_session_lease_id")
        idempotency_id = f"{target_agent_id}:{idempotency_key}"
        if idempotency_id in self.idempotency_index:
            existing = self.idempotency_index[idempotency_id]
            return response(
                "duplicate",
                command_id=command_id,
                target_agent_id=target_agent_id,
                existing_command_id=existing,
            )
        self.idempotency_index[idempotency_id] = command_id
        self.commands.setdefault(target_agent_id, []).append(dict(payload))
        self._append_jsonl("commands.jsonl", payload)
        return response("queued", command_id=command_id, target_agent_id=target_agent_id)

    def next_command(self, agent_id: str) -> dict[str, Any]:
        queue = self.commands.setdefault(agent_id, [])
        kept: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        for command in queue:
            if is_expired(command):
                idempotency_key = command.get("idempotency_key")
                if isinstance(idempotency_key, str):
                    self.idempotency_index.pop(f"{agent_id}:{idempotency_key}", None)
                self._append_jsonl(
                    "expired-commands.jsonl",
                    {
                        "schema": "quest-termux-lab.fleet-expired-command.v1",
                        "command_id": command.get("command_id"),
                        "target_agent_id": command.get("target_agent_id"),
                        "expired_at": utc_now(),
                    },
                )
                continue
            if selected is None:
                selected = command
            else:
                kept.append(command)
        self.commands[agent_id] = kept
        if selected is not None:
            return selected
        return {
            "schema": NO_COMMAND_SCHEMA,
            "agent_id": agent_id,
            "status": "empty",
            "observed_at": utc_now(),
        }

    def record_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("schema") != RESULT_SCHEMA:
            raise ValueError("unsupported result schema")
        command_id = require_text(payload, "command_id")
        agent_id = require_text(payload, "agent_id")
        self.results.append(dict(payload))
        self._append_jsonl("results.jsonl", payload)
        self._record_mirror_result(command_id, payload)
        return response("accepted", command_id=command_id, agent_id=agent_id)

    def create_mirror_lease(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("schema") != MIRROR_LEASE_SCHEMA:
            raise ValueError("unsupported mirror lease schema")
        lease_id = require_text(payload, "lease_id")
        require_text(payload, "operator_id")
        source_agent_id = require_text(payload, "source_agent_id")
        target_agent_id = require_text(payload, "target_agent_id")
        if source_agent_id == target_agent_id:
            raise ValueError("mirror source and target must differ")
        require_text(payload, "fleet_id")
        require_text(payload, "purpose")
        require_text(payload, "consent_mode")
        require_bool(payload, "active_indicator_required")
        require_bool(payload, "emergency_stop_supported")
        require_future_expiry(payload, "mirror lease")
        kinds = require_text_list(payload, "allowed_command_kinds")
        if not kinds:
            raise ValueError("mirror lease must allow at least one command kind")
        lease = dict(payload)
        lease["revoked"] = bool(lease.get("revoked", False))
        self.mirror_leases[lease_id] = lease
        self._append_jsonl("mirror-leases.jsonl", lease)
        return response(
            "accepted",
            lease_id=lease_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
        )

    def revoke_mirror_lease(self, lease_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if lease_id not in self.mirror_leases:
            raise ValueError("mirror lease missing")
        lease = dict(self.mirror_leases[lease_id])
        lease["revoked"] = True
        lease["revoked_at"] = utc_now()
        if isinstance(payload, dict) and isinstance(payload.get("revoked_by"), str):
            lease["revoked_by"] = payload["revoked_by"]
        self.mirror_leases[lease_id] = lease
        record = {
            "schema": "quest-termux-lab.mirror-session-revocation.v1",
            "lease_id": lease_id,
            "revoked_at": lease["revoked_at"],
            "revoked_by": lease.get("revoked_by"),
            "reason": payload.get("reason") if isinstance(payload, dict) else None,
        }
        self._append_jsonl("mirror-lease-revocations.jsonl", record)
        return response("revoked", lease_id=lease_id)

    def submit_mirror_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("schema") != MIRROR_INTENT_SCHEMA:
            raise ValueError("unsupported mirror intent schema")
        mirror_intent_id = require_text(payload, "mirror_intent_id")
        require_text(payload, "source_agent_id")
        require_text(payload, "target_agent_id")
        if mirror_intent_id in self.mirror_intents:
            existing = self.mirror_intents[mirror_intent_id]
            return response(
                "duplicate",
                mirror_intent_id=mirror_intent_id,
                command_id=existing.get("command_id"),
                state=existing.get("state"),
            )
        lease_id = require_text(payload, "lease_id")
        try:
            require_future_expiry(payload, "mirror intent")
        except ValueError as exc:
            return self.reject_mirror_intent(payload, "mirror_intent_expired", str(exc))
        lease = self.mirror_leases.get(lease_id)
        if lease is None:
            return self.reject_mirror_intent(payload, "mirror_lease_missing", "Mirror lease is missing.")
        lease_error = validate_mirror_lease_for_intent(lease, payload)
        if lease_error is not None:
            return self.reject_mirror_intent(payload, lease_error, lease_error.replace("_", " "))

        command = mirror_intent_to_fleet_command(payload)
        try:
            queued = self.queue_command(command)
        except ValueError as exc:
            return self.reject_mirror_intent(payload, "mirror_queue_rejected", str(exc))
        command_id = str(queued.get("existing_command_id") or command["command_id"])
        event = mirror_event(payload, command_id, "queued_for_target", controller_status=str(queued.get("status")))
        intent_status = {
            "schema": "quest-termux-lab.mirror-intent-status.v1",
            "mirror_intent_id": mirror_intent_id,
            "lease_id": lease_id,
            "source_agent_id": payload.get("source_agent_id"),
            "target_agent_id": payload.get("target_agent_id"),
            "command_id": command_id,
            "state": event["state"],
            "controller_status": event["controller_status"],
            "submitted_at": utc_now(),
            "updated_at": event["observed_at"],
            "target_result": None,
            "error_code": None,
            "error_message": None,
        }
        self.mirror_intents[mirror_intent_id] = intent_status
        self.mirror_command_index.setdefault(command_id, []).append(mirror_intent_id)
        self.mirror_events.setdefault(lease_id, []).append(event)
        self._append_jsonl("mirror-intents.jsonl", payload)
        self._append_jsonl("mirror-events.jsonl", event)
        return response(
            "queued_for_target",
            mirror_intent_id=mirror_intent_id,
            lease_id=lease_id,
            command_id=command_id,
            controller_status=queued.get("status"),
        )

    def reject_mirror_intent(self, payload: dict[str, Any], code: str, message: str) -> dict[str, Any]:
        mirror_intent_id = require_text(payload, "mirror_intent_id")
        lease_id = require_text(payload, "lease_id")
        command_id = mirror_command_id(mirror_intent_id)
        event = mirror_event(
            payload,
            command_id,
            "rejected",
            controller_status="rejected",
            error_code=code,
            error_message=message,
        )
        intent_status = {
            "schema": "quest-termux-lab.mirror-intent-status.v1",
            "mirror_intent_id": mirror_intent_id,
            "lease_id": lease_id,
            "source_agent_id": payload.get("source_agent_id"),
            "target_agent_id": payload.get("target_agent_id"),
            "command_id": command_id,
            "state": "rejected",
            "controller_status": "rejected",
            "submitted_at": utc_now(),
            "updated_at": event["observed_at"],
            "target_result": None,
            "error_code": code,
            "error_message": message,
        }
        self.mirror_intents[mirror_intent_id] = intent_status
        self.mirror_events.setdefault(lease_id, []).append(event)
        self._append_jsonl("mirror-intents.jsonl", payload)
        self._append_jsonl("mirror-events.jsonl", event)
        return response(
            "rejected",
            mirror_intent_id=mirror_intent_id,
            lease_id=lease_id,
            command_id=command_id,
            state="rejected",
            error_code=code,
            error_message=message,
        )

    def mirror_intent_status(self, mirror_intent_id: str) -> dict[str, Any]:
        status = self.mirror_intents.get(mirror_intent_id)
        if status is None:
            raise ValueError("mirror intent missing")
        return dict(status)

    def mirror_session_events(self, lease_id: str) -> dict[str, Any]:
        lease = self.mirror_leases.get(lease_id)
        events = list(self.mirror_events.get(lease_id, []))
        fleet_id = lease.get("fleet_id") if isinstance(lease, dict) else ""
        return {
            "schema": MIRROR_SESSION_SUMMARY_SCHEMA,
            "fleet_id": fleet_id,
            "lease_id": lease_id,
            "observed_at": utc_now(),
            "event_count": len(events),
            "events": events,
        }

    def _record_mirror_result(self, command_id: str, result: dict[str, Any]) -> None:
        intent_ids = self.mirror_command_index.get(command_id, [])
        if not intent_ids:
            return
        state = mirror_state_from_result(result)
        for mirror_intent_id in intent_ids:
            current = self.mirror_intents.get(mirror_intent_id)
            if current is None:
                continue
            current = dict(current)
            current["state"] = state
            current["target_result"] = dict(result)
            current["updated_at"] = utc_now()
            self.mirror_intents[mirror_intent_id] = current
            event = {
                "schema": MIRROR_EVENT_SCHEMA,
                "mirror_intent_id": mirror_intent_id,
                "lease_id": current["lease_id"],
                "source_agent_id": current["source_agent_id"],
                "target_agent_id": current["target_agent_id"],
                "command_id": command_id,
                "state": state,
                "observed_at": current["updated_at"],
                "target_result": dict(result),
                "controller_status": "accepted",
                "error_code": None,
                "error_message": None,
            }
            self.mirror_events.setdefault(str(current["lease_id"]), []).append(event)
            self._append_jsonl("mirror-events.jsonl", event)

    def recovery_candidates(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        latest_result_by_agent: dict[str, dict[str, Any]] = {}
        for result in self.results:
            agent_id = result.get("agent_id")
            if isinstance(agent_id, str):
                latest_result_by_agent[agent_id] = result

        for agent_id, heartbeat in sorted(self.heartbeats.items()):
            local_adb = heartbeat.get("local_adb", {})
            reason = None
            if isinstance(local_adb, dict):
                if local_adb.get("checked") and not local_adb.get("available"):
                    reason = local_adb.get("last_failure_reason") or "local_adb_unavailable"
                elif not local_adb.get("checked"):
                    reason = "local_adb_not_checked"
            latest_result = latest_result_by_agent.get(agent_id)
            if latest_result and latest_result.get("error_code") == "local_adb_unavailable":
                reason = "local_adb_unavailable_after_command"
            if reason:
                candidates.append(
                    {
                        "agent_id": agent_id,
                        "reason": reason,
                        "recommended_action": "central_direct_adb_recovery",
                    }
                )
        return candidates

    def summary(self) -> dict[str, Any]:
        queued = sum(len(commands) for commands in self.commands.values())
        latest_agents = sorted(self.heartbeats)
        return {
            "schema": "quest-termux-lab.fleet-summary.v1",
            "observed_at": utc_now(),
            "agent_count": len(self.heartbeats),
            "agents": latest_agents,
            "queued_command_count": queued,
            "result_count": len(self.results),
            "recovery_candidates": self.recovery_candidates(),
        }


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing {key}")
    return value


def require_text_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"missing {key}")
    return list(value)


def require_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"missing {key}")
    return value


def require_future_expiry(payload: dict[str, Any], label: str) -> None:
    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, str):
        raise ValueError(f"{label} is missing expires_at")
    try:
        expires = parse_time(expires_at)
    except ValueError as exc:
        raise ValueError(f"{label} has invalid expires_at") from exc
    if expires <= datetime.now(timezone.utc):
        raise ValueError(f"{label} is already expired")


def is_expired(command: dict[str, Any]) -> bool:
    expires_at = command.get("expires_at")
    if not isinstance(expires_at, str):
        return True
    return parse_time(expires_at) <= datetime.now(timezone.utc)


def validate_mirror_lease_for_intent(lease: dict[str, Any], intent: dict[str, Any]) -> str | None:
    if lease.get("revoked"):
        return "mirror_lease_revoked"
    if lease.get("fleet_id") != intent.get("fleet_id"):
        return "mirror_lease_fleet_mismatch"
    if lease.get("source_agent_id") != intent.get("source_agent_id"):
        return "mirror_source_not_allowed"
    if lease.get("target_agent_id") != intent.get("target_agent_id"):
        return "mirror_target_not_allowed"
    expires_at = lease.get("expires_at")
    if not isinstance(expires_at, str):
        return "mirror_lease_missing_expiry"
    try:
        if parse_time(expires_at) <= datetime.now(timezone.utc):
            return "mirror_lease_expired"
    except ValueError:
        return "mirror_lease_bad_expiry"
    kind = intent.get("kind")
    allowed = lease.get("allowed_command_kinds")
    if not isinstance(allowed, list) or kind not in set(allowed):
        return "mirror_kind_not_allowed"
    if (
        kind in MIRROR_ADB_ACTION_KINDS
        and lease.get("requires_local_adb_shell_for_adb_commands") is True
        and intent.get("requires_local_adb_shell") is not True
    ):
        return "mirror_adb_requirement_missing"
    return None


def mirror_command_id(mirror_intent_id: str) -> str:
    return f"mirror-{mirror_intent_id}"


def mirror_intent_to_fleet_command(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": COMMAND_SCHEMA,
        "fleet_id": intent["fleet_id"],
        "command_id": mirror_command_id(str(intent["mirror_intent_id"])),
        "target_agent_id": intent["target_agent_id"],
        "origin": "mirror",
        "issued_at": intent["issued_at"],
        "expires_at": intent["expires_at"],
        "idempotency_key": intent["idempotency_key"],
        "kind": intent["kind"],
        "remote_session_lease_id": intent["lease_id"],
        "requires_local_adb_shell": bool(intent["requires_local_adb_shell"]),
        "timeout_ms": int(intent.get("timeout_ms", 10000)),
        "max_stdout_bytes": int(intent.get("max_stdout_bytes", 4096)),
        "max_stderr_bytes": int(intent.get("max_stderr_bytes", 4096)),
        "payload": dict(intent.get("payload", {})),
        "sensitivity": intent.get("sensitivity", "local_only"),
        "requested_by": f"mirror:{intent['source_agent_id']}",
        "reason": intent["reason"],
        "source_agent_id": intent["source_agent_id"],
        "mirror_intent_id": intent["mirror_intent_id"],
    }


def mirror_event(
    intent: dict[str, Any],
    command_id: str,
    state: str,
    controller_status: str | None = None,
    target_result: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": MIRROR_EVENT_SCHEMA,
        "mirror_intent_id": intent["mirror_intent_id"],
        "lease_id": intent["lease_id"],
        "source_agent_id": intent["source_agent_id"],
        "target_agent_id": intent["target_agent_id"],
        "command_id": command_id,
        "state": state,
        "observed_at": utc_now(),
        "target_result": target_result,
        "controller_status": controller_status,
        "error_code": error_code,
        "error_message": error_message,
    }


def mirror_state_from_result(result: dict[str, Any]) -> str:
    status = result.get("status")
    if status in {"completed", "rejected", "failed", "timeout", "skipped"}:
        return str(status)
    return "failed"


class FleetHandler(BaseHTTPRequestHandler):
    server: "FleetServer"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == f"{API_PREFIX}/summary":
            self._send_json(200, self.server.state.summary())
            return
        mirror_intent_prefix = f"{MIRROR_API_PREFIX}/intents/"
        if parsed.path.startswith(mirror_intent_prefix):
            mirror_intent_id = parsed.path[len(mirror_intent_prefix) :]
            if not mirror_intent_id:
                self._send_error(400, "missing mirror intent id")
                return
            try:
                self._send_json(200, self.server.state.mirror_intent_status(mirror_intent_id))
            except ValueError as exc:
                self._send_error(404, str(exc))
            return
        mirror_session_prefix = f"{MIRROR_API_PREFIX}/sessions/"
        mirror_session_suffix = "/events"
        if parsed.path.startswith(mirror_session_prefix) and parsed.path.endswith(mirror_session_suffix):
            lease_id = parsed.path[len(mirror_session_prefix) : -len(mirror_session_suffix)]
            if not lease_id:
                self._send_error(400, "missing mirror lease id")
                return
            self._send_json(200, self.server.state.mirror_session_events(lease_id))
            return
        prefix = f"{API_PREFIX}/agents/"
        suffix = "/next-command"
        if parsed.path.startswith(prefix) and parsed.path.endswith(suffix):
            agent_id = parsed.path[len(prefix) : -len(suffix)]
            if not agent_id:
                self._send_error(400, "missing agent id")
                return
            self._send_json(200, self.server.state.next_command(agent_id))
            return
        self._send_error(404, "unknown route")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == f"{API_PREFIX}/heartbeat":
                self._send_json(200, self.server.state.record_heartbeat(payload))
                return
            if parsed.path == f"{API_PREFIX}/commands":
                self._send_json(200, self.server.state.queue_command(payload))
                return
            if parsed.path == f"{API_PREFIX}/command-results":
                self._send_json(200, self.server.state.record_result(payload))
                return
            if parsed.path == f"{MIRROR_API_PREFIX}/leases":
                self._send_json(200, self.server.state.create_mirror_lease(payload))
                return
            if parsed.path == f"{MIRROR_API_PREFIX}/intents":
                self._send_json(200, self.server.state.submit_mirror_intent(payload))
                return
            mirror_lease_prefix = f"{MIRROR_API_PREFIX}/leases/"
            mirror_revoke_suffix = "/revoke"
            if parsed.path.startswith(mirror_lease_prefix) and parsed.path.endswith(mirror_revoke_suffix):
                lease_id = parsed.path[len(mirror_lease_prefix) : -len(mirror_revoke_suffix)]
                if not lease_id:
                    self._send_error(400, "missing mirror lease id")
                    return
                self._send_json(200, self.server.state.revoke_mirror_lease(lease_id, payload))
                return
            self._send_error(404, "unknown route")
        except ValueError as exc:
            self._send_error(400, str(exc))

    def log_message(self, format: str, *args: Any) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(format, *args)

    def _read_json(self) -> dict[str, Any]:
        length_text = self.headers.get("Content-Length")
        if not length_text:
            raise ValueError("missing request body")
        try:
            length = int(length_text)
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, response("error", error=message))


class FleetServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: FleetState, quiet: bool = False):
        super().__init__(server_address, FleetHandler)
        self.state = state
        self.quiet = quiet


def run_server(args: argparse.Namespace) -> int:
    log_dir = Path(args.log_dir) if args.log_dir else None
    state = FleetState(log_dir=log_dir)
    server = FleetServer((args.host, args.port), state, quiet=args.quiet)
    print(f"fleet_control_plane_listening http://{args.host}:{args.port}{API_PREFIX}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("fleet_control_plane_stopped")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a minimal fleet control-plane server.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--log-dir", default="")
    serve.add_argument("--quiet", action="store_true")
    serve.set_defaults(func=run_server)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
