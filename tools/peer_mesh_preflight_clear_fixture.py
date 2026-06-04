#!/usr/bin/env python3
"""Public-safe clear preflight fixture generator for peer mesh prep.

The fixture generator creates a clearly synthetic happy path for route-health,
route-history, readiness, topology, and lab-bundle preflight gates. It does not
approve live work, select endpoints, probe peers, open sockets, copy files
outside declared fixture outputs, discover devices, use ADB, send gossip,
launch apps, execute commands, or execute validation slots.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_dispatch_plan
import peer_mesh_evidence_intake
import peer_mesh_gossip
import peer_mesh_lab_bundle
import peer_mesh_live_lab_readiness
import peer_mesh_route_health
import peer_mesh_route_history
import peer_mesh_send_dry_run
import peer_mesh_topology


PREFLIGHT_FIXTURE_MANIFEST_SCHEMA = "quest-termux-lab.peer-preflight-clear-fixture-manifest.v1"
PREFLIGHT_FIXTURE_REPORT_SCHEMA = "quest-termux-lab.peer-preflight-clear-fixture-report.v1"
OVERALL_STATUSES = {"fixture_ready", "manual_review", "fixture_blocked"}
GENERATED_ARTIFACT_SCHEMAS = {
    "route_health_report": peer_mesh_route_health.ROUTE_HEALTH_REPORT_SCHEMA,
    "route_health_history": peer_mesh_route_history.ROUTE_HISTORY_SCHEMA,
    "readiness_policy": peer_mesh_live_lab_readiness.READINESS_POLICY_SCHEMA,
    "readiness_report": peer_mesh_live_lab_readiness.READINESS_REPORT_SCHEMA,
    "topology_report": peer_mesh_topology.TOPOLOGY_REPORT_SCHEMA,
    "lab_bundle_manifest": peer_mesh_lab_bundle.LAB_BUNDLE_MANIFEST_SCHEMA,
    "lab_bundle_report": peer_mesh_lab_bundle.LAB_BUNDLE_REPORT_SCHEMA,
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def write_json(path_text: str, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, sort_keys=True)
    if path_text == "-":
        print(text)
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def write_json_at(root: Path, relative_path: str, data: dict[str, Any]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_json_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    peer_mesh_evidence_intake.validate_artifact_path(value, label)
    if Path(value).suffix.lower() != ".json":
        raise ValueError(f"{label} must reference a json file")
    return value


def validate_text_array(value: Any, label: str, min_count: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < min_count:
        raise ValueError(f"{label} must contain at least {min_count} entries")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        result.append(item)
    return result


def validate_time_array(value: Any, label: str, min_count: int = 1) -> list[str]:
    result = validate_text_array(value, label, min_count=min_count)
    for item in result:
        peer_mesh_gossip.parse_time(item)
    return result


def validate_path_array(value: Any, label: str, min_count: int = 1) -> list[str]:
    result = [validate_json_path(item, f"{label} entry") for item in validate_text_array(value, label, min_count=min_count)]
    if len(result) != len(set(result)):
        raise ValueError(f"{label} entries must be unique")
    return result


def validate_output_paths(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("output_paths must be an object")
    for key in [
        "route_health_reports",
        "route_health_history",
        "readiness_policy",
        "readiness_report",
        "topology_report",
        "lab_bundle_manifest",
        "lab_bundle_report",
    ]:
        if key not in value:
            raise ValueError(f"output_paths missing {key}")
    output_paths = {
        "route_health_reports": validate_path_array(value["route_health_reports"], "output_paths.route_health_reports", min_count=2),
        "route_health_history": validate_json_path(value["route_health_history"], "output_paths.route_health_history"),
        "readiness_policy": validate_json_path(value["readiness_policy"], "output_paths.readiness_policy"),
        "readiness_report": validate_json_path(value["readiness_report"], "output_paths.readiness_report"),
        "topology_report": validate_json_path(value["topology_report"], "output_paths.topology_report"),
        "lab_bundle_manifest": validate_json_path(value["lab_bundle_manifest"], "output_paths.lab_bundle_manifest"),
        "lab_bundle_report": validate_json_path(value["lab_bundle_report"], "output_paths.lab_bundle_report"),
    }
    all_paths = list(output_paths["route_health_reports"]) + [
        output_paths["route_health_history"],
        output_paths["readiness_policy"],
        output_paths["readiness_report"],
        output_paths["topology_report"],
        output_paths["lab_bundle_manifest"],
        output_paths["lab_bundle_report"],
    ]
    if len(all_paths) != len(set(all_paths)):
        raise ValueError("output_paths entries must be unique")
    return output_paths


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != PREFLIGHT_FIXTURE_MANIFEST_SCHEMA:
        raise ValueError("unsupported preflight clear fixture manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("preflight clear fixture manifest contains command-like or credential-like fields")
    for key in [
        "fixture_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "route_config_path",
        "topology_manifest_path",
        "readiness_policy_template_path",
        "lab_bundle_manifest_template_path",
        "route_health_observed_at",
        "output_paths",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"preflight clear fixture manifest missing {key}")
    for key in [
        "fixture_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "route_config_path",
        "topology_manifest_path",
        "readiness_policy_template_path",
        "lab_bundle_manifest_template_path",
    ]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"preflight clear fixture manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_json_path(manifest["route_config_path"], "route_config_path")
    validate_json_path(manifest["topology_manifest_path"], "topology_manifest_path")
    validate_json_path(manifest["readiness_policy_template_path"], "readiness_policy_template_path")
    validate_json_path(manifest["lab_bundle_manifest_template_path"], "lab_bundle_manifest_template_path")
    observed_at = validate_time_array(manifest["route_health_observed_at"], "route_health_observed_at", min_count=2)
    output_paths = validate_output_paths(manifest["output_paths"])
    if len(output_paths["route_health_reports"]) != len(observed_at):
        raise ValueError("output_paths.route_health_reports length must match route_health_observed_at")
    validate_text_array(manifest["authority_boundary"], "authority_boundary")


def identity_check(document: dict[str, Any], manifest: dict[str, Any], label: str) -> None:
    if document.get("fleet_id") != manifest["fleet_id"]:
        raise ValueError(f"{label} fleet_id mismatch")
    if document.get("source_agent_id") != manifest["source_agent_id"]:
        raise ValueError(f"{label} source_agent_id mismatch")
    if document.get("experiment_scope") and document.get("experiment_scope") != manifest["experiment_scope"]:
        raise ValueError(f"{label} experiment_scope mismatch")


def method_for_route(route: dict[str, Any]) -> str:
    mode = str(route["transport_mode"])
    if mode == "loopback_http_simulator":
        return "post_gossip"
    if mode == "file_drop_simulator":
        return "copy_envelope"
    return "not_sent"


def synthetic_send_report(route_config: dict[str, Any], observed_at: str, index: int) -> dict[str, Any]:
    actions = []
    for route_index, route in enumerate(route_config["routes"], start=1):
        target = str(route["target_agent_id"])
        message_id = f"gossip-clear-{index:02d}-{route_index:02d}"
        actions.append(
            {
                "delivery_id": f"delivery-clear-{index:02d}-{route_index:02d}",
                "target_agent_id": target,
                "message_id": message_id,
                "dispatch_decision": "ready",
                "simulated_outcome": "accepted",
                "transport_mode": route["transport_mode"],
                "method": method_for_route(route),
                "delivery_state_after": "accepted",
                "reason": None,
            }
        )
    return {
        "schema": peer_mesh_send_dry_run.REPORT_SCHEMA,
        "fleet_id": route_config["fleet_id"],
        "source_agent_id": route_config["source_agent_id"],
        "observed_at": observed_at,
        "actions": actions,
        "summary": {
            "action_count": len(actions),
            "accepted_count": len(actions),
            "duplicate_count": 0,
            "rejected_count": 0,
            "no_response_count": 0,
            "not_sent_count": 0,
        },
        "authority_boundary": [
            "Synthetic clear send reports are fixture inputs only.",
            "Synthetic clear send reports do not open sockets, copy files, discover peers, send gossip, use ADB, or launch apps.",
            "Synthetic clear send reports do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, or launch requests.",
        ],
    }


def clear_readiness_policy(template: dict[str, Any], manifest: dict[str, Any], history_report_count: int, tracked_routes: int) -> dict[str, Any]:
    policy = copy.deepcopy(template)
    policy["observed_at"] = manifest["observed_at"]
    policy["min_history_reports"] = history_report_count
    policy["min_tracked_routes"] = tracked_routes
    policy["allowed_last_statuses"] = ["healthy"]
    policy["acceptable_trends"] = ["stable", "single_sample"]
    policy["require_no_unavailable_routes"] = True
    policy["require_no_unknown_routes"] = True
    policy["require_no_disabled_routes"] = True
    policy["require_no_worsening_routes"] = True
    policy["operator_approval_required"] = False
    return policy


def clear_lab_bundle_manifest(template: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    output_paths = manifest["output_paths"]
    bundle = copy.deepcopy(template)
    bundle["observed_at"] = manifest["observed_at"]
    bundle["experiment_id"] = f"{manifest['fixture_id']}-lab-bundle"
    bundle["operator_approval_required"] = False
    bundle["operator_approval_recorded"] = False
    bundle["artifact_paths"] = {
        "route_config": manifest["route_config_path"],
        "topology_report": output_paths["topology_report"],
        "route_history": output_paths["route_health_history"],
        "readiness_report": output_paths["readiness_report"],
    }
    return bundle


def generated_entry(kind: str, path: str, schema: str, written: bool, reason: str) -> dict[str, Any]:
    if kind not in GENERATED_ARTIFACT_SCHEMAS:
        raise ValueError("unsupported generated artifact kind")
    return {
        "artifact_kind": kind,
        "path": path,
        "schema": schema,
        "status": "written" if written else "prepared",
        "reason": reason,
    }


def generated_artifacts(manifest: dict[str, Any], outputs: dict[str, Any], written: bool) -> list[dict[str, Any]]:
    output_paths = manifest["output_paths"]
    entries = [
        generated_entry(
            "route_health_report",
            path,
            peer_mesh_route_health.ROUTE_HEALTH_REPORT_SCHEMA,
            written,
            f"synthetic clear route-health report {index + 1} generated",
        )
        for index, path in enumerate(output_paths["route_health_reports"])
    ]
    entries.extend(
        [
            generated_entry("route_health_history", output_paths["route_health_history"], peer_mesh_route_history.ROUTE_HISTORY_SCHEMA, written, "synthetic clear route-health history generated"),
            generated_entry("readiness_policy", output_paths["readiness_policy"], peer_mesh_live_lab_readiness.READINESS_POLICY_SCHEMA, written, "synthetic no-manual-gate readiness policy generated"),
            generated_entry("readiness_report", output_paths["readiness_report"], peer_mesh_live_lab_readiness.READINESS_REPORT_SCHEMA, written, f"synthetic readiness report generated with status {outputs['readiness_report']['overall_status']}"),
            generated_entry("topology_report", output_paths["topology_report"], peer_mesh_topology.TOPOLOGY_REPORT_SCHEMA, written, f"synthetic topology report generated with status {outputs['topology_report']['overall_status']}"),
            generated_entry("lab_bundle_manifest", output_paths["lab_bundle_manifest"], peer_mesh_lab_bundle.LAB_BUNDLE_MANIFEST_SCHEMA, written, "synthetic no-manual-gate lab bundle manifest generated"),
            generated_entry("lab_bundle_report", output_paths["lab_bundle_report"], peer_mesh_lab_bundle.LAB_BUNDLE_REPORT_SCHEMA, written, f"synthetic lab bundle report generated with status {outputs['lab_bundle_report']['overall_status']}"),
        ]
    )
    return entries


def summarize_fixture(outputs: dict[str, Any], generated_count: int) -> dict[str, Any]:
    latest_health = outputs["route_health_reports"][-1]
    history = outputs["route_health_history"]
    readiness = outputs["readiness_report"]
    topology = outputs["topology_report"]
    bundle = outputs["lab_bundle_report"]
    return {
        "generated_artifact_count": generated_count,
        "route_health_report_count": len(outputs["route_health_reports"]),
        "latest_healthy_route_count": latest_health["summary"]["healthy_count"],
        "latest_unknown_route_count": latest_health["summary"]["unknown_count"],
        "tracked_route_count": history["summary"]["tracked_route_count"],
        "stable_route_count": history["summary"]["stable_count"],
        "readiness_ready_route_count": readiness["summary"]["ready_route_count"],
        "topology_reachable_agent_count": topology["summary"]["reachable_agent_count"],
        "topology_non_ready_edge_count": topology["summary"]["non_ready_edge_count"],
        "lab_bundle_ready_route_count": bundle["summary"]["ready_route_count"],
    }


def status_for_outputs(outputs: dict[str, Any]) -> str:
    latest_health = outputs["route_health_reports"][-1]
    history = outputs["route_health_history"]
    readiness = outputs["readiness_report"]
    topology = outputs["topology_report"]
    bundle = outputs["lab_bundle_report"]
    if latest_health["summary"]["unknown_count"] or latest_health["summary"]["unavailable_count"] or latest_health["summary"]["disabled_count"]:
        return "fixture_blocked"
    if history["summary"]["last_unknown_count"] or history["summary"]["last_unavailable_count"] or history["summary"]["last_disabled_count"]:
        return "fixture_blocked"
    if readiness["overall_status"] == "not_ready":
        return "fixture_blocked"
    if topology["overall_status"] == "topology_blocked":
        return "fixture_blocked"
    if bundle["overall_status"] == "blocked":
        return "fixture_blocked"
    if readiness["overall_status"] == "manual_review" or topology["overall_status"] == "manual_review" or bundle["overall_status"] == "manual_review":
        return "manual_review"
    return "fixture_ready"


def build_preflight_clear_fixture(
    manifest: dict[str, Any],
    route_config: dict[str, Any],
    topology_manifest: dict[str, Any],
    readiness_policy_template: dict[str, Any],
    lab_bundle_manifest_template: dict[str, Any],
    artifact_root: Path,
    write_outputs: bool = True,
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    peer_mesh_dispatch_plan.validate_route_config(route_config)
    peer_mesh_topology.validate_manifest(topology_manifest)
    peer_mesh_live_lab_readiness.validate_policy(readiness_policy_template)
    peer_mesh_lab_bundle.validate_manifest(lab_bundle_manifest_template)
    for label, document in [
        ("route_config", route_config),
        ("topology_manifest", topology_manifest),
        ("readiness_policy_template", readiness_policy_template),
        ("lab_bundle_manifest_template", lab_bundle_manifest_template),
    ]:
        identity_check(document, manifest, label)

    health_reports = [
        peer_mesh_route_health.build_route_health_report(
            route_config,
            send_report=synthetic_send_report(route_config, observed_at, index),
            now_text=observed_at,
        )
        for index, observed_at in enumerate(manifest["route_health_observed_at"], start=1)
    ]
    history = peer_mesh_route_history.build_history(health_reports, now_text=str(manifest["observed_at"]))
    readiness_policy = clear_readiness_policy(
        readiness_policy_template,
        manifest,
        history_report_count=len(health_reports),
        tracked_routes=int(history["summary"]["tracked_route_count"]),
    )
    readiness = peer_mesh_live_lab_readiness.build_readiness_report(
        readiness_policy,
        history,
        now_text=str(manifest["observed_at"]),
    )
    topology = peer_mesh_topology.build_topology_report(
        topology_manifest,
        route_config,
        health_reports[-1],
        now_text=str(manifest["observed_at"]),
    )
    lab_manifest = clear_lab_bundle_manifest(lab_bundle_manifest_template, manifest)
    bundle = peer_mesh_lab_bundle.build_bundle_report(
        lab_manifest,
        route_config,
        topology,
        history,
        readiness,
        now_text=str(manifest["observed_at"]),
    )
    outputs = {
        "route_health_reports": health_reports,
        "route_health_history": history,
        "readiness_policy": readiness_policy,
        "readiness_report": readiness,
        "topology_report": topology,
        "lab_bundle_manifest": lab_manifest,
        "lab_bundle_report": bundle,
    }
    if write_outputs:
        for path, report in zip(manifest["output_paths"]["route_health_reports"], health_reports):
            write_json_at(artifact_root, path, report)
        write_json_at(artifact_root, manifest["output_paths"]["route_health_history"], history)
        write_json_at(artifact_root, manifest["output_paths"]["readiness_policy"], readiness_policy)
        write_json_at(artifact_root, manifest["output_paths"]["readiness_report"], readiness)
        write_json_at(artifact_root, manifest["output_paths"]["topology_report"], topology)
        write_json_at(artifact_root, manifest["output_paths"]["lab_bundle_manifest"], lab_manifest)
        write_json_at(artifact_root, manifest["output_paths"]["lab_bundle_report"], bundle)
    generated = generated_artifacts(manifest, outputs, write_outputs)
    return {
        "schema": PREFLIGHT_FIXTURE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "fixture_id": manifest["fixture_id"],
        "experiment_scope": manifest["experiment_scope"],
        "route_health_status": "clear" if outputs["route_health_reports"][-1]["summary"]["unknown_count"] == 0 else "blocked",
        "route_history_status": "clear" if outputs["route_health_history"]["summary"]["last_unknown_count"] == 0 else "blocked",
        "readiness_status": readiness["overall_status"],
        "topology_status": topology["overall_status"],
        "lab_bundle_status": bundle["overall_status"],
        "overall_status": status_for_outputs(outputs),
        "generated_artifacts": generated,
        "summary": summarize_fixture(outputs, len(generated)),
        "authority_boundary": [
            "Preflight clear fixtures generate public-safe synthetic route preflight documents only.",
            "Preflight clear fixtures do not approve live work, select endpoints, probe peers, open sockets, copy files outside declared fixture outputs, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "A fixture_ready result means only that the synthetic preflight gates compose under declared fixture inputs; it is not live fleet readiness.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    root = Path(args.artifact_root)
    manifest = load_json(Path(args.manifest))
    validate_manifest(manifest)
    report = build_preflight_clear_fixture(
        manifest,
        load_json(root / str(manifest["route_config_path"])),
        load_json(root / str(manifest["topology_manifest_path"])),
        load_json(root / str(manifest["readiness_policy_template_path"])),
        load_json(root / str(manifest["lab_bundle_manifest_template_path"])),
        root,
        write_outputs=True,
        now_text=args.now or None,
    )
    write_json(args.output, report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build public-safe clear preflight fixtures.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
