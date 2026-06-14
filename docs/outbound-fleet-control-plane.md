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

The internet-facing product should be a remote operations console, not a
browser terminal. The browser talks to the controller. The controller queues
typed commands with TTLs, idempotency keys, operator identity, and an optional
remote-session lease. The headset agent continues to initiate outbound traffic,
verify the command against its local allowlists and lease state, run a bounded
action, and return redacted evidence.

Do not expose ADB, Termux listeners, VNC, or headset-local HTTP services to the
internet. Do not tunnel `127.0.0.1:5555`. Use inbound device access only for
local setup and recovery through the live Quest operations workflow.

For headsets that have internet but are not on the same WiFi as the operator's
machine, use outbound polling as the trigger. The operator or CI queues an
`apk.update_verified` command on an HTTPS controller; the headset polls from
Termux, downloads the APK, and installs locally only after the loopback ADB
gate passes. See `docs/internet-triggered-self-update-workflow.md`.

## Files

- `tools/fleet_control_plane.py`: minimal standard-library HTTP controller.
- `scripts/termux_fleet_agent.py`: outbound-only standard-library Python
  agent intended to run under Termux or a simulator.
- `scripts/mirror_commander.py`: source-side CLI for submitting typed mirror
  intents through the controller.
- `schemas/fleet-agent-manifest.schema.json`
- `schemas/fleet-agent-heartbeat.schema.json`
- `schemas/fleet-command-request.schema.json`
- `schemas/fleet-command-result.schema.json`
- `schemas/remote-session-lease.schema.json`
- `schemas/mirror-session-lease.schema.json`
- `schemas/mirror-command-intent.schema.json`
- `schemas/mirror-command-event.schema.json`
- `schemas/mirror-binding-policy.schema.json`
- `schemas/mirror-session-summary.schema.json`
- `schemas/adb-shell-lease-state.schema.json`
- `docs/mirror-protocol-boundary.md`
- `examples/session-recipe.outbound-fleet-agent.json`
- `examples/session-recipe.mirror-two-quest.json`
- `examples/fleet-agent-config.synthetic.json`
- `examples/remote-session-lease.synthetic.json`
- `examples/mirror-session-lease.synthetic.json`
- `examples/mirror-binding-policy.synthetic.json`
- `examples/mirror-command-intent.launch.synthetic.json`
- `examples/mirror-command-event.completed.synthetic.json`

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
uiautomator.run_allowlisted_scenario
media_projection.preview_request
media_projection.preview_stop
termux.agent.restart_status
adb.lease_check
adb.lease_disconnect
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
- `adb.lease_check` refreshes the configured loopback ADB target and returns a
  redacted availability summary. It is diagnostic, so it completes with an
  available/unavailable report even when local ADB is disabled or unavailable.
- `adb.lease_disconnect` disconnects only the configured target and marks the
  local ADB state unavailable when ADB is enabled. If local ADB is disabled, it
  completes with a redacted best-effort summary rather than requiring a passing
  shell gate. It is a kill-switch/recovery command, not a raw ADB client.
- `uiautomator.run_allowlisted_scenario` is the implemented bridge into the
  Quest UI automation APK. It accepts only named scenarios from
  `allowed_uiautomator_scenarios`, small allowlisted extras, an active
  remote-session lease, and a passing loopback ADB shell gate. By default it
  returns only a redacted command summary; raw instrumentation output remains
  private local evidence unless a live private config explicitly opts in.
- `termux.agent.restart_status` reports whether the current agent is alive and
  echoes configured helper-readiness fields such as fixed-helper availability,
  `RUN_COMMAND` permission observation, and Termux external-command
  observation. It cannot restart itself.
- `media_projection.preview_request` and `media_projection.preview_stop` are
  consent-gated placeholders. They reject unless a separate app-owned
  MediaProjection helper and visible active-session indicator are configured;
  the Termux agent does not fabricate or bypass MediaProjection tokens.

There is no generic remote shell command in this lane.

Minimal UIAutomator scenario config:

```json
{
  "allowed_uiautomator_scenarios": {
    "settingsRecoveryProbe": {
      "instrumentation": "io.github.mesmerprism.questquestionnaire.questuiautomation.test/androidx.test.runner.AndroidJUnitRunner",
      "allowed_extras": ["retryCount", "retryWaitMs", "dumpPassiveBaselines"],
      "default_extras": {
        "retryCount": 1,
        "retryWaitMs": 1500,
        "dumpPassiveBaselines": true
      }
    },
    "systemSurfaceReachability": {
      "instrumentation": "io.github.mesmerprism.questquestionnaire.questuiautomation.test/androidx.test.runner.AndroidJUnitRunner",
      "allowed_extras": ["surfaces", "waitAfterSurfaceMs"],
      "default_extras": {
        "surfaces": "current,quickSettings,notifications,androidSettings,metacamPanel",
        "waitAfterSurfaceMs": 1000
      }
    }
  }
}
```

