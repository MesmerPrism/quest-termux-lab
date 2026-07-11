"""Validate the public-lab source profile consumed by sidecar workflow DAGs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "quest-termux-lab.peer-workflow-source-profile.v1"
PROFILE = "public-lab-peer-evidence-v1"
PHASES = ["source", "privacy"]
FORBIDDEN_KEYS = {
    "adb_target", "command", "command_payload", "credentials", "endpoint",
    "host", "ip", "package_id", "pairing_material", "private_device_id",
    "raw_log", "screenshot", "shell", "token",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("profile root must be an object")
    return value


def forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.lower() in FORBIDDEN_KEYS:
                found.append(child_path)
            found.extend(forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_paths(child, f"{path}[{index}]"))
    return found


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if profile.get("schema") != SCHEMA:
        errors.append("unexpected profile schema")
    if profile.get("profile_id") != PROFILE:
        errors.append("unexpected profile_id")
    if profile.get("owner") != "quest-termux-lab":
        errors.append("owner must remain quest-termux-lab")
    if profile.get("contributes_phases") != PHASES:
        errors.append("public profile must contribute source and privacy only")
    artifacts = profile.get("source_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) < 4:
        errors.append("source_artifacts must contain at least four compatibility artifacts")
    else:
        for artifact in artifacts:
            if not isinstance(artifact, dict) or set(artifact) != {"path", "schema", "role"}:
                errors.append("source artifact entries must contain only path, schema, and role")
                continue
            if not str(artifact["path"]).startswith("examples/") or ".." in str(artifact["path"]):
                errors.append("source artifact paths must stay inside examples")
            if not str(artifact["schema"]).startswith("quest-termux-lab."):
                errors.append("source artifact schemas must stay in the public-lab namespace")
        topology = [
            artifact for artifact in artifacts
            if artifact.get("schema") == "quest-termux-lab.peer-topology-report.v1"
            and artifact.get("role") == "n_peer_advisory_topology"
        ]
        if len(topology) != 1:
            errors.append("source_artifacts must contain exactly one N-peer advisory topology")
    privacy = profile.get("privacy_boundary", {})
    if privacy.get("synthetic_only") is not True:
        errors.append("privacy boundary must be synthetic_only")
    for key in ["contains_endpoints", "contains_commands", "contains_credentials", "contains_pairing_material", "contains_private_device_ids", "contains_raw_logs", "contains_visual_captures", "allows_high_rate_payloads"]:
        if privacy.get(key) is not False:
            errors.append(f"privacy_boundary.{key} must be false")
    authority = profile.get("authority_boundary", {})
    if authority != {"role": "public_evidence_source", "runtime_authority": False, "accepted_state_owner": "rusty.manifold", "command_authority": False}:
        errors.append("authority boundary must remain public evidence only")
    compatibility = profile.get("compatibility", {})
    if compatibility != {"legacy_schemas_preserved": True, "legacy_tools_preserved": True, "new_execution_stage": False}:
        errors.append("compatibility must preserve v1 schemas/tools without an execution stage")
    for found in forbidden_paths(profile):
        errors.append(f"forbidden authority or private field: {found}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    args = parser.parse_args()
    path = Path(args.profile)
    errors = validate_profile(load_json(path))
    result = {"schema": "quest-termux-lab.peer-workflow-source-profile-validation.v1", "profile": str(path), "status": "pass" if not errors else "fail", "errors": errors}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
