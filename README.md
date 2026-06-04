# Quest Termux Lab

Quest Termux Lab is a public, MIT-licensed place to explore Termux, Termux:X11,
Proot, local dashboards, and localhost-only VNC as developer lab sidecars on
Meta Quest headsets.

The repository is not a replacement launcher, not a managed-device system, not
a broker/runtime authority, and not a way to bypass Android or Quest security
boundaries. It collects small, auditable recipes and data models that can later
inform downstream XR tools.

## Current Scope

- Data-only session recipe and evidence schemas.
- Synthetic examples for Termux:X11, Proot, and localhost VNC flows.
- Public-safe runbooks for capability testing and cleanup.
- Small host-side helper tools that do not require private project state.
- Localhost-only host helpers for VNC screenshots, direct stream frame pulls,
  and browser-readable MJPEG streams.
- A small Android 2D panel viewer example for showing the localhost MJPEG
  stream in a landscape Quest panel.
- Public-safe native-wide Termux:X11 preference probes, evidence schema,
  capture helper, and patch scaffolds for a possible Quest-flavored activity.
- Public-safe on-device Codex engineering runbooks and synthetic evidence
  records for treating Termux or Proot as a normal-app developer sidecar.
- Public-safe on-device APK build/install/launch guidance for an
  operator-authorized WiFi ADB loopback route.
- Public-safe outbound fleet-agent schemas, examples, and simulator tooling
  for Termux agents that report heartbeats and execute bounded allowlisted
  commands without exposing a headset listener.
- Public-safe peer-gossip preparation for future Termux agent meshes, limited
  to compact status observations, synthetic merge tests, and file-drop round
  simulation.
- Public-safe peer delivery-state modeling for future configured peers,
  limited to pending, accepted, duplicate, rejected, and expired gossip
  delivery status.
- Public-safe configured-peer dispatch planning that decides whether pending
  gossip would use loopback HTTP, file-drop, disabled, missing, expired, or
  terminal routes without sending anything.

## Current Milestone

The first landscape-desktop milestone is complete: Termux:X11 can run a
1280x720 desktop, the localhost VNC/MJPEG bridge can stream it, and the Android
viewer can show the full frame in a wide Quest panel.

This is still a proof of concept. Direct interaction currently works through
the foreground Termux:X11 panel, while the larger viewer is observation-only
and slower because it receives an MJPEG stream rather than the native X11
surface.

The first headless-sidecar milestone is also positive: a Termux-owned
localhost JSON command service can continue answering allowlisted commands
while another headset app is foregrounded. This is the more relevant route for
XR apps that need Linux tools or scripts without showing a desktop.

The current native-wide surface lane is documented in
`docs/termux-x11-native-wide-surface.md`. It tests upstream Termux:X11
preferences before any fork and keeps X-root evidence, Android activity panel
evidence, and fallback viewer evidence separate.

The first preference-only native-wide pass is partial-positive: wide X roots up
to 2560x1440 can be created, and exact 1280x720 can render a visible XFCE
desktop through the native Termux:X11 surface. The remaining blocker is
ergonomics: activity/surface alignment and manual input still need their own
gate.

The first broker-feedback sidecar pass is also positive: a Termux-owned
Python/Linux process can poll a broker-owned status/stream registry, run small
bounded processing work, and publish a low-rate diagnostic feedback event while
an XR app remains foregrounded. This keeps Termux in the processor-sidecar
role; the broker remains the stream/module authority, and high-rate media or
sensor ownership stays out of this repository's recipe scope.

The first on-device APK loop milestone is positive for a baseline smoke app:
after an external workflow enabled or paired WiFi ADB, Termux connected back to
the headset over loopback, received shell authority through that approved ADB
session, built a small Android Activity APK with source-only inputs, signed it
locally, installed it, and launched it into a visible Quest panel. This does
not yet prove a Makepad build or OpenXR rendering. See
`docs/on-device-apk-build-install-launch.md`.

A follow-up helper-app probe keeps the reboot boundary in place: a normal
installed helper can receive boot and write its own status after it has been
launched and pre-granted, but it did not restore classic WiFi ADB after reboot.
Termux-local ADB still needs an external or user-authorized ADB bootstrap
before it can connect and receive `uid=2000(shell)`.

The first outbound fleet-control-plane slice is simulator-only and public-safe:
it defines Termux agent manifests, heartbeats, command requests/results, ADB
lease-state records, a small central controller, and an outbound-only Python
agent. It does not touch ADB or a headset unless a later live run explicitly
enables local ADB in the agent config. See
`docs/outbound-fleet-control-plane.md`.

The first peer-mesh slice is also simulator-only: it defines gossip envelopes,
peer summaries, a merge tool, and tests for stale-state and forbidden-message
handling. It does not open peer sockets, relay commands, or use cross-headset
ADB. See `docs/peer-mesh-preparation.md`.

The peer-mesh simulator can now derive a gossip envelope from a fleet
heartbeat, merge file-drop inbox directories, and prepare TTL-limited relay
envelopes while stripping or rejecting command-like, shell-like, credential,
and ADB-target fields.

The peer-mesh round simulator adds a dry-run harness for multiple synthetic
Termux agents. It creates per-peer inbox/outbox folders, delivers configured
status gossip links, performs bounded TTL relay passes, and writes per-peer
summaries plus a round report. It still does not open peer sockets, discover
devices, run shell commands, use ADB, or relay central commands.

