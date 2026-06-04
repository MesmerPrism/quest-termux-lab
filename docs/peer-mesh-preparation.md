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
- `schemas/peer-file-drop-staging-manifest.schema.json`
- `schemas/peer-file-drop-staging-report.schema.json`
- `schemas/peer-file-drop-copy-outcomes.schema.json`
- `schemas/peer-file-drop-copy-dry-run-report.schema.json`
- `schemas/peer-file-drop-inbox-intake-manifest.schema.json`
- `schemas/peer-file-drop-inbox-intake-report.schema.json`
- `schemas/peer-send-dry-run-outcomes.schema.json`
- `schemas/peer-send-dry-run-report.schema.json`
- `schemas/peer-retry-policy.schema.json`
- `schemas/peer-retry-plan.schema.json`
- `schemas/peer-route-health-report.schema.json`
- `schemas/peer-topology-manifest.schema.json`
- `schemas/peer-topology-report.schema.json`
- `schemas/peer-route-health-history.schema.json`
- `schemas/peer-live-lab-readiness-policy.schema.json`
- `schemas/peer-live-lab-readiness-report.schema.json`
- `schemas/peer-lab-bundle-manifest.schema.json`
- `schemas/peer-lab-bundle-report.schema.json`
- `schemas/peer-trust-policy.schema.json`
- `schemas/peer-trust-report.schema.json`
- `schemas/peer-rehearsal-manifest.schema.json`
- `schemas/peer-rehearsal-report.schema.json`
- `schemas/peer-cleanup-record.schema.json`
- `schemas/peer-cleanup-plan-manifest.schema.json`
- `schemas/peer-cleanup-plan-report.schema.json`
- `schemas/peer-evidence-intake-manifest.schema.json`
- `schemas/peer-evidence-intake-report.schema.json`
- `schemas/peer-scorecard-manifest.schema.json`
- `schemas/peer-scorecard-report.schema.json`
- `schemas/peer-scorecard-history.schema.json`
- `schemas/peer-scorecard-regression-policy.schema.json`
- `schemas/peer-scorecard-regression-report.schema.json`
- `schemas/peer-repeated-scorecard-fixture-manifest.schema.json`
- `schemas/peer-repeated-scorecard-fixture-report.schema.json`
- `schemas/peer-preflight-clear-fixture-manifest.schema.json`
- `schemas/peer-preflight-clear-fixture-report.schema.json`
- `schemas/peer-review-bundle-manifest.schema.json`
- `schemas/peer-review-bundle-report.schema.json`
- `schemas/peer-private-run-handoff-manifest.schema.json`
- `schemas/peer-private-run-handoff-report.schema.json`
- `schemas/peer-private-evidence-checklist-manifest.schema.json`
- `schemas/peer-private-evidence-checklist-report.schema.json`
- `schemas/peer-private-evidence-redaction-manifest.schema.json`
- `schemas/peer-private-evidence-redaction-report.schema.json`
- `schemas/peer-fixture-index-manifest.schema.json`
- `schemas/peer-fixture-index-report.schema.json`
- `schemas/peer-public-package-manifest.schema.json`
- `schemas/peer-public-package-report.schema.json`
- `schemas/peer-private-import-plan-manifest.schema.json`
- `schemas/peer-private-import-plan-report.schema.json`
- `schemas/peer-private-result-placeholder-manifest.schema.json`
- `schemas/peer-private-result-placeholder-report.schema.json`
- `schemas/peer-private-result-acceptance-manifest.schema.json`
- `schemas/peer-private-result-acceptance-report.schema.json`
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
- `examples/peer-delivery-state.file-drop.synthetic.json`
- `examples/peer-route-config.synthetic.json`
- `examples/peer-dispatch-plan.synthetic.json`
- `examples/peer-file-drop-staging-manifest.synthetic.json`
- `examples/peer-file-drop-staging-report.synthetic.json`
- `examples/peer-file-drop-copy-outcomes.synthetic.json`
- `examples/peer-file-drop-copy-dry-run-report.synthetic.json`
- `examples/peer-gossip-envelope.file-drop.synthetic.json`
- `examples/peer-file-drop-inbox-intake-manifest.synthetic.json`
- `examples/peer-file-drop-inbox-intake-report.synthetic.json`
- `examples/peer-send-dry-run-outcomes.synthetic.json`
- `examples/peer-send-dry-run-report.synthetic.json`
- `examples/peer-retry-policy.synthetic.json`
- `examples/peer-retry-plan.synthetic.json`
- `examples/peer-route-health-report.synthetic.json`
- `examples/peer-topology-manifest.synthetic.json`
- `examples/peer-topology-report.synthetic.json`
- `examples/peer-route-health-history.synthetic.json`
- `examples/peer-live-lab-readiness-policy.synthetic.json`
- `examples/peer-live-lab-readiness-report.synthetic.json`
- `examples/peer-lab-bundle-manifest.synthetic.json`
- `examples/peer-lab-bundle-report.synthetic.json`
- `examples/peer-trust-policy.synthetic.json`
- `examples/peer-trust-report.synthetic.json`
- `examples/peer-rehearsal-manifest.synthetic.json`
- `examples/peer-rehearsal-report.synthetic.json`
- `examples/peer-cleanup-record.synthetic.json`
- `examples/peer-cleanup-plan-manifest.synthetic.json`
- `examples/peer-cleanup-plan-report.synthetic.json`
- `examples/peer-evidence-intake-manifest.synthetic.json`
- `examples/peer-evidence-intake-report.synthetic.json`
- `examples/peer-scorecard-manifest.synthetic.json`
- `examples/peer-scorecard-report.synthetic.json`
- `examples/peer-scorecard-history.synthetic.json`
- `examples/peer-scorecard-regression-policy.synthetic.json`
- `examples/peer-scorecard-regression-report.synthetic.json`
- `examples/peer-repeated-scorecard-fixture-manifest.synthetic.json`
- `examples/peer-repeated-scorecard-fixture-report.synthetic.json`
- `examples/peer-scorecard-report.clear-001.synthetic.json`
- `examples/peer-scorecard-report.clear-002.synthetic.json`
- `examples/peer-scorecard-history.clear.synthetic.json`
- `examples/peer-scorecard-regression-report.clear.synthetic.json`
- `examples/peer-preflight-clear-fixture-manifest.synthetic.json`
- `examples/peer-preflight-clear-fixture-report.synthetic.json`
- `examples/peer-route-health-report.clear-001.synthetic.json`
- `examples/peer-route-health-report.clear-002.synthetic.json`
- `examples/peer-route-health-history.clear.synthetic.json`
- `examples/peer-live-lab-readiness-policy.clear.synthetic.json`
- `examples/peer-live-lab-readiness-report.clear.synthetic.json`
- `examples/peer-topology-report.clear.synthetic.json`
- `examples/peer-lab-bundle-manifest.clear.synthetic.json`
- `examples/peer-lab-bundle-report.clear.synthetic.json`
- `examples/peer-review-bundle-manifest.synthetic.json`
- `examples/peer-review-bundle-report.synthetic.json`
- `examples/peer-review-bundle-repeated-scorecard-clear-manifest.synthetic.json`
- `examples/peer-review-bundle-repeated-scorecard-clear-report.synthetic.json`
- `examples/peer-review-bundle-preflight-clear-manifest.synthetic.json`
- `examples/peer-review-bundle-preflight-clear-report.synthetic.json`
- `examples/peer-private-run-handoff-manifest.synthetic.json`
- `examples/peer-private-run-handoff-report.synthetic.json`
- `examples/peer-private-evidence-checklist-manifest.synthetic.json`
- `examples/peer-private-evidence-checklist-report.synthetic.json`
- `examples/peer-private-evidence-redaction-manifest.synthetic.json`
- `examples/peer-private-evidence-redaction-report.synthetic.json`
- `examples/peer-fixture-index-manifest.synthetic.json`
- `examples/peer-fixture-index-report.synthetic.json`
- `examples/peer-public-package-manifest.synthetic.json`
- `examples/peer-public-package-report.synthetic.json`
- `examples/peer-private-import-plan-manifest.synthetic.json`
- `examples/peer-private-import-plan-report.synthetic.json`
- `examples/peer-private-result-placeholder-manifest.synthetic.json`
- `examples/peer-private-result-placeholder-report.synthetic.json`
- `examples/peer-private-result-acceptance-manifest.synthetic.json`
- `examples/peer-private-result-acceptance-report.synthetic.json`
- `examples/peer-mesh-round-scenario.synthetic.json`
- `examples/peer-mesh-round-report.synthetic.json`
- `examples/session-recipe.peer-gossip-status-mesh.json`
- `tools/peer_mesh_gossip.py`
- `tools/peer_mesh_round.py`
- `tools/peer_mesh_http_sim.py`
- `tools/peer_mesh_delivery.py`
- `tools/peer_mesh_dispatch_plan.py`
- `tools/peer_mesh_file_drop_staging.py`
- `tools/peer_mesh_file_drop_copy_dry_run.py`
- `tools/peer_mesh_file_drop_inbox_intake.py`
- `tools/peer_mesh_send_dry_run.py`
- `tools/peer_mesh_retry_plan.py`
- `tools/peer_mesh_route_health.py`
- `tools/peer_mesh_topology.py`
- `tools/peer_mesh_route_history.py`
- `tools/peer_mesh_live_lab_readiness.py`
- `tools/peer_mesh_lab_bundle.py`
- `tools/peer_mesh_trust_gate.py`
- `tools/peer_mesh_rehearsal.py`
- `tools/peer_mesh_evidence_intake.py`
- `tools/peer_mesh_cleanup_plan.py`
- `tools/peer_mesh_scorecard.py`
- `tools/peer_mesh_scorecard_history.py`
- `tools/peer_mesh_scorecard_regression.py`
- `tools/peer_mesh_repeated_scorecard_fixture.py`
- `tools/peer_mesh_preflight_clear_fixture.py`
- `tools/peer_mesh_review_bundle.py`
- `tools/peer_mesh_private_run_handoff.py`
- `tools/peer_mesh_private_evidence_checklist.py`
- `tools/peer_mesh_private_evidence_redaction.py`
- `tools/peer_mesh_fixture_index.py`
- `tools/peer_mesh_public_package.py`
- `tools/peer_mesh_private_import_plan.py`
- `tools/peer_mesh_private_result_placeholder.py`
- `tools/peer_mesh_private_result_acceptance.py`
- `tools/test_peer_mesh_gossip.py`
- `tools/test_peer_mesh_round.py`
- `tools/test_peer_mesh_http_sim.py`
- `tools/test_peer_mesh_delivery.py`
- `tools/test_peer_mesh_dispatch_plan.py`
- `tools/test_peer_mesh_file_drop_staging.py`
- `tools/test_peer_mesh_file_drop_copy_dry_run.py`
- `tools/test_peer_mesh_file_drop_inbox_intake.py`
- `tools/test_peer_mesh_send_dry_run.py`
- `tools/test_peer_mesh_retry_plan.py`
- `tools/test_peer_mesh_route_health.py`
- `tools/test_peer_mesh_topology.py`
- `tools/test_peer_mesh_route_history.py`
- `tools/test_peer_mesh_live_lab_readiness.py`
- `tools/test_peer_mesh_lab_bundle.py`
- `tools/test_peer_mesh_trust_gate.py`
- `tools/test_peer_mesh_rehearsal.py`
- `tools/test_peer_mesh_evidence_intake.py`
- `tools/test_peer_mesh_scorecard.py`
- `tools/test_peer_mesh_scorecard_history.py`
- `tools/test_peer_mesh_scorecard_regression.py`
- `tools/test_peer_mesh_repeated_scorecard_fixture.py`
- `tools/test_peer_mesh_preflight_clear_fixture.py`
- `tools/test_peer_mesh_review_bundle.py`
- `tools/test_peer_mesh_private_run_handoff.py`
- `tools/test_peer_mesh_private_evidence_checklist.py`
- `tools/test_peer_mesh_private_evidence_redaction.py`
- `tools/test_peer_mesh_fixture_index.py`
- `tools/test_peer_mesh_public_package.py`
- `tools/test_peer_mesh_private_import_plan.py`
- `tools/test_peer_mesh_private_result_placeholder.py`
- `tools/test_peer_mesh_private_result_acceptance.py`

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

