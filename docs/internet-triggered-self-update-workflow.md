# Internet-Triggered Self-Update Workflow

This workflow is for lab or break-glass Quest fleets where each headset already
has:

- developer mode enabled;
- WiFi ADB enabled or paired by an operator-approved route;
- Termux installed with the fleet agent runtime;
- the target app already installed with the expected package name and signing
  lineage.

It answers the off-LAN trigger question by making the headset initiate all
network traffic. An external operator machine does not need to be on the same
WiFi as the headset.

## Architecture

```text
operator or CI
  -> publishes signed APK and update manifest to HTTPS artifact host
  -> queues apk.update_verified command on internet-reachable controller

Quest headset
  -> Termux fleet agent polls controller over outbound HTTPS
  -> downloads candidate APK into Termux-readable workspace
  -> verifies package, version, SHA-256, signing digest, and rollout ring
  -> checks loopback ADB gate: adb shell id == uid=2000(shell)
  -> runs adb install -r through 127.0.0.1:5555
  -> optionally launches allowlisted component and records a bounded smoke result
  -> posts command result back to controller
```

The trigger is therefore the queued command plus the agent's next outbound poll.
Do not depend on inbound ADB, LAN reachability, public device IPs, port
forwards, or the operator laptop being nearby.

## Provision Once Per Headset

1. Install Termux and required packages:

```sh
pkg update
pkg install python android-tools curl apksigner
```

2. Install the fleet agent and config into a Termux-private workspace.

3. Configure at minimum:

```json
{
  "central_url": "https://fleet.example.invalid",
  "agent_id": "quest-agent-example",
  "poll_interval_seconds": 30,
  "local_adb_enabled": true,
  "local_adb_target": "127.0.0.1:5555",
  "check_local_adb_on_heartbeat": true,
  "heartbeat_local_adb_timeout_ms": 5000,
  "adb_tmpdir": "/data/data/com.termux/files/usr/tmp"
}
```

4. Configure allowlists:

- allowed command kinds;
- allowed update package names;
- allowed signing certificate digests;
- allowed rollout rings;
- optional allowlisted launch components and logcat tags.

5. Start the agent from an operator-visible Termux session:

```sh
python scripts/termux_fleet_agent.py --config config.json
```

For unattended lab runs, use a visible Termux session, an explicit foreground
service setup, or Termux:Boot only as an operator-approved convenience. Treat
process death, Android background policy, and reboot as expected recovery
cases, not as solved fleet management.

Optional stopped-process recovery can use a normal helper APK that the operator
has launched and pre-granted `com.termux.permission.RUN_COMMAND`. The helper
must also rely on Termux's own external-command setting, such as
`allow-external-apps=true`. It can ask Termux's `RunCommandService` to run the
fixed fleet-agent starter command from Termux-private storage. It does not
create WiFi ADB authorization, does not run arbitrary shell commands, and does
not make the install authority app-owned.

## Publish An Update

1. Build the new APK.
2. Confirm package name, version code, signing certificate digest, and rollout
   ring.
3. Upload the APK to an HTTPS artifact URL.
4. Compute the APK SHA-256.
5. Queue an `apk.update_verified` command with:

```json
{
  "kind": "apk.update_verified",
  "remote_session_lease_id": "lease-synthetic-operator-001",
  "requires_local_adb_shell": true,
  "idempotency_key": "panel-0.2.0-lab",
  "payload": {
    "manifest": {
      "schema": "quest-termux-lab.apk-update-manifest.v1",
      "package_name": "org.example.panel",
      "version_code": 2,
      "version_name": "0.2.0",
      "apk_url": "https://artifacts.example.invalid/panel-0.2.0.apk",
      "sha256": "<64 hex chars>",
      "signing_cert_sha256": "<64 hex chars>",
      "rollout_ring": "lab",
      "launch_after_install": true,
      "launch_component": "org.example.panel/.MainActivity",
      "allow_downgrade": false
    }
  }
}
```

Use a unique idempotency key per target package/version/ring so reconnects and
agent restarts do not create duplicate update intent.

## Connected-Device Lab Variant

For a USB-connected headset, you can test the same polling/install state
machine without publishing a public APK. This is not the production transport:
it uses ADB reverse to make host-local services appear on device loopback.

