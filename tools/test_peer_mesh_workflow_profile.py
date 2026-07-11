import copy
import json
import unittest
from pathlib import Path

from tools import peer_mesh_workflow_profile


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSourceProfileTests(unittest.TestCase):
    def profile(self):
        return json.loads((ROOT / "examples/peer-workflow-source-profile.synthetic.json").read_text(encoding="utf-8"))

    def test_public_source_profile_passes(self):
        profile = self.profile()
        self.assertEqual(peer_mesh_workflow_profile.validate_profile(profile), [])
        topology = [artifact for artifact in profile["source_artifacts"] if artifact["role"] == "n_peer_advisory_topology"]
        self.assertEqual(len(topology), 1)
        authority = [artifact for artifact in profile["source_artifacts"] if artifact["role"] == "peer_authority_proposal_source"]
        self.assertEqual(len(authority), 1)

    def test_command_and_endpoint_fields_fail_closed(self):
        for field in ["command", "endpoint", "pairing_material", "private_device_id"]:
            damaged = copy.deepcopy(self.profile())
            damaged["source_artifacts"][0][field] = "forbidden"
            self.assertTrue(peer_mesh_workflow_profile.validate_profile(damaged), field)

    def test_profile_cannot_claim_runtime_or_add_execution_stage(self):
        damaged = self.profile()
        damaged["authority_boundary"]["runtime_authority"] = True
        damaged["compatibility"]["new_execution_stage"] = True
        self.assertTrue(peer_mesh_workflow_profile.validate_profile(damaged))

    def test_profile_cannot_drop_or_relabel_n_peer_advisory_topology(self):
        for mutation in ["drop", "relabel"]:
            damaged = copy.deepcopy(self.profile())
            if mutation == "drop":
                damaged["source_artifacts"] = damaged["source_artifacts"][:-1]
            else:
                damaged["source_artifacts"][-1]["role"] = "runtime_topology"
            self.assertTrue(peer_mesh_workflow_profile.validate_profile(damaged), mutation)


if __name__ == "__main__":
    unittest.main()
