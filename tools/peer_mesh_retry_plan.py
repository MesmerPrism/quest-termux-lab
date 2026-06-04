#!/usr/bin/env python3
"""Public-safe peer gossip retry/backoff planner.

The retry plan consumes sender-side delivery state and a synthetic retry
policy. It does not send gossip, open sockets, copy files, discover peers, use
ADB, or carry command payloads.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import peer_mesh_delivery
import peer_mesh_gossip


RETRY_POLICY_SCHEMA = "quest-termux-lab.peer-retry-policy.v1"
RETRY_PLAN_SCHEMA = "quest-termux-lab.peer-retry-plan.v1"
DECISIONS = {
    "due_now",
    "waiting_backoff",
    "max_attempts_reached",
    "non_retryable_error",
    "expired",
    "terminal",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def write_json(path_text: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if path_text == "-":
        print(text)
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def format_time(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != RETRY_POLICY_SCHEMA:
        raise ValueError("unsupported retry policy schema")
    if peer_mesh_gossip.contains_forbidden_key(policy):
        raise ValueError("retry policy contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "max_attempts",
        "min_retry_delay_seconds",
        "max_retry_delay_seconds",
        "backoff_multiplier",
        "retryable_errors",
    ]:
        if key not in policy:
            raise ValueError(f"retry policy missing {key}")
    if not isinstance(policy["max_attempts"], int) or policy["max_attempts"] <= 0:
        raise ValueError("max_attempts must be a positive integer")
    for key in ["min_retry_delay_seconds", "max_retry_delay_seconds"]:
        if not isinstance(policy[key], int) or policy[key] < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    if policy["max_retry_delay_seconds"] < policy["min_retry_delay_seconds"]:
        raise ValueError("max_retry_delay_seconds must be >= min_retry_delay_seconds")
    multiplier = policy["backoff_multiplier"]
    if not isinstance(multiplier, (int, float)) or multiplier < 1:
        raise ValueError("backoff_multiplier must be >= 1")
    if not isinstance(policy["retryable_errors"], list):
        raise ValueError("retryable_errors must be an array")
    for error in policy["retryable_errors"]:
        if not isinstance(error, str) or not error:
            raise ValueError("retryable_errors entries must be non-empty strings")


def retry_delay_seconds(policy: dict[str, Any], attempt_count: int) -> int:
    if attempt_count <= 0:
        return 0
    minimum = int(policy["min_retry_delay_seconds"])
    maximum = int(policy["max_retry_delay_seconds"])
    multiplier = float(policy["backoff_multiplier"])
    raw = minimum * math.pow(multiplier, max(0, attempt_count - 1))
    return min(maximum, int(round(raw)))


def is_retryable_error(policy: dict[str, Any], last_error: Any) -> bool:
    if last_error is None:
        return True
    if not isinstance(last_error, str):
        return False
    retryable = set(str(item) for item in policy["retryable_errors"])
    return "*" in retryable or last_error in retryable


def retry_entry(
    delivery: dict[str, Any],
    decision: str,
    now: datetime,
    policy: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError("unsupported retry decision")
    next_attempt_at = None
    delay_seconds = 0
    if decision in {"due_now", "waiting_backoff"}:
        if delivery.get("last_attempt_at") is None:
            next_attempt_at = format_time(now)
        else:
            delay_seconds = retry_delay_seconds(policy, int(delivery["attempt_count"]))
            last_attempt = peer_mesh_gossip.parse_time(str(delivery["last_attempt_at"]))
            next_attempt_at = format_time(last_attempt + timedelta(seconds=delay_seconds))
    return {
        "delivery_id": delivery["delivery_id"],
        "target_agent_id": delivery["target_agent_id"],
        "message_id": delivery["message_id"],
        "delivery_state": delivery["state"],
        "attempt_count": delivery["attempt_count"],
        "decision": decision,
        "next_attempt_at": next_attempt_at,
        "backoff_delay_seconds": delay_seconds,
        "expires_at": delivery["expires_at"],
        "last_error": delivery.get("last_error"),
        "reason": reason,
    }


def summarize(retries: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {decision: 0 for decision in DECISIONS}
    for entry in retries:
        counts[str(entry["decision"])] += 1
    return {
        "retry_count": len(retries),
        "due_now_count": counts["due_now"],
        "waiting_backoff_count": counts["waiting_backoff"],
        "max_attempts_reached_count": counts["max_attempts_reached"],
        "non_retryable_error_count": counts["non_retryable_error"],
        "expired_count": counts["expired"],
        "terminal_count": counts["terminal"],
    }


def build_retry_plan(
    delivery_state: dict[str, Any],
    retry_policy: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    peer_mesh_delivery.validate_state(delivery_state)
    validate_policy(retry_policy)
    if retry_policy["fleet_id"] != delivery_state["fleet_id"]:
        raise ValueError("retry policy fleet_id mismatch")
    if retry_policy["source_agent_id"] != delivery_state["source_agent_id"]:
        raise ValueError("retry policy source_agent_id mismatch")

    observed_at = now_text or str(retry_policy["observed_at"])
    now = peer_mesh_gossip.parse_time(observed_at)
    refreshed = peer_mesh_delivery.expire_pending(delivery_state, now_text=observed_at)
    retries: list[dict[str, Any]] = []
    for delivery in refreshed["deliveries"]:
        if delivery["state"] == "expired":
            retries.append(retry_entry(delivery, "expired", now, retry_policy, "delivery expired"))
            continue
        if delivery["state"] in peer_mesh_delivery.TERMINAL_STATES:
            retries.append(retry_entry(delivery, "terminal", now, retry_policy, "delivery already terminal"))
            continue
        if int(delivery["attempt_count"]) >= int(retry_policy["max_attempts"]):
            retries.append(
                retry_entry(delivery, "max_attempts_reached", now, retry_policy, "max attempts reached")
            )
            continue
        if not is_retryable_error(retry_policy, delivery.get("last_error")):
            retries.append(
                retry_entry(delivery, "non_retryable_error", now, retry_policy, "last error is not retryable")
            )
            continue
        if delivery.get("last_attempt_at") is None:
            retries.append(retry_entry(delivery, "due_now", now, retry_policy, "no previous attempt"))
            continue
        delay_seconds = retry_delay_seconds(retry_policy, int(delivery["attempt_count"]))
        last_attempt = peer_mesh_gossip.parse_time(str(delivery["last_attempt_at"]))
        next_attempt = last_attempt + timedelta(seconds=delay_seconds)
        if next_attempt <= now:
            retries.append(retry_entry(delivery, "due_now", now, retry_policy, "retry backoff elapsed"))
        else:
            retries.append(retry_entry(delivery, "waiting_backoff", now, retry_policy, "retry backoff active"))

    return {
        "schema": RETRY_PLAN_SCHEMA,
        "fleet_id": refreshed["fleet_id"],
        "source_agent_id": refreshed["source_agent_id"],
        "observed_at": observed_at,
        "policy": {
            "max_attempts": retry_policy["max_attempts"],
            "min_retry_delay_seconds": retry_policy["min_retry_delay_seconds"],
            "max_retry_delay_seconds": retry_policy["max_retry_delay_seconds"],
            "backoff_multiplier": retry_policy["backoff_multiplier"],
        },
        "retries": retries,
        "summary": summarize(retries),
        "authority_boundary": [
            "Retry plans schedule gossip delivery attempts only.",
            "Retry plans do not open sockets, copy files, discover peers, send gossip, use ADB, or launch apps.",
            "Retry plans do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    delivery_state = load_json(Path(args.delivery_state))
    retry_policy = load_json(Path(args.policy))
    write_json(args.output, build_retry_plan(delivery_state, retry_policy, now_text=args.now or None))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe peer gossip retry/backoff plan.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    parser.add_argument("delivery_state")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
