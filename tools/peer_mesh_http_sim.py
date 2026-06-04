#!/usr/bin/env python3
"""Loopback-only HTTP simulator for peer gossip transport.

This prepares the shape of a future configured peer transport without doing
live discovery or device work. The server accepts peer gossip envelopes only;
it rejects heartbeats, commands, shell text, ADB targets, and credential-like
fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import peer_mesh_gossip


API_PREFIX = "/api/peer/v1"
HTTP_CONFIG_SCHEMA = "quest-termux-lab.peer-http-node-config.v1"
HTTP_SUMMARY_SCHEMA = "quest-termux-lab.peer-http-summary.v1"
HTTP_RECEIPT_SCHEMA = "quest-termux-lab.peer-http-gossip-receipt.v1"


def response(status: str, **extra: Any) -> dict[str, Any]:
    payload = {"status": status, "observed_at": peer_mesh_gossip.utc_now()}
    payload.update(extra)
    return payload


def stable_digest(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class SeenMessage:
    digest: str
    accepted_at_seconds: float


@dataclass
class PeerHttpState:
    """In-memory peer gossip inbox with optional JSONL audit output."""

    fleet_id: str
    observer_agent_id: str
    log_dir: Path | None = None
    seen_message_ttl_seconds: float = 300.0
    now_func: Callable[[], float] = time.monotonic
    gossip: peer_mesh_gossip.GossipState = field(init=False)
    seen_messages: dict[str, SeenMessage] = field(default_factory=dict)
    accepted_message_count: int = 0
    duplicate_message_count: int = 0
    rejected_message_count: int = 0
    expired_seen_message_count: int = 0

    def __post_init__(self) -> None:
        if self.seen_message_ttl_seconds <= 0:
            raise ValueError("seen_message_ttl_seconds must be positive")
        self.gossip = peer_mesh_gossip.GossipState(
            fleet_id=self.fleet_id,
            observer_agent_id=self.observer_agent_id,
        )
        if self.log_dir is not None:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        if self.log_dir is None:
            return
        path = self.log_dir / name
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def prune_seen_messages(self) -> None:
        now = self.now_func()
        expired = [
            message_id
            for message_id, seen in self.seen_messages.items()
            if now - seen.accepted_at_seconds > self.seen_message_ttl_seconds
        ]
        for message_id in expired:
            del self.seen_messages[message_id]
        self.expired_seen_message_count += len(expired)

    def accept_gossip(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.prune_seen_messages()
        message_id = payload.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            self.rejected_message_count += 1
            self._append_jsonl("rejected-gossip.jsonl", rejection_record(payload, "missing message_id"))
            raise ValueError("missing message_id")
        try:
            peer_mesh_gossip.validate_envelope(payload)
            digest = stable_digest(payload)
            previous = self.seen_messages.get(message_id)
            if previous is not None and previous.digest == digest:
                self.duplicate_message_count += 1
                receipt = self._receipt("duplicate", payload, applied=False, reason="message_id already accepted")
                self._append_jsonl("duplicate-gossip.jsonl", receipt)
                return receipt
            if previous is not None:
                self.rejected_message_count += 1
                self._append_jsonl("rejected-gossip.jsonl", rejection_record(payload, "message_id replay conflict"))
                raise ValueError("message_id replay conflict")
            self.gossip.merge_envelope(payload)
        except ValueError as exc:
            if str(exc) != "message_id replay conflict":
                self.rejected_message_count += 1
                self._append_jsonl("rejected-gossip.jsonl", rejection_record(payload, str(exc)))
            raise
        self.seen_messages[message_id] = SeenMessage(digest=digest, accepted_at_seconds=self.now_func())
        self.accepted_message_count += 1
        self._append_jsonl("accepted-gossip.jsonl", payload)
        return self._receipt("accepted", payload, applied=True)

    def _receipt(self, status: str, payload: dict[str, Any], applied: bool, reason: str | None = None) -> dict[str, Any]:
        receipt = response(
            status,
            schema=HTTP_RECEIPT_SCHEMA,
            fleet_id=self.fleet_id,
            observer_agent_id=self.observer_agent_id,
            message_id=payload.get("message_id"),
            sender_agent_id=payload.get("sender_agent_id"),
            applied=applied,
            reason=reason,
            known_peer_count=self.gossip.summary()["known_peer_count"],
            accepted_message_count=self.accepted_message_count,
            duplicate_message_count=self.duplicate_message_count,
            rejected_message_count=self.rejected_message_count,
            expired_seen_message_count=self.expired_seen_message_count,
            seen_message_ttl_seconds=self.seen_message_ttl_seconds,
        )
        return receipt

    def summary(self) -> dict[str, Any]:
        self.prune_seen_messages()
        peer_summary = self.gossip.summary()
        return {
            "schema": HTTP_SUMMARY_SCHEMA,
            "fleet_id": self.fleet_id,
            "observer_agent_id": self.observer_agent_id,
            "observed_at": peer_summary["observed_at"],
            "transport_scope": "loopback_http_simulator",
            "accepted_message_count": self.accepted_message_count,
            "duplicate_message_count": self.duplicate_message_count,
            "rejected_message_count": self.rejected_message_count,
            "expired_seen_message_count": self.expired_seen_message_count,
            "seen_message_count": len(self.seen_messages),
            "seen_message_ttl_seconds": self.seen_message_ttl_seconds,
            "peer_summary": peer_summary,
        }

    def health(self) -> dict[str, Any]:
        self.prune_seen_messages()
        return response(
            "ok",
            schema="quest-termux-lab.peer-http-health.v1",
            fleet_id=self.fleet_id,
            observer_agent_id=self.observer_agent_id,
            api_prefix=API_PREFIX,
            accepted_message_count=self.accepted_message_count,
            duplicate_message_count=self.duplicate_message_count,
            rejected_message_count=self.rejected_message_count,
            expired_seen_message_count=self.expired_seen_message_count,
            seen_message_count=len(self.seen_messages),
            seen_message_ttl_seconds=self.seen_message_ttl_seconds,
        )


def rejection_record(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "schema": "quest-termux-lab.peer-http-rejected-message.v1",
        "observed_at": peer_mesh_gossip.utc_now(),
        "reason": reason,
        "payload_schema": payload.get("schema"),
        "message_id": payload.get("message_id"),
        "sender_agent_id": payload.get("sender_agent_id"),
    }


class PeerHttpHandler(BaseHTTPRequestHandler):
    server: "PeerHttpServer"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == f"{API_PREFIX}/health":
            self._send_json(200, self.server.state.health())
            return
        if parsed.path == f"{API_PREFIX}/summary":
            self._send_json(200, self.server.state.summary())
            return
        self._send_error(404, "unknown route")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == f"{API_PREFIX}/gossip":
                self._send_json(200, self.server.state.accept_gossip(payload))
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


class PeerHttpServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: PeerHttpState, quiet: bool = False):
        super().__init__(server_address, PeerHttpHandler)
        self.state = state
        self.quiet = quiet


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("config must be a JSON object")
    if payload.get("schema") != HTTP_CONFIG_SCHEMA:
        raise ValueError("unsupported peer HTTP config schema")
    if peer_mesh_gossip.contains_forbidden_key(payload):
        raise ValueError("peer HTTP config contains forbidden keys")
    if payload.get("bind_host") != "127.0.0.1":
        raise ValueError("public simulator config must bind to 127.0.0.1")
    return payload


def run_server(args: argparse.Namespace) -> int:
    if args.config:
        config = load_config(Path(args.config))
        fleet_id = str(config["fleet_id"])
        agent_id = str(config["agent_id"])
        host = str(config["bind_host"])
        port = int(config["bind_port"])
        seen_message_ttl_seconds = float(config.get("seen_message_ttl_seconds", 300.0))
    else:
        fleet_id = args.fleet_id
        agent_id = args.agent_id
        host = args.host
        port = args.port
        seen_message_ttl_seconds = args.seen_message_ttl_seconds
    if host != "127.0.0.1":
        raise SystemExit("peer HTTP simulator binds to 127.0.0.1 only")
    log_dir = Path(args.log_dir) if args.log_dir else None
    state = PeerHttpState(
        fleet_id=fleet_id,
        observer_agent_id=agent_id,
        log_dir=log_dir,
        seen_message_ttl_seconds=seen_message_ttl_seconds,
    )
    server = PeerHttpServer((host, port), state, quiet=args.quiet)
    actual_host, actual_port = server.server_address
    print(f"peer_http_sim_listening http://{actual_host}:{actual_port}{API_PREFIX}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("peer_http_sim_stopped")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a loopback-only peer gossip HTTP simulator.")
    parser.add_argument("--config", default="", help="optional peer HTTP node config JSON")
    parser.add_argument("--fleet-id", default="synthetic-lab-fleet")
    parser.add_argument("--agent-id", default="quest-agent-alpha")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--seen-message-ttl-seconds", type=float, default=300.0)
    parser.add_argument("--log-dir", default="")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    return run_server(args)


if __name__ == "__main__":
    sys.exit(main())
