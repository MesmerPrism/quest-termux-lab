# Termux Agent Launcher

This is a minimal normal-Android helper app for lab validation. It starts the
Termux fleet agent through Termux's `RunCommandService` after the user grants
`com.termux.permission.RUN_COMMAND`.

It does not create ADB authority, restore WiFi ADB, bypass Termux settings, or
run a generic shell. It only asks Termux to run one fixed starter command that
launches the public fleet-agent script from Termux-private storage.

This helper is for operator-visible recovery when the Termux app or fleet-agent
process is stopped. It is not a boot-durable management plane; WiFi ADB must
already be enabled or paired by an approved external/user route before the
agent can install updates through loopback ADB.

Build from the repo root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools\build_android_vnc_panel_viewer.ps1 `
  -ProjectRoot examples\termux-agent-launcher `
  -PackageName org.questtermuxlab.agentlauncher `
  -OutputBase termux-agent-launcher
```

Install and grant the Termux permission during a lab run:

```powershell
adb install -r examples\termux-agent-launcher\build\termux-agent-launcher-debug.apk
adb shell pm grant org.questtermuxlab.agentlauncher com.termux.permission.RUN_COMMAND
```

Launch the helper UI:

```powershell
adb shell am start -n org.questtermuxlab.agentlauncher/.MainActivity
```

For a validation-only auto-start:

```powershell
adb shell am start -n org.questtermuxlab.agentlauncher/.MainActivity --ez start_agent true
```

Termux may also require its own external-command setting, such as
`allow-external-apps=true` in Termux settings. Treat that as an operator setup
step, not as something this helper can force.

## Observed Quest Result

On a Quest 3S live lab run, the first implementation using `startService()`
failed with `BackgroundServiceStartNotAllowedException`. Switching to
`startForegroundService()` for Android 8+ allowed a visible helper Activity to
start Termux's `RunCommandService`.

The validated recovery sequence was:

1. Stop the helper and Termux packages.
2. Confirm no `com.termux` or helper process is running.
3. Confirm Android marks both packages `stopped=true`.
4. Launch:

```powershell
adb shell am start -W -n org.questtermuxlab.agentlauncher/.MainActivity --ez start_agent true
```

The helper cold-launched, restarted Termux, started
`python termux_fleet_agent.py --config config.json`, and the controller
received fresh heartbeats. The last heartbeat in that run reported:

```text
central_reachable=true
local_adb.checked=true
local_adb.available=true
local_adb.shell_uid=2000
```

This proves a normal, launched, pre-granted helper can restart a stopped Termux
agent on the tested OS build. It does not prove reboot autostart, WiFi ADB
restoration, silent install authority for the helper, or managed-device
behavior.
