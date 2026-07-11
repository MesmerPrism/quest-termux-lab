# Peer Workflow Source Profile

`quest-termux-lab.peer-workflow-source-profile.v1` is the public, sanitized
source profile consumed by the Rusty Quest sidecar workflow DAG. It contributes
only `source` and `privacy` evidence. It is not a new execution stage and does
not grant runtime, command, device, or accepted-state authority.

The profile references existing synthetic peer-mesh artifacts; those artifacts,
their schemas, and their tools remain independently usable. Rusty Quest Sidecar
Mesh owns integration-DAG composition. Rusty Manifold remains the future
decision, receipt, audit, and accepted-state authority.

Validate it with:

```powershell
python tools\peer_mesh_workflow_profile.py examples\peer-workflow-source-profile.synthetic.json
python -m unittest tools.test_peer_mesh_workflow_profile
```
