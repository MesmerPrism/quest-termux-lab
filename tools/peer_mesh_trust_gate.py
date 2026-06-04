#!/usr/bin/env python3
"""Public-safe configured-peer trust gate for future peer experiments.

The trust report evaluates configured peers, simulator route modes, bundle
status, and synthetic gossip samples. It does not approve live work, open
sockets, copy files, discover peers, use ADB, send gossip, launch apps, or
carry commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_dispatch_plan
import peer_mesh_gossip
import peer_mesh_lab_bundle
import peer_mesh_live_lab_readiness


TRUST_POLICY_SCHEMA = "quest-termux-lab.peer-trust-policy.v1"
TRUST_REPORT_SCHEMA = "quest-termux-lab.peer-trust-report.v1"
TRUST_STATUSES = {"trusted", "manual_review", "untrusted"}
CHECK_STATUSES = {"passed", "failed", "manual_review"}


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


def validate_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        result.append(item)
    if len(set(result)) != len(result):
        raise ValueError(f"{label} entries must be unique")
    return result


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != TRUST_POLICY_SCHEMA:
        raise ValueError("unsupported trust policy schema")
    if peer_mesh_gossip.contains_forbidden_key(policy):
        raise ValueError("trust policy contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "policy_id",
        "experiment_scope",
        "allowed_agent_ids",
        "allowed_transport_modes",
        "required_message_schema",
        "max_hop_ttl",
        "min_sample_envelopes",
        "require_configured_peers_only",
        "require_trusted_bundle_status",
        "operator_review_required",
    ]:
        if key not in policy:
            raise ValueError(f"trust policy missing {key}")
    for key in ["fleet_id", "source_agent_id", "observed_at", "policy_id"]:
        if not isinstance(policy[key], str) or not policy[key]:
            raise ValueError(f"trust policy missing {key}")
    if policy["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    allowed_agents = validate_string_list(policy["allowed_agent_ids"], "allowed_agent_ids")
    if policy["source_agent_id"] not in allowed_agents:
        raise ValueError("source_agent_id must be present in allowed_agent_ids")
    allowed_modes = validate_string_list(policy["allowed_transport_modes"], "allowed_transport_modes")
    for mode in allowed_modes:
        if mode not in peer_mesh_dispatch_plan.TRANSPORT_MODES:
            raise ValueError("unsupported allowed transport mode")
    if policy["required_message_schema"] != peer_mesh_gossip.GOSSIP_SCHEMA:
        raise ValueError("required_message_schema must be peer gossip")
    for key in ["max_hop_ttl", "min_sample_envelopes"]:
        if not isinstance(policy[key], int) or policy[key] < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    if policy["max_hop_ttl"] < 1:
        raise ValueError("max_hop_ttl must be at least 1")
    for key in ["require_configured_peers_only", "require_trusted_bundle_status", "operator_review_required"]:
        if not isinstance(policy[key], bool):
            raise ValueError(f"{key} must be boolean")


def validate_bundle_report(report: dict[str, Any]) -> None:
    if report.get("schema") != peer_mesh_lab_bundle.LAB_BUNDLE_REPORT_SCHEMA:
        raise ValueError("unsupported lab bundle report schema")
    if peer_mesh_gossip.contains_forbidden_key(report):
        raise ValueError("lab bundle report contains command-like or credential-like fields")
    for key in [
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_id",
        "experiment_scope",
        "overall_status",
        "summary",
    ]:
        if key not in report:
            raise ValueError(f"lab bundle report missing {key}")
    if report["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported lab bundle experiment_scope")
    if report["overall_status"] not in peer_mesh_lab_bundle.BUNDLE_STATUSES:
        raise ValueError("unsupported lab bundle status")
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise ValueError("lab bundle summary must be an object")
    for key in ["configured_route_count", "ready_route_count", "not_ready_route_count"]:
        if not isinstance(summary.get(key), int) or summary[key] < 0:
            raise ValueError(f"lab bundle summary missing non-negative {key}")


def check_entry(check_id: str, status: str, expected: str, observed: str, reason: str) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError("unsupported check status")
    return {
        "check_id": check_id,
        "status": status,
        "expected": expected,
        "observed": observed,
        "reason": reason,
    }


def passed(check_id: str, expected: str, observed: str, reason: str) -> dict[str, Any]:
    return check_entry(check_id, "passed", expected, observed, reason)


def failed(check_id: str, expected: str, observed: str, reason: str) -> dict[str, Any]:
    return check_entry(check_id, "failed", expected, observed, reason)


def manual(check_id: str, expected: str, observed: str, reason: str) -> dict[str, Any]:
    return check_entry(check_id, "manual_review", expected, observed, reason)


def route_reviews(route_config: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_agents = set(policy["allowed_agent_ids"])
    allowed_modes = set(policy["allowed_transport_modes"])
    reviews = []
    routes = route_config.get("routes", [])
    if not isinstance(routes, list):
        return reviews
    for route in routes:
        if not isinstance(route, dict):
            continue
        target = str(route.get("target_agent_id") or "(missing)")
        mode = str(route.get("transport_mode") or "(missing)")
        reasons = []
        status = "trusted"
        if target not in allowed_agents:
            status = "untrusted"
            reasons.append(f"target {target} is not in allowed_agent_ids")
        if mode not in allowed_modes:
            status = "untrusted"
            reasons.append(f"transport mode {mode} is not allowed")
        if not reasons:
            reasons.append("configured route satisfies trust policy")
        reviews.append(
            {
                "target_agent_id": target,
                "transport_mode": mode,
                "trust_status": status,
                "reason": "; ".join(reasons),
            }
        )
    return reviews


def envelope_participants(envelope: dict[str, Any]) -> set[str]:
    participants = {str(envelope.get("sender_agent_id", ""))}
    observations = envelope.get("observations", [])
    if isinstance(observations, list):
        for observation in observations:
            if isinstance(observation, dict):
                participants.add(str(observation.get("agent_id", "")))
                participants.add(str(observation.get("heard_from_agent_id", "")))
    participants.discard("")
    return participants


def envelope_reviews(envelopes: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_agents = set(policy["allowed_agent_ids"])
    max_hop_ttl = int(policy["max_hop_ttl"])
    reviews = []
    for envelope in envelopes:
        message_id = str(envelope.get("message_id", ""))
        sender = str(envelope.get("sender_agent_id", ""))
        try:
            peer_mesh_gossip.validate_envelope(envelope)
            hop_ttl = int(envelope["hop_ttl"])
            participants = envelope_participants(envelope)
            unknown = sorted(participants - allowed_agents)
            reasons = []
            status = "trusted"
            if hop_ttl > max_hop_ttl:
                status = "untrusted"
                reasons.append(f"hop_ttl {hop_ttl} exceeds max {max_hop_ttl}")
            if unknown:
                status = "untrusted"
                reasons.append("participants outside allowed_agent_ids: " + ", ".join(unknown))
            if not reasons:
                reasons.append("sample envelope satisfies trust policy")
        except ValueError as error:
            hop_ttl = envelope.get("hop_ttl")
            status = "untrusted"
            reasons = [str(error)]
        reviews.append(
            {
                "message_id": message_id,
                "sender_agent_id": sender,
                "hop_ttl": hop_ttl if isinstance(hop_ttl, int) else None,
                "trust_status": status,
                "reason": "; ".join(reasons),
            }
        )
    return reviews


def summarize(checks: list[dict[str, Any]], peers: list[dict[str, Any]], envelopes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
        "failed_check_count": sum(1 for check in checks if check["status"] == "failed"),
        "manual_review_check_count": sum(1 for check in checks if check["status"] == "manual_review"),
        "configured_peer_count": len(peers),
        "trusted_peer_count": sum(1 for peer in peers if peer["trust_status"] == "trusted"),
        "untrusted_peer_count": sum(1 for peer in peers if peer["trust_status"] == "untrusted"),
        "sample_envelope_count": len(envelopes),
        "trusted_sample_envelope_count": sum(1 for envelope in envelopes if envelope["trust_status"] == "trusted"),
        "untrusted_sample_envelope_count": sum(1 for envelope in envelopes if envelope["trust_status"] == "untrusted"),
    }


def overall_status(checks: list[dict[str, Any]], peers: list[dict[str, Any]], envelopes: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "untrusted"
    if any(peer["trust_status"] == "untrusted" for peer in peers):
        return "untrusted"
    if any(envelope["trust_status"] == "untrusted" for envelope in envelopes):
        return "untrusted"
    if any(check["status"] == "manual_review" for check in checks):
        return "manual_review"
    return "trusted"


def build_trust_report(
    policy: dict[str, Any],
    route_config: dict[str, Any],
    lab_bundle_report: dict[str, Any],
    gossip_envelopes: list[dict[str, Any]],
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_policy(policy)

    checks: list[dict[str, Any]] = []
    try:
        peer_mesh_dispatch_plan.validate_route_config(route_config)
        if route_config["fleet_id"] != policy["fleet_id"]:
            raise ValueError("fleet_id mismatch")
        if route_config["source_agent_id"] != policy["source_agent_id"]:
            raise ValueError("source_agent_id mismatch")
        checks.append(passed("route_config_valid", "valid peer-route-config.v1", "valid", "route config matches policy identity"))
    except ValueError as error:
        checks.append(failed("route_config_valid", "valid peer-route-config.v1", "invalid", str(error)))

    try:
        validate_bundle_report(lab_bundle_report)
        if lab_bundle_report["fleet_id"] != policy["fleet_id"]:
            raise ValueError("fleet_id mismatch")
        if lab_bundle_report["source_agent_id"] != policy["source_agent_id"]:
            raise ValueError("source_agent_id mismatch")
        if lab_bundle_report["experiment_scope"] != policy["experiment_scope"]:
            raise ValueError("experiment_scope mismatch")
        checks.append(passed("lab_bundle_valid", "valid peer-lab-bundle-report.v1", "valid", "lab bundle matches policy identity"))
    except ValueError as error:
        checks.append(failed("lab_bundle_valid", "valid peer-lab-bundle-report.v1", "invalid", str(error)))

    bundle_status = str(lab_bundle_report.get("overall_status", "invalid"))
    if policy["require_trusted_bundle_status"]:
        if bundle_status == "synthetic_ready":
            checks.append(passed("lab_bundle_status", "synthetic_ready", bundle_status, "bundle preflight is synthetically ready"))
        elif bundle_status == "manual_review":
            checks.append(manual("lab_bundle_status", "synthetic_ready", bundle_status, "bundle preflight still needs manual review"))
        else:
            checks.append(failed("lab_bundle_status", "synthetic_ready", bundle_status, "bundle preflight is blocked or invalid"))

    schemas = route_config.get("allowed_message_schemas", [])
    expected_schema = policy["required_message_schema"]
    if schemas == [expected_schema]:
        checks.append(passed("message_schema", expected_schema, expected_schema, "route config allows gossip schema only"))
    else:
        if isinstance(schemas, list) and schemas:
            observed = ", ".join(str(schema) for schema in schemas)
        elif isinstance(schemas, list):
            observed = "none"
        else:
            observed = "invalid"
        checks.append(failed("message_schema", expected_schema, observed, "route config must allow only peer gossip envelopes"))

    peers = route_reviews(route_config, policy)
    if policy["require_configured_peers_only"] and all(peer["trust_status"] == "trusted" for peer in peers):
        checks.append(passed("configured_peers_allowed", "all configured targets in allowed_agent_ids", str(len(peers)), "configured peers are explicitly allowed"))
    elif policy["require_configured_peers_only"]:
        checks.append(failed("configured_peers_allowed", "all configured targets in allowed_agent_ids", str(len(peers)), "one or more configured peers are not allowed"))

    if all(peer["trust_status"] == "trusted" for peer in peers):
        checks.append(passed("transport_modes_allowed", "all configured transports allowed", str(len(peers)), "configured transport modes are allowed"))
    else:
        checks.append(failed("transport_modes_allowed", "all configured transports allowed", str(len(peers)), "one or more configured transport modes are not allowed"))

    envelope_count = len(gossip_envelopes)
    if envelope_count >= int(policy["min_sample_envelopes"]):
        checks.append(passed("sample_envelope_count", f">= {policy['min_sample_envelopes']} samples", str(envelope_count), "enough synthetic gossip samples were provided"))
    else:
        checks.append(failed("sample_envelope_count", f">= {policy['min_sample_envelopes']} samples", str(envelope_count), "not enough synthetic gossip samples were provided"))

    envelopes = envelope_reviews(gossip_envelopes, policy)
    if all(envelope["trust_status"] == "trusted" for envelope in envelopes):
        checks.append(passed("sample_envelopes_trusted", "sample envelopes within trust policy", str(len(envelopes)), "sample envelopes satisfy agent and TTL policy"))
    else:
        checks.append(failed("sample_envelopes_trusted", "sample envelopes within trust policy", str(len(envelopes)), "one or more sample envelopes violate trust policy"))

    if policy["operator_review_required"]:
        checks.append(
            manual(
                "operator_review",
                "private operator review before live LAN peer experiment",
                "not represented in public synthetic evidence",
                "this public report cannot grant live-device or LAN approval",
            )
        )

    observed_at = now_text or str(policy["observed_at"])
    status = overall_status(checks, peers, envelopes)
    return {
        "schema": TRUST_REPORT_SCHEMA,
        "fleet_id": policy["fleet_id"],
        "source_agent_id": policy["source_agent_id"],
        "observed_at": observed_at,
        "policy_id": policy["policy_id"],
        "experiment_scope": policy["experiment_scope"],
        "overall_status": status,
        "checks": checks,
        "configured_peers": peers,
        "sample_envelopes": envelopes,
        "summary": summarize(checks, peers, envelopes),
        "authority_boundary": [
            "Trust reports evaluate configured peer-mesh evidence only.",
            "Trust reports do not approve live work, probe peers, open sockets, copy files, discover devices, send gossip, use ADB, or launch apps.",
            "Trust reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    policy = load_json(Path(args.policy))
    route_config = load_json(Path(args.route_config))
    lab_bundle_report = load_json(Path(args.lab_bundle_report))
    envelopes = [load_json(Path(path)) for path in args.gossip_envelope]
    report = build_trust_report(
        policy,
        route_config,
        lab_bundle_report,
        envelopes,
        now_text=args.now or None,
    )
    write_json(args.output, report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public-safe configured-peer trust report.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--route-config", required=True)
    parser.add_argument("--lab-bundle-report", required=True)
    parser.add_argument("--gossip-envelope", action="append", default=[])
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
