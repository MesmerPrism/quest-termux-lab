# Meta Quest Workflow Integration

Quest Termux Lab should be used with a broader Meta Quest device workflow.
The Termux recipes in this repository assume that live device operation is
handled by a workflow that already covers:

- shared headset and ADB coordination;
- explicit serial selection;
- APK install and launch gates;
- screenshots and logcat windows;
- capture source labeling;
- port-forward setup and cleanup;
- headset readiness after sleep or reboot;
- operator-visible prompts and protected system UI.
- explicit user authorization for WiFi ADB before Termux runs any local ADB
  install, launch, wake, logcat, or shell command.

If your agent environment supports local skills, use `meta-quest-workflow`
before running a live Quest test. If it does not, apply the same rule manually:
identify the operation class, prefer read-only probes first, preserve power and
proximity state unless the test explicitly changes it, and verify cleanup.

## Current Quest Workflow Baseline

As of the 2026-06 public workflow update, new manual Meta MCP setup examples
should use Meta VR CLI via `npx -y metavr`. Existing MQDH or editor-extension
setups may still expose the same tool family as `hzdb`; record which route and
version produced each screenshot, logcat window, Perfetto trace, or device
status result.

Horizon OS 2.x also changes what a Termux-sidecar run should record. Capture
the exact OS version and PTC/non-PTC state, then note Navigator/Home state,
restored panels, window snapping/rescale, virtual hands in Home, and privacy
indicators. These are Meta system context signals. They do not grant Termux
additional app, shell, HOME, or runtime authority.

For Unity-linked runs, the Quest workflow should verify the target project's
Meta XR SDK/Unity pin against the current public SDK line before drawing
compatibility conclusions. Meta XR SDK 203.0 raises minimum Unity support to
6000.0.66f2 for several packages, adds `XR_META_temporal_pixel_synthesis`, and
includes Meta's AI Runtime Optimizer; Spatial SDK 0.13.1 adds `EntityPath` and
`VisibilityState`.

## Division Of Responsibility

| Area | Owner |
| --- | --- |
| Device coordination, ADB, installs, launches, screenshots, logcat | Meta Quest workflow |
| Termux CLI, X11, Proot, VNC, local dashboard recipes | Quest Termux Lab |
| Outbound remote operations leases, typed command simulator, Termux agent fixtures | Quest Termux Lab |
| Cross-app questionnaire request/result IPC | Quest Questionnaire Panel |
| Quest Settings and recorder UI exploration through UIAutomator | Quest Questionnaire Panel automation example plus Meta Quest workflow evidence rules |
| Rusty Morphospace sidecar intake and Manifold handoff proposals | `rusty-quest-sidecar-mesh` |
| Raw device evidence and private artifacts | Local/private workspace, not this repo |
| Public reusable findings | Sanitized docs, schemas, and synthetic fixtures in this repo |

## Capture Labeling

For Termux/X11 desktop work, label three evidence routes separately:

- X-root evidence: direct localhost/ADB-forwarded VNC screenshots or MJPEG
  frame/status endpoints.
- Headset display evidence: ADB or headset-provider screencaps of the Quest
  panel/compositor view.
- Human observer evidence: visible browser, cast, or desktop-window captures.

Prefer direct X-root frame/status pulls for automated VNC stream evidence.
Use headset display evidence only when the question is whether the Quest panel
itself is presenting the X content.

## Practical Start

1. Confirm the headset is authorized for ADB and in a meaningful ready state.
2. Capture a baseline with model, Android version, foreground surface, and
   recovery route.
3. Run the smallest Termux recipe that answers the question.
4. Stop the sidecar process or server.
5. Remove any ADB forward.
6. Record cleanup evidence before interpreting the result.

## On-Device ADB Loop

When testing the on-device APK loop, keep the first ADB authorization step
outside this repository's authority. A host workflow, phone workflow, or the
headset's own wireless-debugging pairing UI may enable the ADB TCP endpoint.
Only after that should Termux run:

```sh
export TMPDIR="${TMPDIR:-$PREFIX/tmp}"
mkdir -p "$TMPDIR"
adb connect 127.0.0.1:5555
adb -s 127.0.0.1:5555 shell id
```

The pass condition is Android shell UID. If that gate passes, Termux may use
the approved session for bounded install, launch, status, and temporary
keep-awake tests. Record protected prompts and controller requirements as
operator-gated readiness evidence.

For install/update tests, keep artifact ownership explicit. Prefer a
Termux-private download or workspace path for APKs. If the host workflow uses
`/data/local/tmp` as a readable staging fallback, record it as external
ADB-owned lab plumbing. Do not rely on public shared storage or Termux file
drops as the product communication path.

A visible, pre-granted helper APK may be used only to ask Termux to restart the
fixed fleet-agent command after process stop. Treat success as fresh heartbeat
plus loopback ADB `uid=2000(shell)` evidence, not as WiFi ADB recovery or
managed-device authority.

## Remote Operations Relationship

The off-LAN lane should remain outbound-only and typed:

```text
operator web console
  -> authenticated controller
  -> queued command with TTL, idempotency, operator reason, and lease id
Quest Termux agent
  -> outbound poll/WebSocket
  -> local allowlist and remote-session lease check
  -> optional loopback ADB shell gate
  -> bounded result plus redacted evidence
```

This repo owns the command schemas, remote-session lease schema, simulator, and
synthetic fixtures. The Meta Quest workflow owns live headset evidence,
capture labeling, protected prompts, and ADB / Meta VR CLI / `hzdb` provider
choice. The Quest
Questionnaire Panel owns the production questionnaire IPC contract; Termux,
ADB, and UIAutomator can test or recover it but must not become part of the
normal answer channel.

The `uiautomator.run_allowlisted_scenario` command kind is the bridge between
the outbound control plane and the questionnaire panel automation APK. It
runs only configured named scenarios, with small allowlisted extras, under an
active remote-session lease and local ADB shell gate. Public results default to
redacted command summaries; raw instrumentation output, XML, screenshots,
logcat, recordings, device serials, and private package names stay in local
evidence unless a private live-run config explicitly opts in.

The current public fixtures include two safe scenario shapes:

- `settingsRecoveryProbe`, which characterizes invisible or zero-node Quest
  Settings launches through passive baselines and bounded retries;
- `systemSurfaceReachability`, which compares known Android-backed Quest
  system entry points such as current window, quick settings, notifications,
  Android settings, and the Metacam sharing panel using structural counts only.

Use the Quest Questionnaire Panel exporter to summarize either raw JSONL report
before promoting findings into public notes.