## File-Drop Staging Preparation

The file-drop staging planner consumes delivery state and configured peer
routes, reuses the dispatch planner, and produces deterministic relative inbox
filenames only for ready file-drop dispatches:

```sh
python tools/peer_mesh_file_drop_staging.py \
  --manifest examples/peer-file-drop-staging-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-file-drop-staging-report.synthetic.json
```

Staging outcomes:

```text
file_drop_staging_ready
manual_review
file_drop_staging_blocked
```

Per-entry status values:

```text
planned
skipped_non_file_drop
skipped_not_ready
```

The public fixture uses `peer-delivery-state.file-drop.synthetic.json` so the
configured `quest-agent-gamma` file-drop route becomes a ready dispatch. The
report is `file_drop_staging_ready` and contains a relative path under the
configured target inbox. It does not create that file, copy a gossip envelope,
read or embed a gossip body, open sockets, discover peers, send gossip, use
ADB, execute commands, select private endpoints, or launch apps.

## File-Drop Copy Dry Run Preparation

The file-drop copy dry run consumes a staging report plus explicit synthetic
copy outcomes, then reports what the later sender-side file-copy step would
have observed:

```sh
python tools/peer_mesh_file_drop_copy_dry_run.py \
  --staging-report examples/peer-file-drop-staging-report.synthetic.json \
  --outcomes examples/peer-file-drop-copy-outcomes.synthetic.json \
  --output examples/peer-file-drop-copy-dry-run-report.synthetic.json
```

