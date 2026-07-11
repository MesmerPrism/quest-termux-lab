import copy
import json
import unittest
from pathlib import Path

from tools import peer_authority_source_handoff


ROOT = Path(__file__).resolve().parents[1]


class PeerAuthoritySourceHandoffTests(unittest.TestCase):
    def fixture(self):
        return json.loads(
            (ROOT / "examples/peer-authority-source-handoff.synthetic.json").read_text(
                encoding="utf-8"
            )
        )

    def test_public_proposal_fixture_matches_exact_manifold_contracts(self):
        fixture = self.fixture()
        self.assertEqual(peer_authority_source_handoff.validate_handoff(fixture), [])
        self.assertEqual(
            fixture["target_contracts"],
            peer_authority_source_handoff.TARGET_CONTRACTS,
        )
        self.assertFalse(fixture["authority_boundary"]["performs_ed25519_verification"])
        self.assertTrue(all(peer["advisory_only"] for peer in fixture["configured_peers"]))

    def test_third_peer_cannot_escalate_without_independent_evidence(self):
        damaged = copy.deepcopy(self.fixture())
        gamma = damaged["configured_peers"][2]
        gamma.update(
            conformance_status="eligible_for_manifold_review",
            advisory_only=False,
            direct_media_eligible=True,
            topology_authorized=True,
            media_authorized=True,
        )
        errors = peer_authority_source_handoff.validate_handoff(damaged)
        self.assertTrue(any("exceeds its evidence" in error for error in errors))
        self.assertTrue(any("direct_media_eligible" in error for error in errors))

    def test_contract_drift_and_private_authority_fields_fail_closed(self):
        for mutation in ["contract", "private_key", "gossip_grant"]:
            damaged = copy.deepcopy(self.fixture())
            if mutation == "contract":
                damaged["target_contracts"]["enrollment_request"] += ".drift"
            else:
                damaged[mutation] = "forbidden"
            self.assertTrue(
                peer_authority_source_handoff.validate_handoff(damaged), mutation
            )

    def test_committed_schema_and_damaged_fixtures_are_executable(self):
        schema = json.loads(
            (ROOT / "schemas/peer-authority-source-handoff.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["$id"], peer_authority_source_handoff.SCHEMA)
        self.assertFalse(schema["additionalProperties"])
        damaged_paths = sorted(
            (ROOT / "examples/damaged").glob("peer-authority-source-handoff-*.json")
        )
        self.assertEqual(len(damaged_paths), 3)
        for path in damaged_paths:
            value = peer_authority_source_handoff.load_json(path)
            self.assertTrue(peer_authority_source_handoff.validate_handoff(value), path.name)


if __name__ == "__main__":
    unittest.main()
