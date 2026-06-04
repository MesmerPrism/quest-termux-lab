#!/usr/bin/env python3
"""Public-safe peer gossip send dry-run simulator.

The dry run consumes delivery state, route config, and synthetic outcomes. It
does not open sockets, copy files, discover peers, send gossip, use ADB, or
carry command payloads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_delivery
import peer_mesh_dispatch_plan
import peer_mesh_gossip


OUTCOMES_SCHEMA = "quest-termux-lab.peer-send-dry-run-outcomes.v1"
REPORT_SCHEMA = "quest-termux-lab.peer-send-dry-run-report.v1"
OUTCOME_RESULTS = {"accepted", "duplicate", "rejected", "no_response"}


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


def validate_outcomes(payload: dict[str, Any]) -> None:
    if payload.get("schema") != OUTCOMES_SCHEMA:
        raise ValueError("unsupported dry-run outcomes schema")
    if peer_mesh_gossip.contains_forbidden_key(payload):
        raise ValueError("dry-run outcomes contain command-like or credential-like fields")
    for key in ["fleet_id", "source_agent_id", "observed_at", "outcomes"]:
        if key not in payload:
            raise ValueError(f"dry-run outcomes missing {key}")
    if not isinstance(payload["outcomes"], list):
        raise ValueError("outcomes must be an array")
    seen: set[tuple[str, str]] = set()
    for outcome in payload["outcomes"]:
        if not isinstance(outcome, dict):
            raise ValueError("outcome entry must be an object")
        for key in ["target_agent_id", "message_id", "result"]:
            if not isinstance(outcome.get(key), str) or not outcome[key]:
                raise ValueError(f"outcome missing {key}")
        if outcome["result"] not in OUTCOME_RESULTS:
            raise ValueError("unsupported outcome result")
        key = (outcome["target_agent_id"], outcome["message_id"])
        if key in seen:
            raise ValueError("duplicate outcome target/message pair")
        seen.add(key)
        reason = outcome.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise ValueError("outcome reason must be a string or null")


def outcomes_by_target(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    validate_outcomes(payload)
    return {
        (str(outcome["target_agent_id"]), str(outcome["message_id"])): dict(outcome)
        for outcome in payload["outcomes"]
    }


def synthetic_receipt(
    delivery_state: dict[str, Any],
    dispatch: dict[str, Any],
    outcome: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    result = str(outcome["result"])
    return {
        "schema": peer_mesh_delivery.HTTP_RECEIPT_SCHEMA,
        "status": result,
        "observed_at": observed_at,
        "fleet_id": delivery_state["fleet_id"],
        "observer_agent_id": dispatch["target_agent_id"],
        "message_id": dispatch["message_id"],
        "sender_agent_id": delivery_state["source_agent_id"],
        "applied": result == "accepted",
        "reason": outcome.get("reason"),
        "known_peer_count": 0,
        "accepted_message_count": 0,
        "duplicate_message_count": 0,
        "rejected_message_count": 0,
        "expired_seen_message_count": 0,
        "seen_message_ttl_seconds": 300,
    }


def record_no_response(
    delivery_state: dict[str, Any],
    dispatch: dict[str, Any],
    reason: str,
    observed_at: str,
) -> dict[str, Any]:
    updated = peer_mesh_delivery.refresh_summary(delivery_state, observed_at=observed_at)
    delivery = peer_mesh_delivery.find_delivery(
        updated,
        target_agent_id=str(dispatch["target_agent_id"]),
        message_id=str(dispatch["message_id"]),
    )
    delivery["attempt_count"] += 1
    delivery["last_attempt_at"] = observed_at
    delivery["last_receipt_status"] = None
    delivery["last_error"] = reason
    return peer_mesh_delivery.refresh_summary(updated, observed_at=observed_at)


def apply_ready_outcome(
    delivery_state: dict[str, Any],
    dispatch: dict[str, Any],
    outcome: dict[str, Any] | None,
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    chosen = outcome or {
        "target_agent_id": dispatch["target_agent_id"],
        "message_id": dispatch["message_id"],
        "result": "no_response",
        "reason": "no synthetic outcome configured",
    }
    result = str(chosen["result"])
    reason = chosen.get("reason") if isinstance(chosen.get("reason"), str) else None
    if result in {"accepted", "duplicate"}:
        receipt = synthetic_receipt(delivery_state, dispatch, chosen, observed_at)
        updated = peer_mesh_delivery.apply_receipt(
            delivery_state,
            receipt,
            target_agent_id=str(dispatch["target_agent_id"]),
        )
    elif result == "rejected":
        updated = peer_mesh_delivery.apply_error(
            delivery_state,
            target_agent_id=str(dispatch["target_agent_id"]),
            message_id=str(dispatch["message_id"]),
            reason=reason or "synthetic rejection",
            observed_at=observed_at,
        )
    elif result == "no_response":
        updated = record_no_response(
            delivery_state,
            dispatch,
            reason=reason or "synthetic no response",
            observed_at=observed_at,
        )
    else:
        raise ValueError("unsupported outcome result")
    action = {
        "delivery_id": dispatch["delivery_id"],
        "target_agent_id": dispatch["target_agent_id"],
        "message_id": dispatch["message_id"],
        "dispatch_decision": dispatch["decision"],
        "simulated_outcome": result,
        "transport_mode": dispatch["transport_mode"],
        "method": dispatch["method"],
        "delivery_state_after": peer_mesh_delivery.find_delivery(
            updated,
            target_agent_id=str(dispatch["target_agent_id"]),
            message_id=str(dispatch["message_id"]),
        )["state"],
        "reason": reason,
    }
    return updated, action


def summarize_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "accepted": 0,
        "duplicate": 0,
        "rejected": 0,
        "no_response": 0,
        "not_sent": 0,
    }
    for action in actions:
        outcome = str(action["simulated_outcome"])
        if outcome in counts:
            counts[outcome] += 1
    return {
        "action_count": len(actions),
        "accepted_count": counts["accepted"],
        "duplicate_count": counts["duplicate"],
        "rejected_count": counts["rejected"],
        "no_response_count": counts["no_response"],
        "not_sent_count": counts["not_sent"],
    }


def run_dry_run(
    delivery_state: dict[str, Any],
    route_config: dict[str, Any],
    outcomes: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_outcomes(outcomes)
    if outcomes["fleet_id"] != delivery_state["fleet_id"]:
        raise ValueError("outcomes fleet_id mismatch")
    if outcomes["source_agent_id"] != delivery_state["source_agent_id"]:
        raise ValueError("outcomes source_agent_id mismatch")

    observed_at = now_text or str(outcomes["observed_at"])
    plan = peer_mesh_dispatch_plan.build_dispatch_plan(delivery_state, route_config, now_text=observed_at)
    updated_state = peer_mesh_delivery.expire_pending(delivery_state, now_text=observed_at)
    by_target = outcomes_by_target(outcomes)
    actions: list[dict[str, Any]] = []
    for dispatch in plan["dispatches"]:
        if dispatch["decision"] != "ready":
            actions.append(
                {
                    "delivery_id": dispatch["delivery_id"],
                    "target_agent_id": dispatch["target_agent_id"],
                    "message_id": dispatch["message_id"],
                    "dispatch_decision": dispatch["decision"],
                    "simulated_outcome": "not_sent",
                    "transport_mode": dispatch["transport_mode"],
                    "method": dispatch["method"],
                    "delivery_state_after": dispatch["delivery_state"],
                    "reason": dispatch["reason"],
                }
            )
            continue
        key = (str(dispatch["target_agent_id"]), str(dispatch["message_id"]))
        updated_state, action = apply_ready_outcome(
            updated_state,
            dispatch,
            outcome=by_target.get(key),
            observed_at=observed_at,
        )
        actions.append(action)

    return {
        "schema": REPORT_SCHEMA,
        "fleet_id": updated_state["fleet_id"],
        "source_agent_id": updated_state["source_agent_id"],
        "observed_at": observed_at,
        "dispatch_summary": plan["summary"],
        "actions": actions,
        "summary": summarize_actions(actions),
        "updated_delivery_state": updated_state,
        "authority_boundary": [
            "Send dry runs simulate configured-peer gossip delivery only.",
            "Send dry runs do not open sockets, copy files, discover peers, send gossip, use ADB, or launch apps.",
            "Send dry runs do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    delivery_state = load_json(Path(args.delivery_state))
    route_config = load_json(Path(args.route_config))
    outcomes = load_json(Path(args.outcomes))
    report = run_dry_run(delivery_state, route_config, outcomes, now_text=args.now or None)
    if args.state_output:
        write_json(args.state_output, report["updated_delivery_state"])
    write_json(args.output, report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a no-send peer gossip sender dry run.")
    parser.add_argument("--route-config", required=True)
    parser.add_argument("--outcomes", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--state-output", default="")
    parser.add_argument("--output", default="-")
    parser.add_argument("delivery_state")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