Example commands:
`examples/fleet-command-request.uiautomator.synthetic.json` for the Settings
recovery probe and
`examples/fleet-command-request.uiautomator-system-surface.synthetic.json` for
the passive system-surface reachability probe.
The scenario implementation and exporter live in the Quest Questionnaire Panel
repo's `examples/quest-ui-automation` module; this repo only queues and gates
the run.

## Remote Session Lease

Any command beyond passive `agent.status` and `agent.capabilities` must carry a
`remote_session_lease_id`. The active lease object is separate and uses
`quest-termux-lab.remote-session-lease.v1`.

The lease records:

- fleet, agent, operator, purpose, creation time, and expiry;
- consent mode and active indicator requirements;
- allowed command scopes;
- whether local ADB shell is required;
- whether emergency stop/revocation is supported.

The public simulator now rejects missing lease IDs for non-passive commands at
queue time. The agent then checks whether the referenced lease is active,
unexpired, targeted at the current agent/fleet, not revoked, and scoped to the
command kind. This is still a prototype. A live internet controller must add
operator authentication, agent authentication, signed or integrity-checked
commands, replay protection, append-only audit, and revocation checks before
deployment.

The lease is a human-visible consent and audit primitive. It is not the same as
the loopback ADB shell lease. A command can have a valid remote-session lease
and still fail if `adb shell id` does not report `uid=2000(shell)`.

## Controller UI Boundary

The web client should be a controller UI with panels such as:

- fleet overview;
- lease start/revoke status;
- typed command queue;
- redacted evidence;
- recovery candidates;
- emergency stop.

Do not add a terminal textarea. Do not add raw `adb shell`, raw `input`, or
generic `termux.exec` commands. Keep `termux.exec_allowlisted` as alias-only
and prefer purpose-specific command kinds once a command has enough structure.

The controller indexes `idempotency_key` per target agent. Duplicate queued
commands are reported as duplicates rather than queued twice. Agent-side
runtime idempotency also skips a repeated completed update command while the
agent process remains alive.

## Mirror Command Lane

The mirror protocol adds a controller-mediated two-agent command path without
turning peer gossip into a command transport. The source agent submits a
`quest-termux-lab.mirror-command-intent.v1` under an active
`quest-termux-lab.mirror-session-lease.v1`. The controller validates source,
target, TTL, revocation, and allowed command kind, then converts the intent
into the existing `quest-termux-lab.fleet-command-request.v1` for the target.

The target agent treats mirror metadata as a local policy trigger. Its
`mirror_bindings` config must allow the source, lease, command kind, TTL,
visible-session state, and payload-specific fields such as launch component or
UIAutomator scenario. Controller acceptance is not enough for execution.
Mirror-derived fleet commands carry `origin: "mirror"`, `source_agent_id`,
`mirror_intent_id`, and `remote_session_lease_id`; the target rejects mirror
metadata that lacks the explicit origin marker.

Use `scripts/mirror_commander.py` for the first source-side proof:

```sh
python scripts/mirror_commander.py --config examples/mirror-commander-config.synthetic.json create-lease --lease-file examples/mirror-session-lease.synthetic.json
python scripts/mirror_commander.py --config examples/mirror-commander-config.synthetic.json status --target quest-agent-beta --no-poll
```

Start with passive `agent.status` and `agent.capabilities`, then
`adb.lease_check`, before attempting `app.launch_allowlisted` or
`uiautomator.run_allowlisted_scenario`. Do not mirror raw coordinates, raw
ADB, shell text, package installs, VNC control, or raw logcat.

The synthetic examples use long-lived fixture dates so tests remain stable.
Live remote-session and mirror leases should be short, operator-visible, and
revoked after the run.

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

## Source-Backed Constraints

These external sources support the boundaries above:

- Android ADB is a developer/debugging channel. USB debugging requires user
  authorization of the host RSA key, and wireless debugging can turn off or
  need reconnect after network changes:
  <https://developer.android.com/tools/adb>
- Termux `RUN_COMMAND` requires the caller permission and Termux's external
  command setting, and Termux warns that returned transcripts/stdout/stderr can
  expose private data:
  <https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent>
- Android foreground services are for work noticeable to the user and show a
  notification:
  <https://developer.android.com/develop/background-work/services/foreground-services>
- Android and Meta MediaProjection require user consent and a token. Meta says
  Quest uses the Android MediaProjection API for casting, live streaming, and
  screen sharing, with Horizon OS compositor-specific surface behavior:
  <https://developer.android.com/media/grow/media-projection>
  <https://developers.meta.com/horizon/documentation/native/native-media-projection/>
- WebSocket is reasonable for lower-latency browser/controller or
  agent/controller sessions when polling is too slow, but it does not replace
  command authorization or backpressure planning:
  <https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API>
- WebRTC data channels are encrypted and useful for interactive preview/control
  lanes, but they add signaling and message-size concerns:
  <https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Using_data_channels>

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
python -m py_compile tools/fleet_control_plane.py scripts/termux_fleet_agent.py scripts/mirror_commander.py tools/test_fleet_control_plane.py tools/test_mirror_protocol.py
python -m unittest tools.test_fleet_control_plane
python -m unittest tools.test_mirror_protocol
python tools/check_public_boundary.py --repo-root .
```
