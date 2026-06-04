#!/usr/bin/env python3
"""Public-safe peer gossip delivery-state simulator.

The delivery state models sender-side progress for future configured peers.
It does not open sockets, discover peers, carry commands, use ADB, or send
gossip by itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_gossip


DELIVERY_STATE_SCHEMA = "quest-termux-lab.peer-delivery-state.v1"
HTTP_RECEIPT_SCHEMA = "quest-termux-lab.peer-http-gossip-receipt.v1"
DELIVERY_STATES = {"pending", "accepted", "duplicate", "rejected", "expired"}
TERMINAL_STATES = {"accepted", "duplicate", "rejected", "expired"}


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


def validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != DELIVERY_STATE_SCHEMA:
        raise ValueError("unsupported delivery state schema")
    for key in ["fleet_id", "source_agent_id", "observed_at", "deliveries"]:
        if key not in state:
            raise ValueError(f"delivery state missing {key}")
    if not isinstance(state["deliveries"], list):
        raise ValueError("deliveries must be an array")
    seen_delivery_ids: set[str] = set()
    for delivery in state["deliveries"]:
        if not isinstance(delivery, dict):
            raise ValueError("delivery entry must be an object")
        for key in ["delivery_id", "target_agent_id", "message_id", "state", "created_at", "expires_at"]:
            if not isinstance(delivery.get(key), str) or not delivery[key]:
                raise ValueError(f"delivery missing {key}")
        if delivery["state"] not in DELIVERY_STATES:
            raise ValueError("unsupported delivery state")
        if delivery["delivery_id"] in seen_delivery_ids:
            raise ValueError("duplicate delivery_id")
        seen_delivery_ids.add(delivery["delivery_id"])
        if not isinstance(delivery.get("attempt_count"), int) or delivery["attempt_count"] < 0:
            raise ValueError("delivery attempt_count must be a non-negative integer")


def validate_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != HTTP_RECEIPT_SCHEMA:
        raise ValueError("unsupported receipt schema")
    if receipt.get("status") not in {"accepted", "duplicate"}:
        raise ValueError("unsupported receipt status")
    for key in ["fleet_id", "observer_agent_id", "message_id", "observed_at"]:
        if not isinstance(receipt.get(key), str) or not receipt[key]:
            raise ValueError(f"receipt missing {key}")
    if not isinstance(receipt.get("applied"), bool):
        raise ValueError("receipt missing applied")


def summarize(state: dict[str, Any]) -> dict[str, Any]:
    counts = {name: 0 for name in DELIVERY_STATES}
    for delivery in state["deliveries"]:
        counts[str(delivery["state"])] += 1
    return {
        "delivery_count": len(state["deliveries"]),
        "pending_count": counts["pending"],
        "accepted_count": counts["accepted"],
        "duplicate_count": counts["duplicate"],
        "rejected_count": counts["rejected"],
        "expired_count": counts["expired"],
        "terminal_count": sum(counts[name] for name in TERMINAL_STATES),
    }


def refresh_summary(state: dict[str, Any], observed_at: str | None = None) -> dict[str, Any]:
    validate_state(state)
    updated = dict(state)
    updated["deliveries"] = [dict(delivery) for delivery in state["deliveries"]]
    updated["observed_at"] = observed_at or peer_mesh_gossip.utc_now()
    updated["summary"] = summarize(updated)
    return updated


def find_delivery(state: dict[str, Any], target_agent_id: str, message_id: str) -> dict[str, Any]:
    for delivery in state["deliveries"]:
        if delivery["target_agent_id"] == target_agent_id and delivery["message_id"] == message_id:
            return delivery
    raise ValueError("delivery not found for target and message_id")


def apply_receipt(state: dict[str, Any], receipt: dict[str, Any], target_agent_id: str | None = None) -> dict[str, Any]:
    validate_state(state)
    validate_receipt(receipt)
    if receipt["fleet_id"] != state["fleet_id"]:
        raise ValueError("receipt fleet_id mismatch")
    target = target_agent_id or str(receipt["observer_agent_id"])
    updated = refresh_summary(state, observed_at=str(receipt["observed_at"]))
    delivery = find_delivery(updated, target, str(receipt["message_id"]))
    delivery["state"] = str(receipt["status"])
    delivery["attempt_count"] += 1
    delivery["last_attempt_at"] = receipt["observed_at"]
    delivery["last_receipt_status"] = receipt["status"]
    delivery["last_error"] = receipt.get("reason") if isinstance(receipt.get("reason"), str) else None
    return refresh_summary(updated, observed_at=str(receipt["observed_at"]))


def apply_error(
    state: dict[str, Any],
    target_agent_id: str,
    message_id: str,
    reason: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    validate_state(state)
    when = observed_at or peer_mesh_gossip.utc_now()
    updated = refresh_summary(state, observed_at=when)
    delivery = find_delivery(updated, target_agent_id, message_id)
    delivery["state"] = "rejected"
    delivery["attempt_count"] += 1
    delivery["last_attempt_at"] = when
    delivery["last_receipt_status"] = None
    delivery["last_error"] = reason
    return refresh_summary(updated, observed_at=when)


def expire_pending(state: dict[str, Any], now_text: str | None = None) -> dict[str, Any]:
    validate_state(state)
    now = peer_mesh_gossip.parse_time(now_text or peer_mesh_gossip.utc_now())
    updated = refresh_summary(state, observed_at=now.isoformat().replace("+00:00", "Z"))
    for delivery in updated["deliveries"]:
        if delivery["state"] != "pending":
            continue
        expires_at = peer_mesh_gossip.parse_time(str(delivery["expires_at"]))
        if expires_at <= now:
            delivery["state"] = "expired"
            delivery["last_attempt_at"] = delivery.get("last_attempt_at")
            delivery["last_receipt_status"] = None
            delivery["last_error"] = "delivery expired before receipt"
    return refresh_summary(updated, observed_at=now.isoformat().replace("+00:00", "Z"))


def run_apply_receipt(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    receipt = load_json(Path(args.receipt))
    write_json(args.output, apply_receipt(state, receipt, target_agent_id=args.target_agent_id or None))
    return 0


def run_apply_error(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    write_json(
        args.output,
        apply_error(
            state,
            target_agent_id=args.target_agent_id,
            message_id=args.message_id,
            reason=args.reason,
            observed_at=args.observed_at or None,
        ),
    )
    return 0


def run_expire(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    write_json(args.output, expire_pending(state, now_text=args.now or None))
    return 0


def run_summary(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    write_json(args.output, refresh_summary(state))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update peer gossip delivery-state fixtures.")
    sub = parser.add_subparsers(dest="command", required=True)

    apply_receipt_parser = sub.add_parser("apply-receipt")
    apply_receipt_parser.add_argument("--receipt", required=True)
    apply_receipt_parser.add_argument("--target-agent-id", default="")
    apply_receipt_parser.add_argument("--output", default="-")
    apply_receipt_parser.add_argument("state")
    apply_receipt_parser.set_defaults(func=run_apply_receipt)

    apply_error_parser = sub.add_parser("apply-error")
    apply_error_parser.add_argument("--target-agent-id", required=True)
    apply_error_parser.add_argument("--message-id", required=True)
    apply_error_parser.add_argument("--reason", required=True)
    apply_error_parser.add_argument("--observed-at", default="")
    apply_error_parser.add_argument("--output", default="-")
    apply_error_parser.add_argument("state")
    apply_error_parser.set_defaults(func=run_apply_error)

    expire_parser = sub.add_parser("expire")
    expire_parser.add_argument("--now", default="")
    expire_parser.add_argument("--output", default="-")
    expire_parser.add_argument("state")
    expire_parser.set_defaults(func=run_expire)

    summary_parser = sub.add_parser("summary")
    summary_parser.add_argument("--output", default="-")
    summary_parser.add_argument("state")
    summary_parser.set_defaults(func=run_summary)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
