# Accessibility Foreground Watchdogs From A Termux Lab

This note records how a Quest Termux sidecar can help build, configure, and
diagnose an Accessibility-based foreground watchdog without becoming the
watchdog or its Android authority.

The watchdog is an ordinary installed Android APK with a user-enabled
`AccessibilityService`. Termux remains a normal app. It may perform the ADB
steps below only through an already authorized loopback ADB session whose
shell gate reports `uid=2000(shell)`.

For the portable Android and Horizon behavior model, use the public
`meta-quest-agent-workflow` guide
`docs/accessibility-foreground-watchdogs.md` first.

## Authority Split

| Surface | Owner |
| --- | --- |
| Accessibility service declaration and decision engine | Watchdog APK |
| Target/return component contract | Cooperating Android apps |
| Enabling or disabling the service through ADB | Operator-approved ADB shell lease |
| Termux source checkout, build tools, and local evidence orchestration | Termux sidecar |
| Meta Home, Navigator, background-launch policy, and task lifecycle | Horizon/Android |
| True kiosk or lock-task authority | Managed/device-owner platform, not this repo |

Termux app UID cannot write secure settings, launch arbitrary packages, or
read another app's logs merely because the app is installed. Do not run these
steps when the loopback ADB gate fails.

## Loopback ADB Gate

```sh
export TMPDIR="${TMPDIR:-$PREFIX/tmp}"
mkdir -p "$TMPDIR"
adb connect 127.0.0.1:5555
adb -s 127.0.0.1:5555 shell id
```

Pass condition:

```text
uid=2000(shell)
```

The ADB lease is still user/external authority. It can expire after reboot,
adbd restart, timeout, or revocation.

## Privacy-Minimized Service

The installed watchdog should request only:

- `TYPE_WINDOW_STATE_CHANGED`;
- `TYPE_WINDOWS_CHANGED`;
- generic feedback;
- zero notification batching for low-latency experiments;
- `canRetrieveWindowContent=false`.

It should never retrieve the active root, inspect event sources, read text,
identify controls, click buttons, or traverse another app's UI tree. Its logs
should contain only bounded package/class classification, event type, timing,
and decision markers.

Accessibility is not physical HOME interception. On an attended Horizon
build, the physical Meta/Home press was not delivered through
`AccessibilityService.onKeyEvent()` even though top-level Navigator and shell
window transitions were observable.

## Safe Enablement And Readback

Read the current setting first:

```sh
adb -s 127.0.0.1:5555 shell settings get secure enabled_accessibility_services
adb -s 127.0.0.1:5555 shell settings get secure accessibility_enabled
adb -s 127.0.0.1:5555 shell dumpsys accessibility
```

Merge `<package>/<service>` into the existing colon-separated component list;
do not replace other services. Then write and verify:

```sh
adb -s 127.0.0.1:5555 shell settings put secure enabled_accessibility_services '<merged-components>'
adb -s 127.0.0.1:5555 shell settings put secure accessibility_enabled 1
adb -s 127.0.0.1:5555 shell dumpsys accessibility
```

Record the before/after list, bound-service row, global enabled flag, and
whether the service survived an ordinary APK update. Treat disable/restore as
a separate explicit action. Never expose this as a generic remote command or
silently enable it from a fleet agent.

## General Meta Diagnostic Utilities

Use small, purpose-specific probes through the shell lease:

```sh
# Focused window and app
adb -s 127.0.0.1:5555 shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'

# Resolve an exported launcher front door
adb -s 127.0.0.1:5555 shell cmd package resolve-activity --brief '<package>'

# Accessibility binding and event configuration
adb -s 127.0.0.1:5555 shell dumpsys accessibility

# Bounded process/native/graphics memory evidence
adb -s 127.0.0.1:5555 shell dumpsys meminfo '<package>'

# Bounded tagged log evidence
adb -s 127.0.0.1:5555 logcat -d -v threadtime -s '<tag>:I' 'AndroidRuntime:E' '*:S'
```

`dumpsys activity activities` can help distinguish Meta shell, target, and
return tasks, but it is too heavy for tight polling. Prefer focused window
readback in loops.

On compatible Horizon builds, this internal relay can exercise a synthetic
Home transition:

```sh
adb -s 127.0.0.1:5555 shell am start \
  -a com.oculus.vrshell.intent.action.QUIT_TO_HOME \
  -n com.oculus.vrshell/.intents.AndroidIntentsRelayActivity
```

It is an internal diagnostic, not a stable public API or proof of physical
button parity. Wait until the target is actually focused before starting the
next cycle; Horizon can finish opening App Library after an immediate recovery
launch.

Do not add raw `adb shell`, arbitrary `am start`, secure-setting writes, or the
internal Home relay to an internet-facing Termux control plane. If future lab
automation needs these checks, expose named allowlisted scenarios with an
active remote-session lease, the loopback ADB gate, redacted results, and an
operator-visible enable/disable step.

## Event Burst And Escape Semantics

One Home action can produce several exact top-level class events and a later
generic Meta package tail. A reliable watchdog must:

1. group the exact burst into one Home invocation;
2. count only distinct invocations toward an escape gesture;
3. permit the late generic tail to request another target refocus;
4. prevent that tail from incrementing the escape count;
5. re-arm detection when Android accepts a target launch even if no fresh
   target Accessibility event arrives.

An attended trace used a `1.2 s` invocation debounce, a short recovery settle,
and three invocations within five seconds. These are test values, not Horizon
contracts. Preserve class/timing evidence privately and recalibrate after OS
updates.

## Background Launch And Spatial Return

An enabled Accessibility service may be allowed to start an explicit exported
activity from the background. On one Horizon build the start succeeded while
ActivityTaskManager still emitted a background-launch-hardening diagnostic.
Treat success as build-specific evidence and verify the actual focused window.

For an immersive or Spatial multi-panel return app, do not assume bringing an
old task forward restores every native panel. Repeated foreground cycles can
leave stale native/graphics state while a WebView remains visible. Prefer a
dedicated return action that lets the app finish/remove the stale task, wait a
bounded teardown interval, and create a fresh MAIN task. Require fresh scene
and panel markers, bounded memory, focus, and zero package fatals.

## Evidence And Cleanup

Quest's log buffer can discard early connect/arm markers during a verbose
spatial restart. Preserve stage snapshots or run a streaming logcat window;
do not depend on one final dump containing the entire history.

Keep public output sanitized. Record only:

- shell-gate pass/blocked state;
- service configured/bound state;
- event classes as generic Meta Navigator/shell categories;
- recovery and escape pass/blocked state;
- return app fresh-runtime pass/blocked state;
- cleanup/final armed state.

Keep raw logs, exact OS fingerprint, serial, private package/activity names,
screenshots, APKs, and local paths private.

