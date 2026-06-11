# Outbound Fleet Control Plane

This lane models a lightweight fleet of Quest Termux agents without requiring
a visible Linux desktop. It is for public-safe control-plane development and
simulator testing before any live headset run.

For production fleet management, pair this with
`docs/managed-device-owner-options.md`. The current recommendation is Android
Enterprise fully managed / dedicated device owner for phones. For Quest, treat
HMS-backed XR MDM as vendor-confirmed only because Meta's 2026 update stops
selling Horizon managed services and commercial Quest SKUs while continuing
support through 2030. The Termux fleet agent is a lab and break-glass plane,
not the primary 100-device management plane.

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

For headsets that have internet but are not on the same WiFi as the operator's
machine, use outbound polling as the trigger. The operator or CI queues an
`apk.update_verified` command on an HTTPS controller; the headset polls from
Termux, downloads the APK, and installs locally only after the loopback ADB
gate passes. See `docs/internet-triggered-self-update-workflow.md`.

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

Live Quest setup notes:

- Set a Termux-readable temp directory before running ADB. The public agent
  now does this for ADB subprocesses by using `adb_tmpdir`, `TMPDIR`, or
  `$PREFIX/tmp`. This avoids failures from Android builds of `adb` trying to
  write logs under `/tmp` in a non-interactive app context.
- For update fleets, set `check_local_adb_on_heartbeat=true` so ordinary
  polling heartbeats report whether the loopback ADB shell gate is currently
  available before an update command is queued.
- Download or stage the candidate APK where the Termux process can read it,
  preferably Termux-private storage. Host-pushed public shared-storage files
  may be visible to `adb shell` but still unreadable from a specific Termux
  execution context.
- Treat `/data/local/tmp` as a lab staging fallback owned by the external ADB
  workflow, not as the fleet agent's default artifact store.
- For connected-device lab tests only, `allow_insecure_loopback_apk_urls` can
  permit `http://127.0.0.1` APK URLs through `adb reverse`. Production commands
  should use HTTPS artifact URLs.

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

When the agent itself is stopped, the controller cannot cause it to self-wake.
A live Quest probe showed that a visible normal helper APK can restart Termux's
fixed fleet-agent command through `RunCommandService` after the helper is
installed, launched, granted `com.termux.permission.RUN_COMMAND`, and Termux
allows external commands. Treat that as an operator-visible recovery route and
verify it with fresh heartbeats and the local ADB shell gate. It does not
replace central direct ADB or a managed-device plane for WiFi ADB loss, reboot,
or sleeping/offline headsets.

## Live Fleet Direction

The live version should move in this order:

1. One headset, no local ADB.
2. One headset, local ADB lease after external authorization.
3. One headset, `apk.update_verified` against a private test APK and HTTPS
   manifest.
4. One headset, local ADB install/launch from a Termux-readable artifact path,
   with the agent's ADB temp directory verified.
5. One headset, visible helper restart of a stopped Termux agent, verified by
   fresh heartbeats and local ADB shell identity.
6. Three headsets with unique agent IDs and distinct rollout rings.
7. Central direct ADB recovery loop for missing/stale agents.
8. Broker and stream summaries.
9. Transport upgrade from HTTP polling to WebSocket only if needed.

Keep real fleet logs, device names, serials, package IDs, LAN addresses, and
ADB output in local evidence. Promote only synthetic examples or redacted
summaries to this repository.

## Validation

```sh
python -m py_compile tools/fleet_control_plane.py scripts/termux_fleet_agent.py tools/test_fleet_control_plane.py
python -m unittest tools.test_fleet_control_plane
python tools/check_public_boundary.py --repo-root .
```
