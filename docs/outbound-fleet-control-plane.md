# Outbound Fleet Control Plane

This lane models a lightweight fleet of Quest Termux agents without requiring
a visible Linux desktop. It is for public-safe control-plane development and
simulator testing before any live headset run.

Recommended shape:

```text
central fleet controller
  <- outbound heartbeat from Termux agent
  -> queued allowlisted command
  <- bounded command result

central direct ADB
  -> bootstrap, privileged truth checks, and recovery only
```

The Termux agent remains a normal Android app sidecar. It does not create ADB
authorization, become Android shell, replace HOME, own broker authority, or
act as a hidden watchdog.

## Files

- `tools/fleet_control_plane.py`: minimal standard-library HTTP controller.
- `scripts/termux_fleet_agent.py`: outbound-only standard-library Python
  agent intended to run under Termux or a simulator.
- `schemas/fleet-agent-manifest.schema.json`
- `schemas/fleet-agent-heartbeat.schema.json`
- `schemas/fleet-command-request.schema.json`
- `schemas/fleet-command-result.schema.json`
- `schemas/adb-shell-lease-state.schema.json`
- `examples/session-recipe.outbound-fleet-agent.json`
- `examples/fleet-agent-config.synthetic.json`

## Simulator Run

Start the central controller:

```sh
python tools/fleet_control_plane.py serve --host 127.0.0.1 --port 8787 --log-dir runs/fleet-controller
```

Run one agent iteration against the synthetic config:

```sh
python scripts/termux_fleet_agent.py --config examples/fleet-agent-config.synthetic.json --once
```

The synthetic config disables local ADB. It can post a heartbeat and receive
commands, but it will reject ADB self-checks because local ADB is not enabled.

## Command Model

The first implementation accepts only explicit command kinds:

```text
agent.status
agent.capabilities
termux.exec_allowlisted
adb.self_check
```

`termux.exec_allowlisted` does not accept arbitrary shell text. It accepts an
alias that must be present in the agent config, such as `python_version`.

`adb.self_check` is disabled unless the config enables local ADB. Even then it
only checks an already authorized loopback target. It does not pair ADB, enable
wireless debugging, or recover ADB after reboot.

## Live Fleet Direction

The live version should move in this order:

1. One headset, no local ADB.
2. One headset, local ADB lease after external authorization.
3. Three headsets with unique agent IDs.
4. Central direct ADB recovery loop for missing/stale agents.
5. Broker and stream summaries.
6. Transport upgrade from HTTP polling to WebSocket only if needed.

Keep real fleet logs, device names, serials, package IDs, LAN addresses, and
ADB output in local evidence. Promote only synthetic examples or redacted
summaries to this repository.

## Validation

```sh
python -m py_compile tools/fleet_control_plane.py scripts/termux_fleet_agent.py tools/test_fleet_control_plane.py
python -m unittest tools.test_fleet_control_plane
python tools/check_public_boundary.py --repo-root .
```