Report outcomes:

```text
file_drop_copy_dry_run_ready
manual_review
file_drop_copy_dry_run_blocked
```

Per-action status values:

```text
simulated_copied
simulated_duplicate
simulated_missing_source
simulated_write_blocked
missing_outcome
not_planned
```

The public fixture is `file_drop_copy_dry_run_ready` because the one planned
file-drop staging entry has a matching `simulated_copied` outcome. This still
does not copy files, create inbox directories, read or embed gossip bodies,
open sockets, discover peers, send gossip, use ADB, execute commands, select
private endpoints, or launch apps. Missing synthetic outcomes, missing source
results, or write-blocked results keep the report blocked.

## File-Drop Inbox Intake Preparation

The file-drop inbox intake dry run consumes a copy dry-run report plus a
declared synthetic inbox manifest, then validates only explicitly referenced
public fixture envelopes under the artifact root:

```sh
python tools/peer_mesh_file_drop_inbox_intake.py \
  --copy-report examples/peer-file-drop-copy-dry-run-report.synthetic.json \
  --manifest examples/peer-file-drop-inbox-intake-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-file-drop-inbox-intake-report.synthetic.json
```

Report outcomes:

```text
file_drop_inbox_intake_ready
manual_review
file_drop_inbox_intake_blocked
```

Per-entry status values:

```text
accepted
duplicate_ignored
missing_file
unreadable_file
invalid_envelope
not_copied
```

The public fixture is `file_drop_inbox_intake_ready` because the one copied
file-drop action has a declared `simulated_present` inbox entry and the
referenced public fixture envelope matches the expected fleet, sender, message
ID, and gossip-only schema. This reads only the declared synthetic fixture
envelope; it does not scan inbox directories, copy files, send gossip, open
sockets, discover peers, use ADB, execute commands, select private endpoints,
or launch apps. Missing files, unreadable files, invalid envelopes, or copy
actions that were not copied keep the report blocked.

## Send Dry Run Preparation

The send dry-run simulator consumes delivery state, configured peer routes,
and synthetic delivery outcomes:

```sh
python tools/peer_mesh_send_dry_run.py \
  --route-config examples/peer-route-config.synthetic.json \
  --outcomes examples/peer-send-dry-run-outcomes.synthetic.json \
  --state-output runs/peer-send-dry-run/updated-delivery-state.json \
  --output runs/peer-send-dry-run/report.json \
  examples/peer-delivery-state.synthetic.json
```

It turns ready dispatches into simulated outcomes:

```text
accepted
duplicate
rejected
no_response
```

Non-ready dispatches are reported as:

```text
not_sent
```

The report includes the dispatch summary, action list, outcome counts, and an
updated `peer-delivery-state.v1` document. This proves the sender-side state
machine before any live send loop.

The dry run still does not:

- open sockets;
- copy files;
- discover peers;
- send gossip;
- read or embed gossip bodies;
- use ADB;
- carry command, shell, pairing, install, or launch authority.

## Retry/Backoff Preparation

The retry/backoff planner consumes delivery state and a synthetic retry
policy:

```sh
python tools/peer_mesh_retry_plan.py \
  --policy examples/peer-retry-policy.synthetic.json \
  --now 2026-06-04T10:00:01Z \
  examples/peer-delivery-state.synthetic.json
```

Retry decisions:

```text
due_now
waiting_backoff
max_attempts_reached
non_retryable_error
expired
terminal
```

The planner computes `next_attempt_at` and bounded backoff delay for pending
deliveries. It does not mutate delivery state and does not choose a route; the
dispatch planner still owns route selection, and the send dry run still owns
synthetic receipt outcomes.

This keeps retry timing explicit before a live sender exists. It is still not
a live route-health probe, peer trust model, socket sender, file copier,
discovery mechanism, command relay, ADB route, install route, or launch route.

## Route Health Preparation

The route-health report combines configured routes with synthetic sender and
retry evidence:

```sh
python tools/peer_mesh_route_health.py \
  --route-config examples/peer-route-config.synthetic.json \
  --send-report examples/peer-send-dry-run-report.synthetic.json \
  --retry-plan examples/peer-retry-plan.synthetic.json
```

Route status values:

```text
healthy
degraded
unavailable
disabled
unknown
```

The report is intentionally inference-only:

- `healthy` means a synthetic send report shows accepted or duplicate delivery,
  or a terminal accepted/duplicate state.
- `degraded` means a pending delivery is due, waiting for retry backoff, or
  had a retryable synthetic failure.
- `unavailable` means retry policy or terminal state says the route is no
  longer retryable.
- `disabled` comes only from route configuration.
- `unknown` means a configured route has no synthetic send or retry evidence.

Unconfigured send or retry evidence is counted but does not create a route.
The report does not probe peers, open sockets, copy files, discover devices,
send gossip, read or embed gossip bodies, use ADB, or carry command, shell,
pairing, install, or launch authority.

## Topology Coverage Preparation

The topology report compares an expected peer set with configured routes and
synthetic route-health evidence:

```sh
python tools/peer_mesh_topology.py \
  --manifest examples/peer-topology-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-topology-report.synthetic.json
```

Topology outcomes:

```text
topology_ready
manual_review
topology_blocked
```

Per-edge reachability states:

```text
reachable
degraded
unreachable
disabled
unknown
missing_health
missing_route
```

The public fixture is `topology_blocked`: all expected targets are configured,
but one configured route is still `unknown`, so the expected three-agent
topology is not covered. The report is an observer over declared routes and
synthetic route-health only. It does not discover peers, probe peers, open
sockets, copy files, send gossip, use ADB, execute commands, or carry command,
shell, pairing, install, or launch authority.

## Route Health History Preparation

The route-health history tool aggregates one or more synthetic route-health
reports:

```sh
python tools/peer_mesh_route_history.py \
  examples/peer-route-health-report.synthetic.json
```

History trend values:

```text
single_sample
stable
improving
worsening
mixed
```

For each route, the report records:

```text
first_status
last_status
status_counts
transition_count
last_reason
```

The history layer is useful for file-drop or outbound-controller runs that
periodically write route-health reports. It aggregates evidence only. It does
not monitor peers, keep a socket open, copy files between peers, discover
devices, send gossip, use ADB, or carry command, shell, pairing, install, or
launch authority.

## Live-Lab Readiness Preparation

The live-lab readiness report evaluates synthetic route-health history against
an explicit policy:

