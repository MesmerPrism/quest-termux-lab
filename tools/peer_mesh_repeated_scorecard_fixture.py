#!/usr/bin/env python3
"""Public-safe repeated scorecard fixture generator for peer mesh prep.

The fixture generator creates a clearly synthetic two-or-more scorecard path
from an existing public scorecard template, then runs the existing history and
regression gates over it. It does not approve live work, select endpoints,
replay evidence, monitor peers, probe peers, open sockets, discover devices,
use ADB, send gossip, launch apps, execute commands, or execute validation
slots.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import peer_mesh_evidence_intake
import peer_mesh_gossip
import peer_mesh_live_lab_readiness
import peer_mesh_scorecard
import peer_mesh_scorecard_history
import peer_mesh_scorecard_regression


REPEATED_FIXTURE_MANIFEST_SCHEMA = "quest-termux-lab.peer-repeated-scorecard-fixture-manifest.v1"
REPEATED_FIXTURE_REPORT_SCHEMA = "quest-termux-lab.peer-repeated-scorecard-fixture-report.v1"
OVERALL_STATUSES = {"fixture_ready", "manual_review", "fixture_blocked"}
GENERATED_ARTIFACT_KINDS = {
    "scorecard_report",
    "scorecard_history",
    "scorecard_regression_report",
}
CLEAR_SOURCE_STATUS = {
    "readiness_report": "ready",
    "lab_bundle_report": "synthetic_ready",
    "trust_report": "trusted",
    "rehearsal_report": "rehearsal_ready",
    "evidence_intake_report": "accepted",
    "route_health_report": "clear",
    "route_history_report": "clear",
    "cleanup_record": "completed",
}
CLEAR_REASON = {
    "readiness_report": "readiness report is synthetically ready",
    "lab_bundle_report": "lab bundle is synthetically ready",
    "trust_report": "trust report is synthetically trusted",
    "rehearsal_report": "rehearsal report is synthetically ready",
    "evidence_intake_report": "evidence intake is synthetically accepted",
    "route_health_report": "route-health report is synthetically clear",
    "route_history_report": "route-history report is synthetically clear",
    "cleanup_record": "cleanup record is synthetically completed",
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


def validate_path_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    paths = [validate_json_path(item, f"{label} entry") for item in value]
    if len(paths) != len(set(paths)):
        raise ValueError(f"{label} entries must be unique")
    return paths


def validate_text_array(value: Any, label: str, min_count: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < min_count:
        raise ValueError(f"{label} must contain at least {min_count} entries")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} entries must be non-empty strings")
        result.append(item)
    return result


def validate_output_paths(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("output_paths must be an object")
    for key in ["scorecard_reports", "scorecard_history", "scorecard_regression_report"]:
        if key not in value:
            raise ValueError(f"output_paths missing {key}")
    scorecard_reports = validate_path_array(value["scorecard_reports"], "output_paths.scorecard_reports")
    scorecard_history = validate_json_path(value["scorecard_history"], "output_paths.scorecard_history")
    regression_report = validate_json_path(
        value["scorecard_regression_report"],
        "output_paths.scorecard_regression_report",
    )
    all_paths = scorecard_reports + [scorecard_history, regression_report]
    if len(all_paths) != len(set(all_paths)):
        raise ValueError("output_paths entries must be unique")
    return {
        "scorecard_reports": scorecard_reports,
        "scorecard_history": scorecard_history,
        "scorecard_regression_report": regression_report,
    }


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != REPEATED_FIXTURE_MANIFEST_SCHEMA:
        raise ValueError("unsupported repeated scorecard fixture manifest schema")
    if peer_mesh_gossip.contains_forbidden_key(manifest):
        raise ValueError("repeated scorecard fixture manifest contains command-like or credential-like fields")
    for key in [
        "fixture_id",
        "fleet_id",
        "source_agent_id",
        "observed_at",
        "experiment_scope",
        "scorecard_template_path",
        "regression_policy_path",
        "scorecard_ids",
        "scorecard_observed_at",
        "output_paths",
        "authority_boundary",
    ]:
        if key not in manifest:
            raise ValueError(f"repeated scorecard fixture manifest missing {key}")
    for key in ["fixture_id", "fleet_id", "source_agent_id", "observed_at"]:
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError(f"repeated scorecard fixture manifest missing {key}")
    peer_mesh_gossip.parse_time(str(manifest["observed_at"]))
    if manifest["experiment_scope"] not in peer_mesh_live_lab_readiness.EXPERIMENT_SCOPES:
        raise ValueError("unsupported experiment_scope")
    validate_json_path(manifest["scorecard_template_path"], "scorecard_template_path")
    validate_json_path(manifest["regression_policy_path"], "regression_policy_path")
    scorecard_ids = validate_text_array(manifest["scorecard_ids"], "scorecard_ids", min_count=2)
    observed_at = validate_text_array(manifest["scorecard_observed_at"], "scorecard_observed_at", min_count=2)
    for value in observed_at:
        peer_mesh_gossip.parse_time(value)
    if len(scorecard_ids) != len(observed_at):
        raise ValueError("scorecard_ids and scorecard_observed_at must have the same length")
    if len(scorecard_ids) != len(set(scorecard_ids)):
        raise ValueError("scorecard_ids entries must be unique")
    output_paths = validate_output_paths(manifest["output_paths"])
    if len(output_paths["scorecard_reports"]) != len(scorecard_ids):
        raise ValueError("output_paths.scorecard_reports length must match scorecard_ids")
    authority = validate_text_array(manifest["authority_boundary"], "authority_boundary")
    if not authority:
        raise ValueError("authority_boundary must not be empty")


def clear_artifact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    kind = str(entry.get("artifact_kind", ""))
    if kind not in peer_mesh_scorecard.ARTIFACT_SCHEMAS:
        raise ValueError("scorecard template contains unsupported artifact kind")
    expected_schema = str(entry.get("expected_schema", peer_mesh_scorecard.ARTIFACT_SCHEMAS[kind]))
    if expected_schema != peer_mesh_scorecard.ARTIFACT_SCHEMAS[kind]:
        raise ValueError("scorecard template expected_schema mismatch")
    return {
        "artifact_kind": kind,
        "required": bool(entry.get("required", False)),
        "status": "synthetic_clear",
        "source_status": CLEAR_SOURCE_STATUS[kind],
        "expected_schema": expected_schema,
        "observed_schema": expected_schema,
        "reason": CLEAR_REASON[kind],
    }


def clear_scorecard_from_template(
    template: dict[str, Any],
    manifest: dict[str, Any],
    scorecard_id: str,
    observed_at: str,
) -> dict[str, Any]:
    peer_mesh_scorecard_history.validate_scorecard_report(template)
    entries = [clear_artifact_entry(entry) for entry in template["artifacts"]]
    if not entries:
        raise ValueError("scorecard template must contain artifacts")
    if len({entry["artifact_kind"] for entry in entries}) != len(entries):
        raise ValueError("scorecard template artifact kinds must be unique")
    return {
        "schema": peer_mesh_scorecard.SCORECARD_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": observed_at,
        "scorecard_id": scorecard_id,
        "experiment_scope": manifest["experiment_scope"],
        "overall_status": peer_mesh_scorecard.overall_status(entries),
        "artifacts": entries,
        "pressure_points": peer_mesh_scorecard.pressure_points(entries),
        "summary": peer_mesh_scorecard.summarize(entries),
        "authority_boundary": [
            "Generated clear scorecards are synthetic fixture documents only.",
            "Generated clear scorecards do not approve live work, select endpoints, replay evidence, monitor peers, probe peers, open sockets, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "Generated clear scorecards do not carry gossip bodies, commands, shell text, ADB targets, pairing material, install requests, launch requests, or private endpoint values.",
        ],
    }


def status_for_outputs(scorecards: list[dict[str, Any]], history: dict[str, Any], regression: dict[str, Any]) -> str:
    if any(scorecard["overall_status"] == "blocked" for scorecard in scorecards):
        return "fixture_blocked"
    if history["overall_status"] == "blocked" or regression["overall_status"] == "regression_blocked":
        return "fixture_blocked"
    if any(scorecard["overall_status"] == "manual_review" for scorecard in scorecards):
        return "manual_review"
    if history["overall_status"] == "manual_review" or regression["overall_status"] == "manual_review":
        return "manual_review"
    return "fixture_ready"


def generated_entry(kind: str, path: str, schema: str, written: bool, reason: str) -> dict[str, Any]:
    if kind not in GENERATED_ARTIFACT_KINDS:
        raise ValueError("unsupported generated artifact kind")
    return {
        "artifact_kind": kind,
        "path": path,
        "schema": schema,
        "status": "written" if written else "prepared",
        "reason": reason,
    }


def generated_artifacts(
    manifest: dict[str, Any],
    scorecards: list[dict[str, Any]],
    history: dict[str, Any],
    regression: dict[str, Any],
    written: bool,
) -> list[dict[str, Any]]:
    output_paths = manifest["output_paths"]
    entries = [
        generated_entry(
            "scorecard_report",
            path,
            peer_mesh_scorecard.SCORECARD_REPORT_SCHEMA,
            written,
            f"synthetic clear scorecard {scorecards[index]['scorecard_id']} generated",
        )
        for index, path in enumerate(output_paths["scorecard_reports"])
    ]
    entries.append(
        generated_entry(
            "scorecard_history",
            output_paths["scorecard_history"],
            peer_mesh_scorecard_history.SCORECARD_HISTORY_SCHEMA,
            written,
            f"synthetic scorecard history generated with {history['report_count']} reports",
        )
    )
    entries.append(
        generated_entry(
            "scorecard_regression_report",
            output_paths["scorecard_regression_report"],
            peer_mesh_scorecard_regression.REGRESSION_REPORT_SCHEMA,
            written,
            f"synthetic scorecard regression generated with status {regression['overall_status']}",
        )
    )
    return entries


def summarize_fixture(
    scorecards: list[dict[str, Any]],
    history: dict[str, Any],
    regression: dict[str, Any],
    generated_count: int,
) -> dict[str, Any]:
    return {
        "scorecard_count": len(scorecards),
        "generated_artifact_count": generated_count,
        "synthetic_clear_scorecard_count": sum(1 for scorecard in scorecards if scorecard["overall_status"] == "synthetic_clear"),
        "history_report_count": int(history["report_count"]),
        "history_pressure_point_count": len(history["pressure_point_deltas"]),
        "regression_check_count": int(regression["summary"]["check_count"]),
        "regression_failed_check_count": int(regression["summary"]["failed_check_count"]),
    }


def build_repeated_fixture(
    manifest: dict[str, Any],
    scorecard_template: dict[str, Any],
    regression_policy: dict[str, Any],
    artifact_root: Path,
    write_outputs: bool = True,
    now_text: str | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    peer_mesh_scorecard_regression.validate_policy(regression_policy)
    if regression_policy["fleet_id"] != manifest["fleet_id"]:
        raise ValueError("scorecard regression policy fleet_id mismatch")
    if regression_policy["source_agent_id"] != manifest["source_agent_id"]:
        raise ValueError("scorecard regression policy source_agent_id mismatch")
    if regression_policy["experiment_scope"] != manifest["experiment_scope"]:
        raise ValueError("scorecard regression policy experiment_scope mismatch")

    scorecards = [
        clear_scorecard_from_template(scorecard_template, manifest, scorecard_id, observed_at)
        for scorecard_id, observed_at in zip(manifest["scorecard_ids"], manifest["scorecard_observed_at"])
    ]
    history = peer_mesh_scorecard_history.build_history(scorecards, now_text=str(manifest["observed_at"]))
    regression = peer_mesh_scorecard_regression.build_regression_report(
        regression_policy,
        history,
        now_text=str(manifest["observed_at"]),
    )
    if write_outputs:
        for path, scorecard in zip(manifest["output_paths"]["scorecard_reports"], scorecards):
            write_json_at(artifact_root, path, scorecard)
        write_json_at(artifact_root, manifest["output_paths"]["scorecard_history"], history)
        write_json_at(artifact_root, manifest["output_paths"]["scorecard_regression_report"], regression)
    generated = generated_artifacts(manifest, scorecards, history, regression, write_outputs)
    return {
        "schema": REPEATED_FIXTURE_REPORT_SCHEMA,
        "fleet_id": manifest["fleet_id"],
        "source_agent_id": manifest["source_agent_id"],
        "observed_at": now_text or str(manifest["observed_at"]),
        "fixture_id": manifest["fixture_id"],
        "experiment_scope": manifest["experiment_scope"],
        "scorecard_ids": list(manifest["scorecard_ids"]),
        "history_status": history["overall_status"],
        "history_trend": history["overall_trend"],
        "regression_status": regression["overall_status"],
        "overall_status": status_for_outputs(scorecards, history, regression),
        "generated_artifacts": generated,
        "summary": summarize_fixture(scorecards, history, regression, len(generated)),
        "authority_boundary": [
            "Repeated scorecard fixtures generate public-safe synthetic scorecard, history, and regression documents only.",
            "Repeated scorecard fixtures do not approve live work, select endpoints, replay evidence, monitor peers, probe peers, open sockets, discover devices, send gossip, use ADB, launch apps, execute commands, or execute validation slots.",
            "A fixture_ready result means only that the synthetic repeated-scorecard path is internally stable under the declared public policy.",
        ],
    }


def run_cli(args: argparse.Namespace) -> int:
    root = Path(args.artifact_root)
    manifest = load_json(Path(args.manifest))
    validate_manifest(manifest)
    scorecard_template = load_json(root / str(manifest["scorecard_template_path"]))
    regression_policy = load_json(root / str(manifest["regression_policy_path"]))
    report = build_repeated_fixture(
        manifest,
        scorecard_template,
        regression_policy,
        root,
        write_outputs=True,
        now_text=args.now or None,
    )
    write_json(args.output, report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build public-safe repeated scorecard fixtures.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default=".")
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
