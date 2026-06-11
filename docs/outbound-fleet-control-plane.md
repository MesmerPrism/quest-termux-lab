# Outbound Fleet Control Plane

This lane models a lightweight fleet of Quest Termux agents without requiring
a visible Linux desktop. It is for public-safe control-plane development and
simulator testing before any live headset run.

For production fleet management, pair this with
`docs/managed-device-owner-options.md`. The current recommendation is Android
Enterprise fully managed / dedicated device owner for phones, and Meta-managed
Quest enrollment plus a Quest-capable MDM for headsets. The Termux fleet agent
is a lab and break-glass plane, not the primary 100-device management plane.

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
apk.update_verified
app.launch_allowlisted
android.foreground_snapshot
android.logcat_slice
```

`termux.exec_allowlisted` does not accept arbitrary shell text. It accepts an
alias that must be present in the agent config, such as `python_version`.

`adb.self_check` is disabled unless the config enables local ADB. Even then it
only checks an already authorized loopback target. It does not pair ADB, enable
wireless debugging, or recover ADB after reboot.

`apk.update_verified` is the first update command shape. It accepts an embedded
`quest-termux-lab.apk-update-manifest.v1` manifest with:

- package name;
- version code and version name;
- HTTPS APK URL;
- APK SHA-256 digest;
- signing certificate SHA-256 digest;
- rollout ring;
- optional allowlisted launch component.

The Termux agent rejects the command unless the package is present in
`allowed_update_packages`, the rollout ring is allowlisted for that package,
the signing certificate digest matches the configured package policy, and any
launch component is allowlisted. If local ADB is unavailable, the result reports
`central_direct_adb_recovery` instead of trying to install through another
route.

When local ADB is available, the agent downloads the APK, verifies the file
hash, checks APK package/version metadata, checks the signing certificate
digest with `apksigner`, runs `adb install -r`, reads back the installed package
version, optionally launches an allowlisted component, and reports update plus
rollback state. Rollback is reporting-only in this public lane: the agent
records the previously installed version when it can, but it does not perform
an automatic rollback unless a later private/live lane adds an explicit,
separately allowlisted rollback command.

ADB-backed commands are intentionally narrow:

- `app.launch_allowlisted` runs only `am start -W -n <allowlisted component>`.
- `android.foreground_snapshot` reads `dumpsys window` and returns only focused
  window/activity lines.
- `android.logcat_slice` reads a bounded logcat tail for an allowlisted tag.

There is no generic remote shell command in this lane.

The controller indexes `idempotency_key` per target agent. Duplicate queued
commands are reported as duplicates rather than queued twice. Agent-side
runtime idempotency also skips a repeated completed update command while the
agent process remains alive.

The controller summary includes `recovery_candidates` when an agent heartbeat
shows missing/stale local ADB or when the latest command result failed because
local ADB was unavailable. That is the handoff point for a central direct-ADB
recovery workflow owned by the live Quest operations layer.

## Live Fleet Direction

The live version should move in this order:

1. One headset, no local ADB.
2. One headset, local ADB lease after external authorization.
3. One headset, `apk.update_verified` against a private test APK and HTTPS
   manifest.
4. Three headsets with unique agent IDs and distinct rollout rings.
5. Central direct ADB recovery loop for missing/stale agents.
6. Broker and stream summaries.
7. Transport upgrade from HTTP polling to WebSocket only if needed.

Keep real fleet logs, device names, serials, package IDs, LAN addresses, and
ADB output in local evidence. Promote only synthetic examples or redacted
summaries to this repository.

## Validation

```sh
python -m py_compile tools/fleet_control_plane.py scripts/termux_fleet_agent.py tools/test_fleet_control_plane.py
python -m unittest tools.test_fleet_control_plane
python tools/check_public_boundary.py --repo-root .
```
