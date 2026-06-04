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
NO_COMMAND_SCHEMA = "quest-termux-lab.fleet-no-command.v1"
HEARTBEAT_SCHEMA = "quest-termux-lab.fleet-agent-heartbeat.v1"
COMMAND_SCHEMA = "quest-termux-lab.fleet-command-request.v1"
RESULT_SCHEMA = "quest-termux-lab.fleet-command-result.v1"


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
        if is_expired(payload):
            raise ValueError("command is already expired")
        self.commands.setdefault(target_agent_id, []).append(dict(payload))
        self._append_jsonl("commands.jsonl", payload)
        return response("queued", command_id=command_id, target_agent_id=target_agent_id)

    def next_command(self, agent_id: str) -> dict[str, Any]:
        queue = self.commands.setdefault(agent_id, [])
        kept: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        for command in queue:
            if is_expired(command):
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
        return response("accepted", command_id=command_id, agent_id=agent_id)

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
        }


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing {key}")
    return value


def is_expired(command: dict[str, Any]) -> bool:
    expires_at = command.get("expires_at")
    if not isinstance(expires_at, str):
        return True
    return parse_time(expires_at) <= datetime.now(timezone.utc)


class FleetHandler(BaseHTTPRequestHandler):
    server: "FleetServer"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == f"{API_PREFIX}/summary":
            self._send_json(200, self.server.state.summary())
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
