#!/usr/bin/env python3
"""Validate a public-safe proposal handoff for Manifold peer authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "quest-termux-lab.peer-authority-source-handoff.v1"
TARGET_CONTRACTS = {
    "credential_record": "rusty.manifold.peer.credential_record.v1",
    "enrollment_request": "rusty.manifold.peer.enrollment_request.v1",
    "enrollment_receipt": "rusty.manifold.peer.enrollment_receipt.v1",
    "signed_rendezvous_evidence": "rusty.manifold.peer.signed_rendezvous_evidence.v1",
    "rendezvous_review_request": "rusty.manifold.peer.rendezvous_review_request.v1",
    "rendezvous_receipt": "rusty.manifold.peer.rendezvous_receipt.v1",
    "signed_session_review": "rusty.manifold.peer.signed_session_review.v1",
    "signed_topology_authorization": "rusty.manifold.peer.signed_topology_authorization.v1",
    "direct_lane_lease_request": "rusty.manifold.peer.direct_lane_lease_request.v1",
    "direct_lane_lease_receipt": "rusty.manifold.peer.direct_lane_lease_receipt.v1",
}
TOPOLOGY_CONTRACT = "rusty.quest.product_wifi_direct_topology.v1"
EXPECTED_AUTHORITY = {
    "role": "public_evidence_proposer",
    "performs_ed25519_verification": False,
    "owns_accepted_state": False,
    "owns_coordinator": False,
    "owns_direct_lane_lease": False,
    "owns_media_authority": False,
}
EXPECTED_PRIVACY = {
    "contains_private_key_material": False,
    "contains_pairing_material": False,
    "contains_endpoint_values": False,
    "contains_commands": False,
    "contains_private_device_ids": False,
    "contains_raw_logs": False,
    "contains_media_payloads": False,
}
FORBIDDEN_KEYS = {
    "private_key", "private_key_hex", "secret", "pairing_material", "endpoint",
    "endpoint_value", "adb_target", "command", "command_payload", "token",
    "accepted_state", "coordinator_decision", "lease_authorized", "media_payload",
    "gossip_grant", "topology_grant",
}
LOWER_HEX_32 = re.compile(r"^[0-9a-f]{64}$")
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{128}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("handoff root must be an object")
    return value


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.lower() in FORBIDDEN_KEYS:
                found.append(child_path)
            found.extend(_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{path}[{index}]"))
    return found


def validate_handoff(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_root = {"schema", "handoff_id", "synthetic", "target_contracts", "enrollment_requests", "signed_evidence_proposals", "configured_peers", "authority_boundary", "privacy_boundary"}
    if set(document) != expected_root:
        errors.append("source handoff fields must match the v1 closed shape")
    if document.get("schema") != SCHEMA:
        errors.append("unexpected source handoff schema")
    if document.get("synthetic") is not True:
        errors.append("public fixture must declare synthetic=true")
    if document.get("target_contracts") != TARGET_CONTRACTS:
        errors.append("Manifold target contract ids/versions must match exactly")
    if document.get("authority_boundary") != EXPECTED_AUTHORITY:
        errors.append("authority boundary must remain proposal-only")
    if document.get("privacy_boundary") != EXPECTED_PRIVACY:
        errors.append("privacy boundary must remain public and payload-free")

    enrollments = document.get("enrollment_requests")
    if not isinstance(enrollments, list) or not enrollments:
        errors.append("enrollment_requests must contain proposals")
        enrollments = []
    enrollment_by_id: dict[str, dict[str, Any]] = {}
    enrollment_by_peer: dict[str, dict[str, Any]] = {}
    for request in enrollments:
        if not isinstance(request, dict):
            errors.append("enrollment request must be an object")
            continue
        expected_fields = {"proposal_id", "target_schema", "credential_schema", "action", "operator_id", "operator_request_ref", "expected_enrollment_authority_revision", "credential_id", "peer_id", "trust_domain", "key_id", "key_generation", "public_key_hex", "public_key_sha256", "valid_from_ms", "expires_at_ms", "proposed_only"}
        if set(request) != expected_fields:
            errors.append("enrollment request fields must match the v1 closed shape")
        proposal_id = request.get("proposal_id")
        if not isinstance(proposal_id, str) or proposal_id in enrollment_by_id:
            errors.append("enrollment proposal ids must be unique strings")
        else:
            enrollment_by_id[proposal_id] = request
        if request.get("target_schema") != TARGET_CONTRACTS["enrollment_request"]:
            errors.append(f"enrollment {proposal_id!r} target schema mismatch")
        if request.get("credential_schema") != TARGET_CONTRACTS["credential_record"]:
            errors.append(f"enrollment {proposal_id!r} credential schema mismatch")
        if request.get("action") != "enroll" or request.get("proposed_only") is not True:
            errors.append(f"enrollment {proposal_id!r} must remain an enroll proposal")
        if not LOWER_HEX_32.fullmatch(str(request.get("public_key_hex", ""))):
            errors.append(f"enrollment {proposal_id!r} public key must be canonical public hex")
        if not SHA256.fullmatch(str(request.get("public_key_sha256", ""))):
            errors.append(f"enrollment {proposal_id!r} public key digest must be canonical")
        elif LOWER_HEX_32.fullmatch(str(request.get("public_key_hex", ""))) and request["public_key_sha256"] != f"sha256:{hashlib.sha256(bytes.fromhex(request['public_key_hex'])).hexdigest()}":
            errors.append(f"enrollment {proposal_id!r} public key digest mismatch")
        if not isinstance(request.get("expected_enrollment_authority_revision"), int) or request["expected_enrollment_authority_revision"] < 1:
            errors.append(f"enrollment {proposal_id!r} must name a positive expected revision")
        peer_id = request.get("peer_id")
        if isinstance(peer_id, str):
            if peer_id in enrollment_by_peer:
                errors.append(f"peer {peer_id!r} has duplicate enrollment proposals")
            enrollment_by_peer[peer_id] = request
        if not isinstance(request.get("key_generation"), int) or request["key_generation"] < 1:
            errors.append(f"enrollment {proposal_id!r} key generation must be positive")
        if not isinstance(request.get("valid_from_ms"), int) or not isinstance(request.get("expires_at_ms"), int) or request["valid_from_ms"] >= request["expires_at_ms"]:
            errors.append(f"enrollment {proposal_id!r} validity window is invalid")

    evidence = document.get("signed_evidence_proposals")
    if not isinstance(evidence, list) or len(evidence) < 2:
        errors.append("signed_evidence_proposals must contain a reciprocal pair")
        evidence = []
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for proposal in evidence:
        if not isinstance(proposal, dict):
            errors.append("signed evidence proposal must be an object")
            continue
        expected_fields = {"proposal_id", "target_schema", "review_request_schema", "review_request_ref", "expected_rendezvous_authority_revision", "expected_enrollment_authority_revision", "evidence_id", "signer_peer_id", "signer_key_id", "counterparty_peer_id", "nonce_hex", "coordinator_epoch", "role", "topology_contract_id", "issued_at_ms", "expires_at_ms", "signature_hex", "provenance_refs", "proposed_only", "cryptographic_verification_performed"}
        if set(proposal) != expected_fields:
            errors.append("signed evidence fields must match the v1 closed shape")
        proposal_id = proposal.get("proposal_id")
        if not isinstance(proposal_id, str) or proposal_id in evidence_by_id:
            errors.append("signed evidence proposal ids must be unique strings")
        else:
            evidence_by_id[proposal_id] = proposal
        if proposal.get("target_schema") != TARGET_CONTRACTS["signed_rendezvous_evidence"]:
            errors.append(f"evidence {proposal_id!r} target schema mismatch")
        if proposal.get("review_request_schema") != TARGET_CONTRACTS["rendezvous_review_request"]:
            errors.append(f"evidence {proposal_id!r} review schema mismatch")
        if not isinstance(proposal.get("expected_rendezvous_authority_revision"), int) or proposal["expected_rendezvous_authority_revision"] < 1:
            errors.append(f"evidence {proposal_id!r} must name a positive rendezvous revision")
        if not isinstance(proposal.get("expected_enrollment_authority_revision"), int) or proposal["expected_enrollment_authority_revision"] < 1:
            errors.append(f"evidence {proposal_id!r} must name a positive enrollment revision")
        if proposal.get("topology_contract_id") != TOPOLOGY_CONTRACT:
            errors.append(f"evidence {proposal_id!r} topology contract mismatch")
        if proposal.get("proposed_only") is not True or proposal.get("cryptographic_verification_performed") is not False:
            errors.append(f"evidence {proposal_id!r} must remain unverified proposal data")
        if not LOWER_HEX_32.fullmatch(str(proposal.get("nonce_hex", ""))):
            errors.append(f"evidence {proposal_id!r} nonce must be canonical public hex")
        if not LOWER_HEX_64.fullmatch(str(proposal.get("signature_hex", ""))):
            errors.append(f"evidence {proposal_id!r} signature must be canonical public hex")
        refs = proposal.get("provenance_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
            errors.append(f"evidence {proposal_id!r} requires opaque provenance refs")
        enrollment = enrollment_by_peer.get(str(proposal.get("signer_peer_id")))
        if enrollment is None or enrollment.get("key_id") != proposal.get("signer_key_id"):
            errors.append(f"evidence {proposal_id!r} signer key lacks an enrollment proposal")
        issued_at = proposal.get("issued_at_ms")
        expires_at = proposal.get("expires_at_ms")
        if not isinstance(issued_at, int) or not isinstance(expires_at, int) or issued_at >= expires_at or expires_at - issued_at > 60_000:
            errors.append(f"evidence {proposal_id!r} validity window is invalid")

    for proposal in evidence:
        if not isinstance(proposal, dict):
            continue
        reciprocal = [
            other for other in evidence
            if isinstance(other, dict)
            and other.get("signer_peer_id") == proposal.get("counterparty_peer_id")
            and other.get("counterparty_peer_id") == proposal.get("signer_peer_id")
        ]
        if len(reciprocal) != 1:
            errors.append(f"evidence {proposal.get('proposal_id')!r} lacks one reciprocal envelope")
            continue
        other = reciprocal[0]
        for field in ["review_request_ref", "expected_rendezvous_authority_revision", "expected_enrollment_authority_revision", "nonce_hex", "coordinator_epoch", "topology_contract_id", "issued_at_ms", "expires_at_ms"]:
            if proposal.get(field) != other.get(field):
                errors.append(f"reciprocal evidence field {field} must match")
        if {proposal.get("role"), other.get("role")} != {"group_owner", "client"}:
            errors.append("reciprocal evidence roles must be group_owner/client")

    reciprocal_pairs = {
        (item.get("signer_peer_id"), item.get("counterparty_peer_id"))
        for item in evidence if isinstance(item, dict)
    }
    peers = document.get("configured_peers")
    if not isinstance(peers, list) or len(peers) < 3:
        errors.append("configured_peers must retain the sanitized N-peer case")
        peers = []
    peer_ids = [peer.get("peer_id") for peer in peers if isinstance(peer, dict)]
    if peer_ids != sorted(peer_ids) or len(set(peer_ids)) != len(peer_ids):
        errors.append("configured peers must be unique and sorted")
    for peer in peers:
        if not isinstance(peer, dict):
            errors.append("configured peer must be an object")
            continue
        expected_fields = {"peer_id", "enrollment_proposal_id", "reciprocal_evidence_proposal_ids", "conformance_status", "advisory_only", "direct_media_eligible", "topology_authorized", "media_authorized"}
        if set(peer) != expected_fields:
            errors.append("configured peer fields must match the v1 closed shape")
        peer_id = peer.get("peer_id")
        enrollment_id = peer.get("enrollment_proposal_id")
        evidence_ids = peer.get("reciprocal_evidence_proposal_ids", [])
        independently_enrolled = (
            isinstance(enrollment_id, str)
            and enrollment_id in enrollment_by_id
            and enrollment_by_id[enrollment_id].get("peer_id") == peer_id
        )
        independently_authenticated = any(
            isinstance(evidence_id, str)
            and evidence_id in evidence_by_id
            and evidence_by_id[evidence_id].get("signer_peer_id") == peer_id
            and (
                peer_id,
                evidence_by_id[evidence_id].get("counterparty_peer_id"),
            ) in reciprocal_pairs
            and (
                evidence_by_id[evidence_id].get("counterparty_peer_id"),
                peer_id,
            ) in reciprocal_pairs
            for evidence_id in evidence_ids
        )
        expected_status = (
            "eligible_for_manifold_review"
            if independently_enrolled and independently_authenticated
            else "advisory_pending_independent_enrollment"
        )
        if peer.get("conformance_status") != expected_status:
            errors.append(f"peer {peer_id!r} conformance status exceeds its evidence")
        for field in ["advisory_only", "direct_media_eligible", "topology_authorized", "media_authorized"]:
            expected = field == "advisory_only"
            if peer.get(field) is not expected:
                errors.append(f"peer {peer_id!r} {field} must be {expected}")

    for path in _forbidden_paths(document):
        errors.append(f"forbidden private or authority field: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff")
    args = parser.parse_args()
    path = Path(args.handoff)
    errors = validate_handoff(load_json(path))
    print(json.dumps({"schema": "quest-termux-lab.peer-authority-source-handoff-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