```sh
python tools/peer_mesh_live_lab_readiness.py \
  --policy examples/peer-live-lab-readiness-policy.synthetic.json \
  --history examples/peer-route-health-history.synthetic.json
```

Readiness outcomes:

```text
ready
manual_review
not_ready
```

The readiness gate checks only synthetic evidence:

- minimum route-health report count;
- minimum tracked route count;
- whether unavailable, unknown, disabled, or worsening routes are disallowed;
- per-route allowed latest status and trend;
- whether explicit operator approval is still required.

The public fixture is intentionally `not_ready` because one configured route is
still `unknown` and the policy requires operator review. A `ready` report only
means the synthetic evidence passes a policy with no manual gate. It still does
not approve live work, probe peers, open sockets, copy files, discover devices,
send gossip, use ADB, or carry command, shell, pairing, install, or launch
authority.

## Lab Bundle Preparation

The lab bundle report packages the synthetic preflight artifacts into one
operator-facing report:

```sh
python tools/peer_mesh_lab_bundle.py \
  --manifest examples/peer-lab-bundle-manifest.synthetic.json \
  --route-config examples/peer-route-config.synthetic.json \
  --topology-report examples/peer-topology-report.synthetic.json \
  --route-history examples/peer-route-health-history.synthetic.json \
  --readiness-report examples/peer-live-lab-readiness-report.synthetic.json
```

Bundle outcomes:

```text
synthetic_ready
manual_review
blocked
```

The checker validates:

- manifest schema, experiment scope, and public-safe relative artifact paths;
- route config schema and public-safe loopback/file-drop route shape;
- topology report schema, topology status, and fleet/source/scope match;
- route-health history schema, summary counters, and fleet/source match;
- readiness report schema, readiness status, and fleet/source/scope match;
- whether operator approval is required but not represented in the private
  workflow yet.

The public fixture is `blocked` because the topology report is
`topology_blocked` and the readiness report is `not_ready`. Even
`synthetic_ready` remains a public preflight result only. It does not approve
live work, select private LAN endpoints, probe peers, open sockets, copy
files, discover devices, send gossip, use ADB, or carry command, shell,
pairing, install, or launch authority.

## Trust Gate Preparation

The trust gate checks the configured-peer shape before a private lab decides
whether any LAN endpoint setup is worth attempting:

```sh
python tools/peer_mesh_trust_gate.py \
  --policy examples/peer-trust-policy.synthetic.json \
  --route-config examples/peer-route-config.synthetic.json \
  --lab-bundle-report examples/peer-lab-bundle-report.synthetic.json \
  --gossip-envelope examples/peer-gossip-envelope.synthetic.json
```

Trust outcomes:

```text
trusted
manual_review
untrusted
```

The trust report evaluates:

- allowed agent IDs, including the source agent and configured targets;
- allowed simulator route modes;
- required `peer-gossip-envelope.v1` message schema;
- synthetic lab bundle status;
- minimum synthetic sample envelope count;
- sample envelope participant IDs and hop TTL;
- whether operator review is still required.

The public fixture is `untrusted` because the lab bundle remains `blocked`.
Even a `trusted` report would only mean the configured synthetic evidence
matches the trust policy. It would not approve live work, select private LAN
endpoints, probe peers, open sockets, copy files, discover devices, send
gossip, use ADB, or carry command, shell, pairing, install, or launch
authority.

## Rehearsal Preparation

The rehearsal report packages the preflight status and the evidence phases a
future private run would need:

```sh
python tools/peer_mesh_rehearsal.py \
  --manifest examples/peer-rehearsal-manifest.synthetic.json \
  --lab-bundle-report examples/peer-lab-bundle-report.synthetic.json \
  --trust-report examples/peer-trust-report.synthetic.json
```

Rehearsal outcomes:

```text
rehearsal_ready
manual_review
blocked
```

The report checks:

- lab bundle schema, identity, and required status;
- trust report schema, identity, and required status;
- whether operator review is required but not represented in public evidence;
- phase readiness for bundle, trust, and operator gates;
- private-only evidence phases for endpoint selection, gossip receipts, route
  health, route history, and cleanup.

The public fixture is `blocked` because the lab bundle is `blocked` and the
trust report is `untrusted`. A `rehearsal_ready` result only means the public
synthetic preflight artifacts and manifest agree; it still does not approve
live work, select private LAN endpoints, probe peers, open sockets, copy files,
discover devices, send gossip, use ADB, or carry command, shell, pairing,
install, or launch authority.

## Evidence Intake Preparation

The evidence intake report validates the artifact set a future private run
would produce:

```sh
python tools/peer_mesh_evidence_intake.py \
  --manifest examples/peer-evidence-intake-manifest.synthetic.json
```

Evidence intake outcomes:

```text
accepted
manual_review
rejected
```

The intake report validates:

- rehearsal and trust report schema, identity, and status;
- gossip receipt schema and fleet identity;
- route-health and route-history report schema, identity, and unknown-route
  review status;
- cleanup record schema and cleanup status;
- required versus optional artifact presence;
- public-safe relative artifact paths.

The public fixture is `rejected` because the rehearsal report is `blocked`,
the trust report is `untrusted`, route health/history still contain unknown
routes, and cleanup has not started. An `accepted` intake only means the
provided evidence artifacts match the manifest. It does not replay evidence,
approve live work, select endpoints, probe peers, open sockets, copy files,
discover devices, send gossip, use ADB, or carry command, shell, pairing,
install, or launch authority.

## Cleanup Plan Preparation

The cleanup plan report declares cleanup categories a future private run needs
before live peer transport is allowed:

```sh
python tools/peer_mesh_cleanup_plan.py \
  --manifest examples/peer-cleanup-plan-manifest.synthetic.json \
  --output examples/peer-cleanup-plan-report.synthetic.json
```

Cleanup plan outcomes:

```text
cleanup_plan_ready
cleanup_plan_blocked
```

The plan checks that these required cleanup categories are declared:

- operator cleanup review;
- peer transport stopped or confirmed never started;
- ephemeral inbox cleanup;
- ephemeral outbox cleanup;
- cleanup record.

The public fixture is `cleanup_plan_ready` because all required categories are
declared with expected evidence slots. This is a pre-run declaration only. It
does not execute cleanup, inspect devices, monitor peers, probe peers, open
sockets, copy files, discover devices, send gossip, use ADB, execute commands,
or carry command, shell, pairing, install, or launch authority.

## Scorecard Preparation

The scorecard report summarizes the synthetic peer-mesh evidence stack:

```sh
python tools/peer_mesh_scorecard.py \
  --manifest examples/peer-scorecard-manifest.synthetic.json
```

Scorecard outcomes:

```text
synthetic_clear
manual_review
blocked
```

