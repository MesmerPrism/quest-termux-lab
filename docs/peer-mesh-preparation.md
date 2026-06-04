# Peer Mesh Preparation

This lane prepares a future Termux peer mesh without adding a live peer
transport yet. The first scope is gossip-only status exchange.

Recommended shape:

```text
Termux agent A -> status observation -> Termux agent B
Termux agent B -> merged status summary -> central controller, if reachable

central controller -> command queue and audit
central direct ADB -> privileged truth and recovery
```

Peer mesh messages are not commands. They do not carry shell text, ADB targets,
pairing material, APK install requests, app launch requests, or recovery
authority.

## Files

- `schemas/peer-gossip-envelope.schema.json`
- `schemas/peer-mesh-summary.schema.json`
- `schemas/peer-node-config.schema.json`
- `schemas/peer-http-node-config.schema.json`
- `schemas/peer-http-gossip-receipt.schema.json`
- `schemas/peer-http-summary.schema.json`
- `schemas/peer-delivery-state.schema.json`
- `schemas/peer-route-config.schema.json`
- `schemas/peer-dispatch-plan.schema.json`
- `schemas/peer-mesh-round-scenario.schema.json`
- `schemas/peer-mesh-round-report.schema.json`
- `examples/peer-gossip-envelope.synthetic.json`
- `examples/peer-gossip-envelope.from-heartbeat.synthetic.json`
- `examples/peer-mesh-summary.synthetic.json`
- `examples/peer-node-config.synthetic.json`
- `examples/peer-http-node-config.synthetic.json`
- `examples/peer-http-gossip-receipt.synthetic.json`
- `examples/peer-http-summary.synthetic.json`
- `examples/peer-delivery-state.synthetic.json`
- `examples/peer-delivery-state.accepted.synthetic.json`
- `examples/peer-route-config.synthetic.json`
- `examples/peer-dispatch-plan.synthetic.json`
- `examples/peer-mesh-round-scenario.synthetic.json`
- `examples/peer-mesh-round-report.synthetic.json`
- `examples/session-recipe.peer-gossip-status-mesh.json`
- `tools/peer_mesh_gossip.py`
- `tools/peer_mesh_round.py`
- `tools/peer_mesh_http_sim.py`
- `tools/peer_mesh_delivery.py`
- `tools/peer_mesh_dispatch_plan.py`
- `tools/test_peer_mesh_gossip.py`
- `tools/test_peer_mesh_round.py`
- `tools/test_peer_mesh_http_sim.py`
- `tools/test_peer_mesh_delivery.py`
- `tools/test_peer_mesh_dispatch_plan.py`

## Simulator Run

Create a gossip envelope from a fleet heartbeat:

```sh
python tools/peer_mesh_gossip.py from-heartbeat \
  --sender quest-agent-alpha \
  --message-id gossip-from-heartbeat-alpha-001 \
  --output - \
  examples/fleet-agent-heartbeat.synthetic.json
```

The conversion intentionally strips fields that should not travel through peer
gossip, such as command IDs and ADB targets. The resulting envelope carries
only compact status observations.

Merge one or more synthetic gossip envelopes:

```sh
python tools/peer_mesh_gossip.py summarize --observer quest-agent-alpha examples/peer-gossip-envelope.synthetic.json
```

Merge all envelopes in a file-drop directory:

```sh
python tools/peer_mesh_gossip.py summarize-dir \
  --observer quest-agent-alpha \
  --fleet-id synthetic-lab-fleet \
  --skip-invalid \
  runs/peer-mesh/quest-agent-alpha/inbox
```

Prepare a relayed envelope with a decremented hop TTL:

```sh
python tools/peer_mesh_gossip.py relay \
  --sender quest-agent-beta \
  --message-id gossip-beta-relay-001 \
  --output - \
  examples/peer-gossip-envelope.synthetic.json
```

Relay is still status-only. It does not relay central commands, shell text,
ADB targets, APK operations, or pairing material.

The summary contains only status fields:

```text
agent_id
status
observed_at
heard_from_agent_id
central_reachable
local_adb_available
battery_percent
last_command_status
```

## Boundary

Allowed in peer gossip:

- compact heartbeat-derived status;
- whether the peer thinks central is reachable;
- whether local ADB appears available on that same peer;
- battery, stale/alive state, and last command status;
- synthetic or redacted summary hashes.
- short hop TTLs for future controlled relay experiments.

Rejected in peer gossip:

- command IDs;
- arbitrary command payloads;
- shell text;
- ADB targets for other headsets;
- pairing codes or tokens;
- install/launch requests;
- package IDs, serials, raw LAN IPs, screenshots, or logs.

## File-Drop Preparation

`peer-node-config.synthetic.json` models a file-drop simulator:

```text
runs/peer-mesh/<agent>/inbox
runs/peer-mesh/<agent>/outbox
```

This is not a live transport. It lets tests and future dry runs copy synthetic
gossip envelopes between agent folders and verify merge, stale-state, and
forbidden-field behavior before adding sockets, discovery, or device work.

Run a full synthetic file-drop round:

```sh
python tools/peer_mesh_round.py \
  --output runs/peer-mesh-round \
  examples/peer-mesh-round-scenario.synthetic.json
```

The round simulator creates:

```text
runs/peer-mesh-round/<round-id>/<agent>/inbox
runs/peer-mesh-round/<round-id>/<agent>/outbox
runs/peer-mesh-round/<round-id>/<agent>/summary.json
runs/peer-mesh-round/<round-id>/round-report.json
```