1. Start the controller on the host:

```sh
python tools/fleet_control_plane.py serve --host 127.0.0.1 --port 8787 --log-dir runs/fleet-controller-live --quiet
```

2. Start a host-local artifact server in the APK directory:

```sh
python -m http.server 8790 --bind 127.0.0.1
```

3. Reverse both ports:

```sh
adb reverse tcp:8787 tcp:8787
adb reverse tcp:8790 tcp:8790
```

4. Set the Termux agent config:

```json
{
  "central_url": "http://127.0.0.1:8787",
  "allow_insecure_loopback_apk_urls": true,
  "local_adb_enabled": true,
  "local_adb_target": "127.0.0.1:5555",
  "check_local_adb_on_heartbeat": true,
  "heartbeat_local_adb_timeout_ms": 5000,
  "adb_tmpdir": "/data/data/com.termux/files/usr/tmp"
}
```

5. Use an APK URL such as:

```text
http://127.0.0.1:8790/app-debug.apk
```

The agent accepts loopback HTTP APK URLs only when
`allow_insecure_loopback_apk_urls` is true and the host is `127.0.0.1`,
`localhost`, or `::1`. Production update commands should keep HTTPS URLs and
should not depend on `adb reverse`.

## Observed Connected-Device Example

A connected-device lab run used the variant above with:

- controller on host loopback port `8787`;
- artifact server on host loopback port `8790`;
- `adb reverse tcp:8787 tcp:8787`;
- `adb reverse tcp:8790 tcp:8790`;
- Termux agent `poll_interval_seconds=2`;
- `check_local_adb_on_heartbeat=true`;
- a debug panel APK built with `versionCode=2`;
- target package previously installed at `versionCode=1`.

The queued `apk.update_verified` command completed in one poll cycle. The
result reported:

```text
status=completed
local_adb_shell_uid=2000
apk_sha256_verified=true
signing_cert_verified=true
apk_package_verified=true
previous_version_code=1
installed_version_code=2
install_attempted=true
launch_attempted=true
```

The command stdout contained:

```text
Performing Streamed Install
Success
Starting: Intent { cmp=<package>/.update.PanelUpdateActivity }
Status: ok
Complete
```

The bounded polling run continued after the install and produced 20 heartbeat
records over roughly 40 seconds. A follow-up one-shot heartbeat with
`check_local_adb_on_heartbeat=true` reported:

```text
central_reachable=true
local_adb.checked=true
local_adb.available=true
local_adb.shell_uid=2000
```

This proves the repeatable local state machine: while the Termux process is
alive, the headset has power/network, and the loopback WiFi ADB lease remains
valid, ordinary polling can both report update readiness and execute a queued
verified update. It does not prove reboot recovery or Termux process
resurrection.

## Observed Helper Restart Example

A second connected-device run tested the stopped-process recovery shape with
the normal helper app in `examples/termux-agent-launcher`.

Setup:

- helper package: `org.questtermuxlab.agentlauncher`;
- helper permission: `com.termux.permission.RUN_COMMAND` granted;
- Termux property: `allow-external-apps=true`;
- helper command route: Termux `RunCommandService`;
- service start: `startForegroundService()` on Android 8+;
- controller on host loopback port `8787`;
- `adb reverse tcp:8787 tcp:8787`;
- Termux agent config points to `http://127.0.0.1:8787`.

In this connected-lab variant, the helper can restart the agent even when the
host-local `adb reverse` is missing, but the controller will not receive fresh
heartbeats until the reverse is restored. Production HTTPS controller URLs do
not use this host-local reverse.

Negative result first: calling Termux's command service with `startService()`
from the helper failed with `BackgroundServiceStartNotAllowedException` on the
tested Quest OS. The helper must use `startForegroundService()` for this route.

Validated recovery sequence:

```powershell
adb shell am force-stop org.questtermuxlab.agentlauncher
adb shell am force-stop com.termux
adb shell pidof com.termux
adb shell pidof org.questtermuxlab.agentlauncher
adb shell am start -W -n org.questtermuxlab.agentlauncher/.MainActivity --ez start_agent true
```