The scorecard maps each input artifact to:

```text
synthetic_clear
manual_review
blocked
missing
```

The public fixture is `blocked` because readiness, lab bundle, trust,
rehearsal, and evidence intake are still blocked or rejected, while route
health/history and cleanup require manual review. A `synthetic_clear`
scorecard only means the supplied public-safe artifacts agree; it does not
approve live work, select endpoints, replay evidence, probe peers, open
sockets, copy files, discover devices, send gossip, use ADB, or carry command,
shell, pairing, install, or launch authority.

## Scorecard History Preparation

The scorecard history report compares one or more scorecard reports in
timestamp order:

```sh
python tools/peer_mesh_scorecard_history.py \
  examples/peer-scorecard-report.synthetic.json
```

History trends:

```text
single_sample
stable
improving
worsening
mixed
```

Pressure-point deltas:

```text
observed_pressure_point
resolved
new_pressure_point
improved
regressed
persistent
```

This is a comparison surface for operator review. It does not monitor live
peers, approve live work, select endpoints, replay evidence, probe peers, open
sockets, copy files, discover devices, send gossip, use ADB, or carry command,
shell, pairing, install, or launch authority.

## Scorecard Regression Preparation

The scorecard regression report evaluates scorecard history against an explicit
policy:

```sh
python tools/peer_mesh_scorecard_regression.py \
  --policy examples/peer-scorecard-regression-policy.synthetic.json \
  --history examples/peer-scorecard-history.synthetic.json
```

Regression outcomes:

```text
regression_clear
manual_review
regression_blocked
```

The public policy fixture requires at least two scorecards and zero new,
worsening, persistent, blocked, or missing pressure points. The public history
fixture therefore remains `regression_blocked`; one blocked sample is useful
as a baseline but is not repeatability evidence.

This gate evaluates synthetic scorecard history only. It does not monitor live
peers, approve live work, select endpoints, replay evidence, probe peers, open
sockets, copy files, discover devices, send gossip, use ADB, or carry command,
shell, pairing, install, or launch authority.

## Repeated Scorecard Fixture Preparation

The repeated scorecard fixture generator creates a public-safe clear path for
the scorecard stack:

```sh
python tools/peer_mesh_repeated_scorecard_fixture.py \
  --manifest examples/peer-repeated-scorecard-fixture-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-repeated-scorecard-fixture-report.synthetic.json
```

It writes:

```text
two synthetic-clear scorecard reports
one stable synthetic-clear scorecard history
one regression-clear scorecard regression report
one fixture report
```

Fixture outcomes:

```text
fixture_ready
manual_review
fixture_blocked
```

The public fixture is `fixture_ready` because the generator deliberately
creates two synthetic-clear scorecards from a sanitized template and applies
the existing strict regression policy. This is a happy-path fixture for the
public contract. It does not prove a private live run, approve live work,
select endpoints, replay evidence, monitor peers, probe peers, open sockets,
copy files, discover devices, send gossip, use ADB, execute validation slots,
or carry command, shell, pairing, install, or launch authority.

## Preflight Clear Fixture Preparation

The preflight clear fixture generator creates a public-safe happy path for the
upstream route preflight stack:

```sh
python tools/peer_mesh_preflight_clear_fixture.py \
  --manifest examples/peer-preflight-clear-fixture-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-preflight-clear-fixture-report.synthetic.json
```

It writes:

```text
two synthetic-clear route-health reports
one stable synthetic-clear route-health history
one no-manual-gate readiness policy
one ready readiness report
one topology_ready topology report
one synthetic_ready lab bundle report
one fixture report
```

Fixture outcomes:

```text
fixture_ready
manual_review
fixture_blocked
```

The public fixture is `fixture_ready` because both configured routes are
synthetically healthy across two route-health samples, route history is stable,
readiness is `ready`, topology is `topology_ready`, and the lab bundle is
`synthetic_ready`. This is a public contract fixture only. It does not approve
live work, select private LAN endpoints, probe peers, open sockets, copy files
outside declared fixture outputs, discover devices, send gossip, use ADB,
execute validation slots, or carry command, shell, pairing, install, or launch
authority.

## Review Bundle Preparation

The review bundle report packages the sanitized peer-mesh artifact stack for
human or agent review:

```sh
python tools/peer_mesh_review_bundle.py \
  --manifest examples/peer-review-bundle-manifest.synthetic.json
```

Review outcomes:

```text
review_ready
manual_review
review_blocked
```

The report checks:

```text
json artifact presence and schema
file artifact presence
terminal status gates
```

The public review bundle is `review_blocked` because all referenced artifacts
are present, but the synthetic readiness, trust, evidence, scorecard,
scorecard-history, and regression gates are intentionally blocked. That makes
the bundle useful as a handoff surface without pretending that repeatability or
private live readiness has been proven.

The review bundle does not execute validation slots, monitor live peers,
approve live work, select endpoints, replay evidence, probe peers, open
sockets, copy files, discover devices, send gossip, use ADB, or carry command,
shell, pairing, install, or launch authority.

The repeated-scorecard clear review bundle is a second public fixture that
reviews only the generated clear scorecard path:

```sh
python tools/peer_mesh_review_bundle.py \
  --manifest examples/peer-review-bundle-repeated-scorecard-clear-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-review-bundle-repeated-scorecard-clear-report.synthetic.json
```

It can be `review_ready` because it checks the clear fixture report, the two
synthetic-clear scorecards, the stable clear history, the regression-clear
report, and the related docs/tools/schemas. This does not change the full
baseline review bundle, which remains `review_blocked` while readiness, trust,
evidence intake, and private-run gates are blocked.

The preflight clear review bundle is the matching second public fixture for the
route preflight happy path:

```sh
python tools/peer_mesh_review_bundle.py \
  --manifest examples/peer-review-bundle-preflight-clear-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-review-bundle-preflight-clear-report.synthetic.json
```

It can be `review_ready` because it checks the preflight clear fixture report,
the two healthy route-health reports, the stable clear route-health history,
the ready readiness report, the ready topology report, the synthetic-ready lab
bundle report, and the related docs/tools/schemas. This still does not change
the full baseline review bundle, which remains `review_blocked` while private
live-run evidence is absent.

## Private-Run Handoff Preparation

The private-run handoff report consumes the review bundle and declares the
private evidence slots a future live run would need:

```sh
python tools/peer_mesh_private_run_handoff.py \
  --manifest examples/peer-private-run-handoff-manifest.synthetic.json
```

Handoff outcomes:

```text
handoff_ready
manual_review
handoff_blocked
```

The public handoff fixture declares required private evidence slots for:

```text
operator approval
endpoint selection record
gossip receipts
post-run route health
cleanup record
```