The peer HTTP simulator adds the next transport-shaped dry run: a
loopback-only HTTP endpoint that accepts `peer-gossip-envelope.v1` messages and
returns an HTTP summary wrapper. It rejects heartbeats, command routes, shell
fields, ADB targets, pairing material, install/launch operations, and
non-loopback binding in the public fixture. It also returns explicit gossip
receipts, treats exact duplicate message IDs as idempotent, and rejects same-ID
content changes as replay conflicts inside a bounded replay window.

The peer delivery-state simulator adds the sender-side dry run: it tracks
pending gossip deliveries, applies HTTP receipts, records duplicate or rejected
outcomes, and expires undelivered entries. It stores message IDs and delivery
status only; it does not store gossip bodies, commands, shell text, ADB
targets, pairing material, install requests, or launch requests.

The peer dispatch-plan simulator adds the next sender-side step: it combines
delivery state with configured peer routes and produces a no-send plan. A
pending delivery can become ready for loopback HTTP or relative file-drop, or
be marked as expired, skipped terminal, route disabled, or missing route.

## Workflow Pairing

Use this repository for Termux/Linux sidecar recipes and sanitized evidence
models. For live headset work, use the public `meta-quest-workflow` skill or
the equivalent team workflow before touching ADB, installing APKs, launching
apps, taking screenshots, collecting logcat, forwarding ports, or relying on
headset-visible state.

The split is intentional:

- `meta-quest-workflow`: device-operation discipline, provider choice,
  readiness checks, capture semantics, and cleanup gates.
- `quest-termux-lab`: Termux, Termux:X11, Proot, local dashboard, and VNC
  sidecar recipes that remain normal Android app workflows.

## Non-Goals

- No root, Magisk, bootloader unlock, SELinux changes, or device-owner policy.
- No ADB authorization bypasses or hidden pairing material.
- No APK vendoring.
- No default LAN VNC, SSHD, or persistent remote shell.
- No hidden boot daemon assumptions.
- No high-rate media or XR runtime payload routing through command/control JSON.

## Upstream Projects

Install Termux-family components from their upstream projects and follow their
licenses:

- Termux: https://github.com/termux/termux-app
- Termux:X11: https://github.com/termux/termux-x11
- Termux:Boot: https://github.com/termux/termux-boot
- Proot-Distro: https://github.com/termux/proot-distro

This repository's original code and documentation are MIT licensed. Upstream
Termux-family projects have their own licenses; do not copy their code into
this repository unless license obligations are reviewed.

## Recommended Test Order

0. Activate the Meta Quest workflow for live headset operations and reserve or
   coordinate any shared device, ADB, build, capture, or port resources through
   your team's normal process.
1. Baseline: record device model, Android version, focused surface, package
   state, and recovery route.
2. Termux CLI: verify app UID, package updates, bounded child processes, and
   cleanup.
3. Termux:X11: start a minimal X server and one small client.
4. Native-wide Termux:X11: apply the preference-only probe and capture X-root
   evidence separately from Android activity panel evidence.
5. Proot: run a CLI smoke test, then one small GUI client only after X11 is
   visible and stoppable.
6. Local dashboard: bind to device localhost and consume through an explicit
   host forward.
7. VNC: keep it localhost-only or ADB-forwarded, record direct screenshot or
   live stream endpoint evidence, then stop it.
8. Broker feedback sidecar: poll a broker-owned status/registry surface and
   publish bounded diagnostic feedback through an explicit broker route.
9. Outbound fleet agent: prove simulator heartbeats, command polling, bounded
   results, and no inbound listener before any live multi-headset run.
10. Peer gossip mesh: prove synthetic status merge and forbidden-command
    rejection before adding any peer network transport.
11. Peer HTTP simulator: prove a loopback-only gossip receive/summarize route
    before any configured LAN peer experiment.
12. Peer delivery state: prove pending, accepted, duplicate, rejected, and
    expired delivery outcomes before any live send loop.
13. Peer dispatch plan: prove configured route selection and no-send planning
    before any live send loop.
14. On-device Codex engineering: prove the CLI, sandbox behavior, small public
   repo edits, validation, and patch review before any build or deploy lane.
15. On-device APK loop: use an operator-authorized WiFi ADB endpoint to build,
   sign, install, and launch a source-only smoke APK from Termux.
16. Reboot ADB recovery: treat Termux:Boot and pre-granted normal helpers as
   status probes only unless the target OS proves an official user-authorized
   wireless-debugging route.
17. Boot, wake-lock, desktop environments, audio, and graphics acceleration:
   treat each as a separate high-risk gate.

## Validation

```powershell
python tools/check_public_boundary.py --repo-root .
python -m py_compile tools/capture_vnc_screenshot.py tools/stream_vnc_mjpeg.py tools/check_public_boundary.py
python -m py_compile tools/fleet_control_plane.py scripts/termux_fleet_agent.py tools/test_fleet_control_plane.py
python -m unittest tools.test_fleet_control_plane
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
powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw tools\capture_x11_surface_metrics.ps1)) | Out-Null"
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_android_vnc_panel_viewer.ps1 -Unsigned
bash -n scripts/build-minimal-android-apk-on-device.sh scripts/wifi-adb-keepawake-watchdog.sh scripts/quest-x11-wide-prefs.sh scripts/start-quest-x11-wide.sh
```