The synthetic scenario proves a directed chain:

```text
quest-agent-alpha -> quest-agent-beta -> quest-agent-gamma
```

With one relay pass, `quest-agent-gamma` can learn alpha's status through beta
without receiving alpha's command IDs, shell text, ADB target, pairing data, or
install/launch authority.

## Loopback HTTP Preparation

The HTTP simulator models the future configured-peer receive path without
turning on live LAN peer transport:

```sh
python tools/peer_mesh_http_sim.py --config examples/peer-http-node-config.synthetic.json --quiet
```

It binds to `127.0.0.1` only in the public fixture and exposes:

```text
GET  /api/peer/v1/health
POST /api/peer/v1/gossip
GET  /api/peer/v1/summary
```

Accepted payloads:

- `quest-termux-lab.peer-gossip-envelope.v1`

Rejected payloads and routes:

- fleet heartbeats;
- central commands or command results;
- shell text;
- ADB targets or ADB commands;
- pairing material, install requests, or launch requests;
- non-loopback public simulator binding.

The summary response is a `peer-http-summary.v1` wrapper containing the plain
`peer-mesh-summary.v1` plus transport counters. This keeps the reusable peer
summary schema independent from the HTTP simulator.

The gossip POST response is a `peer-http-gossip-receipt.v1` receipt:

- first valid delivery returns `accepted` and applies observations;
- exact duplicate delivery returns `duplicate` and does not apply observations
  a second time;
- same `message_id` with different content is rejected as a replay conflict;
- `seen_message_ttl_seconds` bounds the simulator's replay cache; after expiry,
  the same `message_id` can be accepted again, while the normal gossip merge
  rules still decide whether its observations update peer state;
- invalid gossip is rejected and counted, but it never creates command,
  shell, ADB, pairing, install, or launch authority.

## Delivery State Preparation

The delivery-state simulator models sender-side progress without sending
anything:

```sh
python tools/peer_mesh_delivery.py apply-receipt \
  --receipt examples/peer-http-gossip-receipt.synthetic.json \
  --target-agent-id quest-agent-beta \
  examples/peer-delivery-state.synthetic.json
```

It tracks delivery entries through:

```text
pending
accepted
duplicate
rejected
expired
```

Useful dry-run commands:

```sh
python tools/peer_mesh_delivery.py apply-error \
  --target-agent-id quest-agent-beta \
  --message-id gossip-alpha-001 \
  --reason http_400_replay_conflict \
  examples/peer-delivery-state.synthetic.json

python tools/peer_mesh_delivery.py expire \
  --now 2026-06-04T10:05:01Z \
  examples/peer-delivery-state.synthetic.json
```

Delivery state stores message IDs, target IDs, attempts, receipt status,
expiry, and summary counts. It does not store gossip bodies, central commands,
shell text, ADB targets, pairing material, install requests, or launch
requests.

## Dispatch Plan Preparation

The dispatch-plan simulator combines delivery state with configured peer
routes and produces a no-send plan:

```sh
python tools/peer_mesh_dispatch_plan.py \
  --route-config examples/peer-route-config.synthetic.json \
  --now 2026-06-04T10:00:01Z \
  examples/peer-delivery-state.synthetic.json
```

Dispatch decisions:

```text
ready
skipped_terminal
expired
missing_route
route_disabled
```

Supported public-safe route modes:

```text
loopback_http_simulator
file_drop_simulator
disabled
```

The planner validates that public HTTP routes stay on `127.0.0.1` and that
file-drop routes stay relative. The plan can say `post_gossip` or
`copy_envelope`, but it does not perform either operation and it does not read
or embed gossip bodies.

## Live Direction

Do this only after the outbound fleet-agent path is stable:

1. Keep the central controller as the command/audit surface.
2. Add local peer discovery or configured peer URLs in a private live run.
3. Send gossip-only envelopes with a short hop TTL.
4. Forward merged summaries to the central controller.
5. Treat stale peer state as advisory, not fleet truth.
6. Keep direct ADB centralized or local-loopback only. Do not add
   cross-headset ADB.

## Validation

```sh
python -m py_compile tools/peer_mesh_gossip.py tools/test_peer_mesh_gossip.py
python -m unittest tools.test_peer_mesh_gossip
python -m py_compile tools/peer_mesh_round.py tools/test_peer_mesh_round.py
python -m unittest tools.test_peer_mesh_round
python -m py_compile tools/peer_mesh_http_sim.py tools/test_peer_mesh_http_sim.py
python -m unittest tools.test_peer_mesh_http_sim
python -m py_compile tools/peer_mesh_delivery.py tools/test_peer_mesh_delivery.py
python -m unittest tools.test_peer_mesh_delivery
python -m py_compile tools/peer_mesh_dispatch_plan.py tools/test_peer_mesh_dispatch_plan.py
python -m unittest tools.test_peer_mesh_dispatch_plan
python tools/peer_mesh_gossip.py from-heartbeat --sender quest-agent-alpha --message-id gossip-from-heartbeat-alpha-001 --output - examples/fleet-agent-heartbeat.synthetic.json
python tools/peer_mesh_gossip.py summarize --observer quest-agent-alpha examples/peer-gossip-envelope.synthetic.json
python tools/peer_mesh_round.py --output runs/peer-mesh-round examples/peer-mesh-round-scenario.synthetic.json
python tools/check_public_boundary.py --repo-root .
```