The fixture is `handoff_blocked` because the review bundle is currently
`review_blocked`. The handoff report does not include private endpoint values
and does not approve live work, select endpoints, replay evidence, monitor
peers, probe peers, open sockets, copy files, discover devices, send gossip,
use ADB, execute validation slots, or carry command, shell, pairing, install,
or launch authority.

## Private Evidence Checklist Preparation

The private evidence checklist converts a sanitized handoff report into
pending evidence items for a future private run:

```sh
python tools/peer_mesh_private_evidence_checklist.py \
  --manifest examples/peer-private-evidence-checklist-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-private-evidence-checklist-report.synthetic.json
```

Checklist outcomes:

```text
checklist_ready
manual_review
checklist_blocked
```

Each private evidence item remains a public placeholder:

```text
pending_private_run
optional_pending_private_run
```

The public fixture is `checklist_blocked` because the handoff is currently
`handoff_blocked`. It still lists required pending private evidence for
operator approval, endpoint selection record, gossip receipts, post-run route
health, and cleanup, plus optional scorecard and regression evidence. It does
not collect evidence, include private endpoint values, approve live work,
select endpoints, replay evidence, monitor peers, probe peers, open sockets,
copy files, discover devices, send gossip, use ADB, execute validation slots,
or carry command, shell, pairing, install, or launch authority.

## Private Evidence Redaction Preparation

The private evidence redaction report consumes the checklist and declares which
private evidence stays private-only and which evidence kinds may later produce
a sanitized public derivative:

```sh
python tools/peer_mesh_private_evidence_redaction.py \
  --manifest examples/peer-private-evidence-redaction-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-private-evidence-redaction-report.synthetic.json
```

Redaction outcomes:

```text
redaction_ready
manual_review
redaction_blocked
```

Per-slot redaction states:

```text
private_only
ready_for_sanitized_derivative
blocked_until_private_evidence
```

The public fixture is `redaction_blocked` because the checklist is currently
`checklist_blocked`. Operator approval and endpoint selection records are
private-only; gossip receipts, route-health reports, cleanup records,
scorecards, and regression reports may only become sanitized derivatives after
a private review. The report does not read private evidence, sanitize live
artifacts, include private endpoint values, approve live work, select
endpoints, replay evidence, monitor peers, probe peers, open sockets, copy
files, discover devices, send gossip, use ADB, execute validation slots, or
carry command, shell, pairing, install, or launch authority.

## Fixture Index Preparation

The fixture index summarizes the expected public fixture landscape:

```sh
python tools/peer_mesh_fixture_index.py \
  --manifest examples/peer-fixture-index-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-fixture-index-report.synthetic.json
```

Index outcomes:

```text
fixture_index_ready
fixture_index_blocked
```

The current public fixture index is `fixture_index_ready` because each group
matches its expected state:

```text
blocked-public-baseline: blocked
clear-repeated-scorecard-fixture: ready
clear-preflight-fixture: ready
cleanup-plan-fixture: ready
file-drop-staging-fixture: ready
file-drop-copy-dry-run-fixture: ready
file-drop-inbox-intake-fixture: ready
private-handoff-placeholders: blocked
```

This is a packaging and orientation surface only. It can treat deliberately
blocked public baselines, blocked private evidence placeholders, ready
synthetic clear fixtures, the cleanup plan, the no-copy file-drop staging
fixture, the file-drop copy dry-run fixture, and the file-drop inbox intake
fixture as expected fixture states. It does not execute validation slots,
approve live work, select endpoints, collect evidence, monitor peers, probe
peers, open sockets, copy files, discover devices, send gossip, use ADB,
execute commands, or carry command, shell, pairing, install, or launch
authority.

## Public Package Preparation

The public package index checks whether the public peer-mesh preparation stack
is coherent enough for public review:

```sh
python tools/peer_mesh_public_package.py \
  --manifest examples/peer-public-package-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-public-package-report.synthetic.json
```

Package outcomes:

```text
package_ready
manual_review
package_blocked
```

The package report checks required docs, tools, tests, schemas, and examples,
then verifies expected fixture states such as:

```text
route-health baseline: blocked by an unknown configured route
route-history baseline: blocked by the latest unknown route
live-lab readiness: not_ready
topology baseline: blocked
topology-aware lab bundle: blocked
preflight clear fixture: ready
fixture index: ready
cleanup plan: ready
file-drop staging: ready
file-drop copy dry run: ready
file-drop inbox intake: ready
baseline review bundle: blocked
repeated-scorecard clear review bundle: ready
preflight clear review bundle: ready
private evidence redaction: blocked
```

It also records declared validation-slot evidence for public packaging. A
`package_ready` result means the public package is internally coherent for
review, including the fact that route-health, readiness, topology, and
lab-bundle blocks are currently expected while the synthetic clear preflight
fixture, cleanup plan, file-drop staging fixture, file-drop copy dry-run
fixture, file-drop inbox intake fixture, and both narrow clear review bundles
remain ready. It
does not prove a live fleet, private endpoint setup, private evidence
collection, or public release of private artifacts. The package report does
not execute validation slots, approve live work, select endpoints, collect
evidence, replay evidence, monitor peers, probe peers, open sockets, copy
files, discover devices, send gossip, use ADB, execute commands, or carry
command, shell, pairing, install, or launch authority.

## Private Import Plan Preparation

The private import plan consumes the public package report and private evidence
redaction report, then describes which sanitized derivatives could later be
imported after private evidence exists:

```sh
python tools/peer_mesh_private_import_plan.py \
  --manifest examples/peer-private-import-plan-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-private-import-plan-report.synthetic.json
```

Import outcomes:

```text
import_ready
manual_review
import_blocked
```

Per-slot import states:

```text
private_only
ready_for_public_derivative
blocked_until_redaction_ready
missing_derivative_schema
```

The public fixture is `import_blocked`: the public package is ready for review,
but redaction is still blocked because private evidence has not been captured
and sanitized. Operator approval and endpoint selection stay private-only;
gossip receipt, route-health, cleanup, scorecard, and regression derivatives
are blocked until redaction readiness and private sanitized derivative evidence
exist. The import plan does not read private evidence, sanitize live artifacts,
approve live work, select endpoints, collect evidence, replay evidence, monitor
peers, probe peers, open sockets, copy files, discover devices, send gossip,
use ADB, execute commands, or carry command, shell, pairing, install, or launch
authority.

## Private Result Placeholder Preparation

The private result placeholder report consumes the import plan and declares
future public result slots without reading any private evidence:

```sh
python tools/peer_mesh_private_result_placeholder.py \
  --manifest examples/peer-private-result-placeholder-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-private-result-placeholder-report.synthetic.json
```

Placeholder outcomes:

```text
result_placeholders_ready
manual_review
result_placeholders_blocked
```

Per-slot placeholder states:

