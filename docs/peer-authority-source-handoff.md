# Peer Authority Source Handoff

`quest-termux-lab.peer-authority-source-handoff.v1` is a sanitized proposal
surface for the Rusty Quest sidecar bridge. It carries only synthetic operator
request references, public Ed25519 keys and digests, public signatures,
canonical nonce/timing/role fields, and opaque provenance references.

The handoff pins the exact Manifold v1 enrollment, signed-rendezvous,
signed-session, and direct-lane request/receipt schema identifiers. This repo
does not deserialize them as accepted Manifold state and does not perform
Ed25519 verification. Manifold remains the only owner of enrollment decisions,
current keys, nonce consumption, coordinator epochs, accepted pair/session
state, route eligibility, direct-lane leases, revocation, media authority, and
audit.

All configured peers remain advisory in this artifact. A peer may become
`eligible_for_manifold_review` only after it has its own enrollment proposal
and reciprocal signed-evidence proposal. The synthetic third peer deliberately
remains `advisory_pending_independent_enrollment`. Neither peer gossip nor a
route-health/eligibility Boolean can grant topology or media authority.

Validate the committed source and damage cases with:

```powershell
python tools\peer_authority_source_handoff.py examples\peer-authority-source-handoff.synthetic.json
python -m unittest tools.test_peer_authority_source_handoff
```
