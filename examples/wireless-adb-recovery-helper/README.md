# Wireless ADB Recovery Helper

This normal Android helper pairs or authorizes Termux once, attempts to recover
an Android 11+ TLS Wireless Debugging connection after boot, and provides an
attended **Restore Now** fallback. It is opt-in, operator-visible, and intended
for a private sideloaded developer setup.

It does not generate a pairing code, read a protected system dialog, generate
shell authority, bypass a Quest prompt, claim HOME, or expose a generic command
API. It can only:

1. write `adb_enabled=1`, `adb_wifi_enabled=1`, and
   `adb_allowed_connection_time=0` only during an attended restore after a
   one-time ADB grant of `WRITE_SECURE_SETTINGS`; the boot path reads these
   values but never changes them;
2. send one embedded recovery payload through Termux's permission-gated
   `RunCommandService`;
3. discover `_adb-tls-connect._tcp` through Android's NSD API and pass only
   that boot's dynamic port to the fixed Termux payload;
4. let Termux connect through loopback and require `uid=2000(shell)`;
5. restart the existing public fleet agent with a runtime config using
   `local_adb_discovery=tls_nsd`.

The boot recovery attempt is disabled by default. The Activity exposes explicit
pairing, enable, one-shot restore, disable-boot-attempt, and
disable-Wireless-Debugging commands. The service shows a foreground
notification while pairing or recovery runs.

The helper declares `INTERNET` solely because Android NSD requires network
access for DNS-SD discovery. It has no HTTP client, remote endpoint, listener,
or generic command surface.

## Prerequisites

- Android 13 or newer. The current Quest test lane is Android 14.
- A current Termux build with `RUN_COMMAND` stdin support (Termux `0.109` or
  newer).
- `allow-external-apps=true` in `~/.termux/termux.properties`.
- Termux packages `python` and `android-tools`.
- A one-time TLS Wireless Debugging pairing or Meta debugging authorization
  completed through an operator-visible protected surface.

For standard Android headset-local pairing:

1. Press **Open Wireless Debugging Settings**, then physically choose the
   system action that displays a pairing code. If Horizon OS does not expose
   that settings intent, open Wireless Debugging manually.
2. Keep the protected system pairing dialog open.
3. Enter its six-digit code in the helper and press **Pair Termux with
   Displayed Code**.
4. Require `termux_pairing_succeeded`; the helper sends the code to the fixed
   `adb pair` operation over stdin and never stores it.

The equivalent attended Termux command remains available for diagnostics:

```sh
pkg install python android-tools
export TMPDIR="${TMPDIR:-$PREFIX/tmp}"
mkdir -p "$TMPDIR"
adb pair 127.0.0.1:<pairing-port>
```

Accept all protected Quest/Android consent surfaces physically. Do not automate
pairing codes or protected prompt buttons. The helper discovers only the
official `_adb-tls-pairing._tcp` service while that dialog is open.

The tested Horizon OS build does not expose Android's standard pairing-code
settings Activity. It instead uses Meta's protected
`WifiDebuggingAlertActivity`. The **Always allow** choice persists the Termux
ADB key and Wi-Fi BSSID, but live reboot evidence shows that this Meta build
still requires the alert again when Wi-Fi ADB is re-enabled after reboot.

## Build

From the repo root, with the canonical Android SDK/JDK environment loaded:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass `
  -File tools\build_android_vnc_panel_viewer.ps1 `
  -ProjectRoot examples\wireless-adb-recovery-helper `
  -PackageName org.questtermuxlab.wirelessadbrecovery `
  -OutputBase wireless-adb-recovery `
  -MinSdk 33
```

Generated APKs, debug keystores, and device evidence stay ignored.

## One-Time Install And Grants

Use an already authorized, serial-scoped external ADB route:

```powershell
adb -s <serial> install -r examples\wireless-adb-recovery-helper\build\wireless-adb-recovery-debug.apk
adb -s <serial> shell pm grant org.questtermuxlab.wirelessadbrecovery android.permission.WRITE_SECURE_SETTINGS
adb -s <serial> shell pm grant org.questtermuxlab.wirelessadbrecovery com.termux.permission.RUN_COMMAND
adb -s <serial> shell pm grant org.questtermuxlab.wirelessadbrecovery android.permission.POST_NOTIFICATIONS
```

Open the Activity and press **Enable Boot Recovery Attempt + Restore**:

```powershell
adb -s <serial> shell am start -W -n org.questtermuxlab.wirelessadbrecovery/.MainActivity
```

The helper installs its embedded Python payload into:

```text
$HOME/quest-lab/wireless-adb-recovery/wireless_adb_recovery.py
```

The private runtime result is written to `status.json` beside that script. A
successful result must contain:

```text
state=available
local_adb.available=true
local_adb.shell_uid=2000
discovery_mode=tls_nsd
```

The helper also receives the bounded Termux command result through a non-exported
`PendingIntent` service. Its UI records `tls_shell_available` only when the
payload reports an accepted modern TLS discovery mode and shell UID `2000`.

The same result is projected for the Rusty Quest Fleet Agent through one
query-only ContentProvider:

```text
content://org.questtermuxlab.wirelessadbrecovery.loopbackproof/v1/loopback-adb-proof
```