```text
private_only
awaiting_sanitized_derivative_artifact
blocked_until_import_ready
blocked_missing_derivative_schema
```

The public fixture is `result_placeholders_blocked` because the import plan is
currently `import_blocked`. Private-only evidence is represented as non-public
placeholders; sanitized derivative result slots stay blocked until import
planning and redaction readiness exist. The placeholder report does not read
private evidence, sanitize live artifacts, approve live work, select endpoints,
collect evidence, replay evidence, monitor peers, probe peers, open sockets,
copy files, discover devices, send gossip, use ADB, execute commands, or carry
command, shell, pairing, install, or launch authority.

## Private Result Acceptance Preparation

The private result acceptance report consumes result placeholders and declares
whether future sanitized derivative result slots could later accept public-safe
artifacts after private review:

```sh
python tools/peer_mesh_private_result_acceptance.py \
  --manifest examples/peer-private-result-acceptance-manifest.synthetic.json \
  --artifact-root . \
  --output examples/peer-private-result-acceptance-report.synthetic.json
```

Acceptance outcomes:

```text
acceptance_ready
manual_review
acceptance_blocked
```

Per-slot acceptance states:

```text
private_only
ready_to_accept_sanitized_artifact
blocked_until_placeholders_ready
blocked_missing_derivative_schema
```

The public fixture is `acceptance_blocked` because result placeholders are
currently `result_placeholders_blocked`. Private-only evidence remains outside
public acceptance; sanitized derivative result slots stay blocked until
placeholder readiness exists. The acceptance report does not read private
evidence, import artifacts, sanitize live artifacts, approve live work, select
endpoints, collect evidence, replay evidence, monitor peers, probe peers, open
sockets, copy files, discover devices, send gossip, use ADB, execute commands,
or carry command, shell, pairing, install, or launch authority.

## Live Direction

Do this only after the outbound fleet-agent path is stable:

1. Keep the central controller as the command/audit surface.
2. Produce a topology report over expected agents, configured routes, and
   synthetic route-health before calling the mesh covered.
3. Produce a live-lab readiness report over synthetic route-health history.
4. Produce a lab bundle report that keeps all live approval outside this public
   repo.
5. Produce a trust report over configured peer IDs, route modes, and sample
   gossip before any private LAN endpoint setup.
6. Produce a rehearsal report that lists private evidence requirements before
   any private LAN endpoint setup.
7. Produce an evidence intake manifest that lists expected private-run
   artifacts before any private LAN endpoint setup.
8. Produce a cleanup plan report that declares cleanup categories and expected
   evidence slots before any private LAN endpoint setup.
9. Produce a scorecard report to summarize synthetic pressure points before
   any private LAN endpoint setup.
10. Produce a scorecard history report to compare repeated scorecards before
   treating a private experiment as repeatable.
11. Produce a scorecard regression report against an explicit policy before
   treating repeated synthetic evidence as stable.
12. Produce a repeated-scorecard fixture to keep a clear public happy path
    separate from blocked public baseline evidence.
13. Produce a preflight clear fixture to keep a clear public happy path for
    route-health, route-history, readiness, topology, and lab-bundle gates
    separate from blocked public baseline evidence.
14. Produce a repeated-scorecard clear review bundle that checks the generated
    happy-path fixture separately from the full blocked baseline.
15. Produce a preflight clear review bundle that checks the generated route
    preflight happy-path fixture separately from the full blocked baseline.
16. Produce a review bundle report before handing artifacts to a private live
    run.
17. Produce a private-run handoff report that declares required private
    evidence slots without endpoint values.
18. Produce a private evidence checklist from the handoff report without
    collecting evidence or endpoint values.
19. Produce a private evidence redaction report before any private evidence is
    translated into public derivatives.
20. Produce a fixture index that records expected blocked and ready public
    lanes before packaging or handoff review.
21. Produce a public package report before public review or commit packaging.
22. Produce a file-drop staging report for configured file-drop routes before
    any private run copies envelopes between peers.
23. Produce a file-drop copy dry-run report with synthetic outcomes before any
    private run copies envelopes between peers.
24. Produce a file-drop inbox intake report with declared synthetic envelope
    fixtures before any private run treats copied files as received gossip.
25. Produce a private import plan that waits on redaction readiness before any
    sanitized private evidence can move into public fixtures.
26. Produce private result placeholders before any sanitized private derivative
    artifact is imported into public examples.
27. Produce private result acceptance reports before any sanitized private
    derivative artifact is accepted into public examples.
