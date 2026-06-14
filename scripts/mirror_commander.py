#!/usr/bin/env python3
"""Submit typed mirror-command intents to the fleet controller."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


MIRROR_API_PREFIX = "/api/mirror/v1"
MIRROR_INTENT_SCHEMA = "quest-termux-lab.mirror-command-intent.v1"
SAFE_ID_RE = re.compile(r"[^a-z0-9_.-]+")
TERMINAL_STATES = {"completed", "rejected", "failed", "timeout", "skipped"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_time(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


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


def central_url(config: dict[str, Any], path: str) -> str:
    return str(config["central_url"]).rstrip("/") + path


def safe_id(value: str) -> str:
    cleaned = SAFE_ID_RE.sub("-", value.lower()).strip("-.")
    if not cleaned or not cleaned[0].isalnum():
        return f"mirror-{cleaned or 'intent'}"
    return cleaned[:80]


def config_source_agent_id(config: dict[str, Any]) -> str:
    value = config.get("source_agent_id", config.get("agent_id"))
    if not isinstance(value, str) or not value:
        raise ValueError("config must include source_agent_id or agent_id")
    return value


def config_text(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"config must include {key}")
    return value


def build_intent(args: argparse.Namespace, config: dict[str, Any], kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    source_agent_id = config_source_agent_id(config)
    target_agent_id = args.target or config.get("target_agent_id")
    if not isinstance(target_agent_id, str) or not target_agent_id:
        raise ValueError("target agent id is required")
    lease_id = args.lease_id or config.get("lease_id")
    if not isinstance(lease_id, str) or not lease_id:
        raise ValueError("lease id is required")

    now = utc_now()
    ttl_seconds = int(args.ttl_seconds)
    intent_id = args.intent_id or (
        f"{safe_id(source_agent_id)}-{kind.replace('.', '-')}-{uuid.uuid4().hex[:8]}"
    )
    idem = args.idempotency_key or f"{intent_id}-idem"
    return {
        "schema": MIRROR_INTENT_SCHEMA,
        "fleet_id": config_text(config, "fleet_id"),
        "mirror_intent_id": intent_id,
        "lease_id": lease_id,
        "source_agent_id": source_agent_id,
        "target_agent_id": target_agent_id,
        "issued_at": format_time(now),
        "expires_at": format_time(now + timedelta(seconds=ttl_seconds)),
        "idempotency_key": idem,
        "kind": kind,
        "requires_local_adb_shell": bool(args.requires_local_adb_shell),
        "timeout_ms": int(args.timeout_ms),
        "max_stdout_bytes": int(args.max_stdout_bytes),
        "max_stderr_bytes": int(args.max_stderr_bytes),
        "payload": payload,
        "sensitivity": args.sensitivity,
        "reason": args.reason,
        "synthetic": bool(config.get("synthetic", False)),
    }


def parse_extras(values: list[str]) -> dict[str, str]:
    extras: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"extra must be key=value: {value}")
        key, item = value.split("=", 1)
        if not key:
            raise ValueError("extra key must not be empty")
        extras[key] = item
    return extras


def submit_and_maybe_poll(args: argparse.Namespace, config: dict[str, Any], intent: dict[str, Any]) -> int:
    submitted = post_json(central_url(config, f"{MIRROR_API_PREFIX}/intents"), intent)
    if args.no_poll:
        print(json.dumps(submitted, indent=2, sort_keys=True))
        return 0

    deadline = time.monotonic() + float(args.poll_timeout_seconds)
    status = submitted
    while time.monotonic() <= deadline:
        status = get_json(
            central_url(config, f"{MIRROR_API_PREFIX}/intents/{intent['mirror_intent_id']}"),
            timeout_seconds=float(args.http_timeout_seconds),
        )
        state = status.get("state")
        if state in TERMINAL_STATES:
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0 if state == "completed" else 2
        time.sleep(float(args.poll_interval_seconds))
    print(json.dumps(status, indent=2, sort_keys=True))
    return 3


def command_create_lease(args: argparse.Namespace, config: dict[str, Any]) -> int:
    lease = load_json(Path(args.lease_file))
    result = post_json(central_url(config, f"{MIRROR_API_PREFIX}/leases"), lease)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_revoke_lease(args: argparse.Namespace, config: dict[str, Any]) -> int:
    lease_id = args.lease_id or config.get("lease_id")
    if not isinstance(lease_id, str) or not lease_id:
        raise ValueError("lease id is required")
    result = post_json(
        central_url(config, f"{MIRROR_API_PREFIX}/leases/{lease_id}/revoke"),
        {"reason": args.reason},
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_status(args: argparse.Namespace, config: dict[str, Any]) -> int:
    intent = build_intent(args, config, "agent.status", {})
    return submit_and_maybe_poll(args, config, intent)


def command_capabilities(args: argparse.Namespace, config: dict[str, Any]) -> int:
    intent = build_intent(args, config, "agent.capabilities", {})
    return submit_and_maybe_poll(args, config, intent)


def command_lease_check(args: argparse.Namespace, config: dict[str, Any]) -> int:
    intent = build_intent(args, config, "adb.lease_check", {})
    return submit_and_maybe_poll(args, config, intent)


def command_launch_panel(args: argparse.Namespace, config: dict[str, Any]) -> int:
    intent = build_intent(args, config, "app.launch_allowlisted", {"component": args.component})
    return submit_and_maybe_poll(args, config, intent)


def command_uiautomator(args: argparse.Namespace, config: dict[str, Any]) -> int:
    payload = {"scenario": args.scenario, "extras": parse_extras(args.extra)}
    intent = build_intent(args, config, "uiautomator.run_allowlisted_scenario", payload)
    return submit_and_maybe_poll(args, config, intent)


def add_intent_options(parser: argparse.ArgumentParser, *, requires_adb: bool, reason: str) -> None:
    parser.add_argument("--target", default="")
    parser.add_argument("--lease-id", default="")
    parser.add_argument("--intent-id", default="")
    parser.add_argument("--idempotency-key", default="")
    parser.add_argument("--ttl-seconds", type=int, default=30)
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--max-stdout-bytes", type=int, default=4096)
    parser.add_argument("--max-stderr-bytes", type=int, default=4096)
    parser.add_argument("--sensitivity", default="local_only", choices=["public_safe", "local_only", "private_evidence"])
    parser.add_argument("--reason", default=reason)
    parser.add_argument("--requires-local-adb-shell", action="store_true", default=requires_adb)
    parser.add_argument("--no-poll", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--poll-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--http-timeout-seconds", type=float, default=10.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit typed mirror commands to a fleet controller.")
    parser.add_argument("--config", required=True, help="JSON config with fleet_id, source_agent_id, central_url, and lease_id")
    sub = parser.add_subparsers(dest="command", required=True)

    create_lease = sub.add_parser("create-lease")
    create_lease.add_argument("--lease-file", required=True)
    create_lease.set_defaults(func=command_create_lease)

    revoke = sub.add_parser("revoke-lease")
    revoke.add_argument("--lease-id", default="")
    revoke.add_argument("--reason", default="Operator revoked mirror lease.")
    revoke.set_defaults(func=command_revoke_lease)

    status = sub.add_parser("status")
    add_intent_options(status, requires_adb=False, reason="Mirror source status check to target headset.")
    status.set_defaults(func=command_status)

    capabilities = sub.add_parser("capabilities")
    add_intent_options(capabilities, requires_adb=False, reason="Mirror source capability check to target headset.")
    capabilities.set_defaults(func=command_capabilities)

    lease_check = sub.add_parser("lease-check")
    add_intent_options(lease_check, requires_adb=False, reason="Check target local ADB lease state.")
    lease_check.set_defaults(func=command_lease_check)

    launch = sub.add_parser("launch-panel")
    add_intent_options(launch, requires_adb=True, reason="Mirror source launch action to target headset.")
    launch.add_argument("--component", required=True)
    launch.set_defaults(func=command_launch_panel)

    uiautomator = sub.add_parser("run-uiautomator")
    add_intent_options(uiautomator, requires_adb=True, reason="Mirror source UIAutomator scenario to target headset.")
    uiautomator.add_argument("--scenario", required=True)
    uiautomator.add_argument("--extra", action="append", default=[])
    uiautomator.set_defaults(func=command_uiautomator)

    args = parser.parse_args(argv)
    config = load_json(Path(args.config))
    return int(args.func(args, config))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"mirror_commander_error: {exc}", file=sys.stderr)
        sys.exit(1)