The provider is protected by the signature-level
`org.questtermuxlab.wirelessadbrecovery.permission.READ_LOOPBACK_ADB_PROOF`
permission. The helper and Fleet Agent must therefore be deliberately signed
with the same deployment key. Its single row is valid for at most 60 seconds
and contains only schema, evidence revision, observation/freshness times,
modern-TLS discovery mode, listener and shell-UID facts, and a SHA-256 evidence
digest. It never exposes the dynamic endpoint, host, port, serial, stdout,
filesystem path, pairing material, command, or Fleet operation identity.

Use the same keystore for both source builds. The generic helper builder accepts
`-Keystore`; the Rusty Quest Fleet Agent builder accepts its own `-Keystore`
parameter. A differently signed Fleet Agent cannot read the provider.

The dynamic port may change and is generated into a private runtime config on
each recovery; it is not durable configuration. The helper ignores
`_adb._tcp`, and the payload never falls back to port `5555`. A direct
`tls_mdns` mode remains available for ADB builds that implement the ADB mDNS
host service, but the tested Termux package does not.

## Live Validation Status

The attended pre-reboot gate passes on the selected Android 14 Quest. The
helper and fresh outbound controller heartbeats independently reported
`local_adb.available=true`, `discovery_mode=tls_nsd`, and shell UID `2000`.

Fully unattended USB-unplugged reboot recovery does not pass on the tested
Horizon OS build:

- rewriting `adb_wifi_enabled=1` after boot launches Meta's protected Wi-Fi
  debugging alert, and the fresh heartbeat appears only after physical
  acceptance;
- leaving settings untouched avoids the alert, but Android has already reset
  the Wi-Fi ADB transport before Wi-Fi joins, so no TLS service is advertised;
- the persisted Termux key remains present and stable, so key rotation is not
  the blocker.

The installed helper therefore attempts read-only boot recovery and fails
closed when the transport is unavailable. **Restore Now** is the supported
attended fallback on this build.

### Self-Hosted Network Result

The helper also exposes bounded, operator-visible probes for two headset-owned
network topologies:

- a peerless Wi-Fi Direct group with the Quest as group owner; and
- an Android `LocalOnlyHotspot` with the Quest as hotspot owner.

Both topologies stayed active after the ordinary infrastructure Wi-Fi
connection was disconnected. This proves that the headset can host a local
network without an external access point. Neither topology passed Horizon OS's
Wireless Debugging network gate on the tested build:

- `adb_wifi_enabled` stayed at or returned to `0`;
- no corresponding live TLS listener was observed (the runtime
  `service.adb.tls.port` property is diagnostic only: it may be blank even
  when a TLS listener is live on this headset);
- Termux could not obtain `uid=2000(shell)`; and
- no protected Meta approval Activity appeared.

Android NSD can briefly return a cached `_adb-tls-connect._tcp` service from the
previous infrastructure connection. Do not count an NSD callback as recovery.
A pass requires all three of the active setting, a live TLS listener, and an
independent `adb shell id` result containing `uid=2000(shell)`.

The tested modern TLS route therefore still needs an infrastructure Wi-Fi
access point. The access point does not need internet service or a PC after the
one-time install, grants, and pairing are complete.

Use the serial-scoped runner to repeat either experiment. `Prepare` intentionally
disables Wireless Debugging, creates the selected topology, disconnects the
saved infrastructure network without forgetting it, and presses **Restore
Now**. It stops and reports `operator_action_required` if a protected Meta
approval Activity appears; accept that prompt physically before continuing.

```powershell
pwsh -NoProfile -File tools\Invoke-SelfHostedWirelessAdbProbe.ps1 `
  -Serial <quest-serial> -Mode WifiDirect -Phase Prepare

pwsh -NoProfile -File tools\Invoke-SelfHostedWirelessAdbProbe.ps1 `
  -Serial <quest-serial> -Mode WifiDirect -Phase Collect

pwsh -NoProfile -File tools\Invoke-SelfHostedWirelessAdbProbe.ps1 `
  -Serial <quest-serial> -Mode WifiDirect -Phase Cleanup
```

Substitute `LocalOnlyHotspot` for `WifiDirect` to test the SoftAP route. Always
run `Cleanup`, including after a failed preparation or collection phase. Raw
device, interface, and network evidence is written only below the ignored
`runs/self-hosted-wireless-adb` tree.

## Reboot Gate

1. Confirm the helper reports auto recovery enabled.
2. Confirm Termux can connect through the TLS service before reboot.
3. Unplug USB.
4. Reboot physically or from the already-authorized shell.
5. Do not accept a protected prompt; wait for Wi-Fi, `BOOT_COMPLETED`, helper
   recovery, and the fleet heartbeat.
6. Require a fresh heartbeat with `local_adb.available=true` and
   `local_adb.shell_uid=2000`.
7. Reconnect USB only after a timeout or failure requires diagnostics.

If Horizon OS resets Wi-Fi ADB or shows its protected alert, the unattended gate
has failed. Open the helper from its Unknown Sources tile or the Hub's
**Developer Control** button, press **Restore Now**, and accept the protected
alert physically. This remains entirely headset-local but is an attended
fallback, not automatic boot recovery.

## Revocation

- Press **Disable Boot Recovery Attempt** to leave the current debugging
  session unchanged but stop future boot attempts.
- Press **Disable Wireless Debugging** to disarm boot recovery and set
  `adb_wifi_enabled=0`; this can immediately disconnect Wi-Fi ADB.
- Forget the pairing or revoke debugging authorizations in Android settings to
  invalidate the stored Termux ADB identity.
- Uninstall the helper to remove its boot receiver and app-owned state.