28. Add local peer discovery or configured peer URLs in a private live run.
29. Send gossip-only envelopes with a short hop TTL.
30. Forward merged summaries to the central controller.
31. Treat stale peer state as advisory, not fleet truth.
32. Keep direct ADB centralized or local-loopback only. Do not add
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
python -m py_compile tools/peer_mesh_file_drop_staging.py tools/test_peer_mesh_file_drop_staging.py
python -m unittest tools.test_peer_mesh_file_drop_staging
python tools/peer_mesh_file_drop_staging.py --manifest examples/peer-file-drop-staging-manifest.synthetic.json --artifact-root . --output examples/peer-file-drop-staging-report.synthetic.json
python -m py_compile tools/peer_mesh_file_drop_copy_dry_run.py tools/test_peer_mesh_file_drop_copy_dry_run.py
python -m unittest tools.test_peer_mesh_file_drop_copy_dry_run
python tools/peer_mesh_file_drop_copy_dry_run.py --staging-report examples/peer-file-drop-staging-report.synthetic.json --outcomes examples/peer-file-drop-copy-outcomes.synthetic.json --output examples/peer-file-drop-copy-dry-run-report.synthetic.json
python -m py_compile tools/peer_mesh_file_drop_inbox_intake.py tools/test_peer_mesh_file_drop_inbox_intake.py
python -m unittest tools.test_peer_mesh_file_drop_inbox_intake
python tools/peer_mesh_file_drop_inbox_intake.py --copy-report examples/peer-file-drop-copy-dry-run-report.synthetic.json --manifest examples/peer-file-drop-inbox-intake-manifest.synthetic.json --artifact-root . --output examples/peer-file-drop-inbox-intake-report.synthetic.json
python -m py_compile tools/peer_mesh_send_dry_run.py tools/test_peer_mesh_send_dry_run.py
python -m unittest tools.test_peer_mesh_send_dry_run
python -m py_compile tools/peer_mesh_retry_plan.py tools/test_peer_mesh_retry_plan.py
python -m unittest tools.test_peer_mesh_retry_plan
python -m py_compile tools/peer_mesh_route_health.py tools/test_peer_mesh_route_health.py
python -m unittest tools.test_peer_mesh_route_health
python -m py_compile tools/peer_mesh_topology.py tools/test_peer_mesh_topology.py
python -m unittest tools.test_peer_mesh_topology
python tools/peer_mesh_topology.py --manifest examples/peer-topology-manifest.synthetic.json --artifact-root . --output examples/peer-topology-report.synthetic.json
python -m py_compile tools/peer_mesh_route_history.py tools/test_peer_mesh_route_history.py
python -m unittest tools.test_peer_mesh_route_history
python -m py_compile tools/peer_mesh_live_lab_readiness.py tools/test_peer_mesh_live_lab_readiness.py
python -m unittest tools.test_peer_mesh_live_lab_readiness
python -m py_compile tools/peer_mesh_lab_bundle.py tools/test_peer_mesh_lab_bundle.py
python -m unittest tools.test_peer_mesh_lab_bundle
python -m py_compile tools/peer_mesh_trust_gate.py tools/test_peer_mesh_trust_gate.py
python -m unittest tools.test_peer_mesh_trust_gate
python -m py_compile tools/peer_mesh_rehearsal.py tools/test_peer_mesh_rehearsal.py
python -m unittest tools.test_peer_mesh_rehearsal
python -m py_compile tools/peer_mesh_evidence_intake.py tools/test_peer_mesh_evidence_intake.py
python -m unittest tools.test_peer_mesh_evidence_intake
python -m py_compile tools/peer_mesh_cleanup_plan.py tools/test_peer_mesh_cleanup_plan.py
python -m unittest tools.test_peer_mesh_cleanup_plan
python tools/peer_mesh_cleanup_plan.py --manifest examples/peer-cleanup-plan-manifest.synthetic.json --output examples/peer-cleanup-plan-report.synthetic.json
python -m py_compile tools/peer_mesh_scorecard.py tools/test_peer_mesh_scorecard.py
python -m unittest tools.test_peer_mesh_scorecard
python -m py_compile tools/peer_mesh_scorecard_history.py tools/test_peer_mesh_scorecard_history.py
python -m unittest tools.test_peer_mesh_scorecard_history
python -m py_compile tools/peer_mesh_scorecard_regression.py tools/test_peer_mesh_scorecard_regression.py
python -m unittest tools.test_peer_mesh_scorecard_regression
python -m py_compile tools/peer_mesh_repeated_scorecard_fixture.py tools/test_peer_mesh_repeated_scorecard_fixture.py
python -m unittest tools.test_peer_mesh_repeated_scorecard_fixture
python -m py_compile tools/peer_mesh_preflight_clear_fixture.py tools/test_peer_mesh_preflight_clear_fixture.py
python -m unittest tools.test_peer_mesh_preflight_clear_fixture
python tools/peer_mesh_preflight_clear_fixture.py --manifest examples/peer-preflight-clear-fixture-manifest.synthetic.json --artifact-root . --output examples/peer-preflight-clear-fixture-report.synthetic.json
python -m py_compile tools/peer_mesh_review_bundle.py tools/test_peer_mesh_review_bundle.py
python -m unittest tools.test_peer_mesh_review_bundle
python tools/peer_mesh_review_bundle.py --manifest examples/peer-review-bundle-repeated-scorecard-clear-manifest.synthetic.json --artifact-root . --output examples/peer-review-bundle-repeated-scorecard-clear-report.synthetic.json
python tools/peer_mesh_review_bundle.py --manifest examples/peer-review-bundle-preflight-clear-manifest.synthetic.json --artifact-root . --output examples/peer-review-bundle-preflight-clear-report.synthetic.json
python -m py_compile tools/peer_mesh_private_run_handoff.py tools/test_peer_mesh_private_run_handoff.py
python -m unittest tools.test_peer_mesh_private_run_handoff
python -m py_compile tools/peer_mesh_private_evidence_checklist.py tools/test_peer_mesh_private_evidence_checklist.py
python -m unittest tools.test_peer_mesh_private_evidence_checklist
python tools/peer_mesh_private_evidence_checklist.py --manifest examples/peer-private-evidence-checklist-manifest.synthetic.json --artifact-root . --output examples/peer-private-evidence-checklist-report.synthetic.json
python -m py_compile tools/peer_mesh_private_evidence_redaction.py tools/test_peer_mesh_private_evidence_redaction.py
python -m unittest tools.test_peer_mesh_private_evidence_redaction
python tools/peer_mesh_private_evidence_redaction.py --manifest examples/peer-private-evidence-redaction-manifest.synthetic.json --artifact-root . --output examples/peer-private-evidence-redaction-report.synthetic.json
python -m py_compile tools/peer_mesh_fixture_index.py tools/test_peer_mesh_fixture_index.py
python -m unittest tools.test_peer_mesh_fixture_index
python tools/peer_mesh_fixture_index.py --manifest examples/peer-fixture-index-manifest.synthetic.json --artifact-root . --output examples/peer-fixture-index-report.synthetic.json
python -m py_compile tools/peer_mesh_public_package.py tools/test_peer_mesh_public_package.py
python -m unittest tools.test_peer_mesh_public_package
python tools/peer_mesh_public_package.py --manifest examples/peer-public-package-manifest.synthetic.json --artifact-root . --output examples/peer-public-package-report.synthetic.json
python -m py_compile tools/peer_mesh_private_import_plan.py tools/test_peer_mesh_private_import_plan.py
python -m unittest tools.test_peer_mesh_private_import_plan
python tools/peer_mesh_private_import_plan.py --manifest examples/peer-private-import-plan-manifest.synthetic.json --artifact-root . --output examples/peer-private-import-plan-report.synthetic.json
python -m py_compile tools/peer_mesh_private_result_placeholder.py tools/test_peer_mesh_private_result_placeholder.py
python -m unittest tools.test_peer_mesh_private_result_placeholder
python tools/peer_mesh_private_result_placeholder.py --manifest examples/peer-private-result-placeholder-manifest.synthetic.json --artifact-root . --output examples/peer-private-result-placeholder-report.synthetic.json
python -m py_compile tools/peer_mesh_private_result_acceptance.py tools/test_peer_mesh_private_result_acceptance.py
python -m unittest tools.test_peer_mesh_private_result_acceptance
python tools/peer_mesh_private_result_acceptance.py --manifest examples/peer-private-result-acceptance-manifest.synthetic.json --artifact-root . --output examples/peer-private-result-acceptance-report.synthetic.json
python tools/peer_mesh_gossip.py from-heartbeat --sender quest-agent-alpha --message-id gossip-from-heartbeat-alpha-001 --output - examples/fleet-agent-heartbeat.synthetic.json
python tools/peer_mesh_gossip.py summarize --observer quest-agent-alpha examples/peer-gossip-envelope.synthetic.json
python tools/peer_mesh_round.py --output runs/peer-mesh-round examples/peer-mesh-round-scenario.synthetic.json
python tools/check_public_boundary.py --repo-root .
```