Before launch, both package process IDs were absent and Android reported both
packages as `stopped=true`. After launch, the helper cold-started, Termux
started, and the fleet agent ran as:

```text
python termux_fleet_agent.py --config config.json
```

The controller received six fresh heartbeats in roughly 12 seconds. The latest
heartbeat reported:

```text
central_reachable=true
local_adb.checked=true
local_adb.available=true
local_adb.shell_uid=2000
local_adb.adb_target=127.0.0.1:5555
```

This proves that a normal visible helper, once installed, launched, configured,
and granted, can restart a stopped Termux fleet agent on the tested device. It
does not prove reboot autostart, restoration of WiFi ADB, device-owner
management, or silent install authority for the helper itself.

## Trigger Model

Recommended trigger:

1. Operator or CI queues the command on a controller reachable from the public
   internet over TLS.
2. The headset polls outbound on its normal internet connection.
3. The controller returns at most one queued command for that agent.
4. The agent executes only if the remote-session lease, command kind, package,
   ring, signing digest, launch component, and ADB shell gate all pass.

Acceptable future refinements:

- long polling to reduce delay without opening a headset listener;
- WebSocket or MQTT from the headset to the controller when the polling delay
  is too high;
- a visible companion app notification that asks an operator to open Termux or
  recover the agent.
- a visible/pre-granted helper Activity that asks Termux to restart the fixed
  fleet-agent process when an operator launches it.

Avoid as primary triggers:

- inbound ADB from an operator laptop;
- exposing a headset HTTP listener to the internet;
- peer devices relaying install commands;
- public shared-storage file drops;
- arbitrary remote shell commands;
- assuming push notifications can wake a Termux process reliably.

## Result States

| State | Meaning | Next action |
| --- | --- | --- |
| Fresh heartbeat, local ADB available | Agent can receive and install verified updates. | Queue the update. |
| Fresh heartbeat, local ADB unavailable | Agent is alive but cannot install silently. | Restore WiFi ADB through approved external/user route. |
| No fresh heartbeat, helper launchable | Termux agent is stopped or killed, but a pre-granted visible helper is installed and the device is reachable to the operator/user. | Launch the helper and confirm fresh heartbeat plus local ADB gate. |
| No fresh heartbeat, helper unavailable | Termux agent is stopped, offline, device is asleep/off, or the helper route is not configured. | Operator recovery, direct approved ADB recovery, or managed-device path. |
| Download/hash/signing/package check failed | Artifact or manifest is wrong or tampered with. | Do not install; publish corrected artifact. |
| Version already installed | Idempotent success or no-op. | Record completion. |
| Install failed after ADB gate | APK/package/signing/version or package-manager issue. | Inspect bounded stderr and package readback. |

The controller should surface `recovery_candidates` for agents with missing
heartbeats, stale heartbeats, or local ADB failures. Recovery is external to
the Termux agent.

## Security Rules

- Internet-exposed controllers must add authentication and authorization before
  live use. The public prototype is a schema/simulator, not a secure service.
- Any non-passive remote command must carry an active remote-session lease ID;
  only `agent.status` and `agent.capabilities` may be lease-free.
- Commands must have TTLs and idempotency keys.
- Keep command kinds explicit. Do not add a generic remote shell.
- Keep package/signing/ring/launch allowlists on the agent, not only on the
  controller.
- Keep operator web auth, agent auth, command integrity, replay protection,
  append-only audit, and revocation checks in scope before any public internet
  controller is used with real devices.
- Download into a Termux-readable workspace and verify before install.
- Set `TMPDIR` or `adb_tmpdir` to a writable Termux path before invoking ADB.
- Keep private device names, package IDs, logs, IPs, and fleet endpoints out of
  public artifacts.

## What This Does Not Solve

- It does not enable WiFi ADB after reboot.
- It does not let the Termux agent recover itself when it is not running.
- It does not make helper-based recovery boot-durable; the helper has only
  proved operator-visible restart after being launched and pre-granted.
- It does not replace Android Enterprise device owner, XR MDM, or a written
  vendor-supported fleet-management path.
- It does not make app-side self-update silent; the silent install authority is
  the active ADB shell lease.
