# Agent Notes

This repository is intended to be public.

## Rusty Morphospace Relationship

Keep this repo as a public MIT lab/reference source, not a Rusty Morphospace
core repo. Its Morphospace connection is through the Rusty Quest sidecar lane:
public-safe Termux, Termux:X11, Proot, VNC, fleet-agent, and peer-mesh
findings can inform `rusty-quest-sidecar-mesh`, which translates selected
sanitized artifacts into `rusty.quest.sidecar.*` proposals and future
Manifold-facing handoffs.

For consolidated workflow intake, export only
`quest-termux-lab.peer-workflow-source-profile.v1`. It contributes sanitized
`source` and `privacy` evidence to the sidecar DAG; it is not another execution
stage and does not replace any existing peer-mesh schema or tool. See
`docs/peer-workflow-source-profile.md`.

The profile's N-peer topology artifact is advisory evidence only. It may
describe a sanitized three-peer configured graph, but cannot elect a
coordinator, accept membership, rank a product route, authorize a direct media
lane, or mutate Manifold state.

For NET-017 peer-authority conformance, route through
`quest-termux-lab.peer-authority-source-handoff.v1` and
`docs/peer-authority-source-handoff.md`. It is a public proposal envelope only:
public keys, signatures, and provenance references are allowed; private keys,
pairing material, endpoints, commands, accepted state, coordinator decisions,
leases, and media authority are forbidden. The configured third peer remains
advisory until it has its own enrollment and reciprocal signed evidence.

Do not introduce `rusty.*` schema IDs, AGPL Morphospace ownership claims, or
runtime authority here by default. Keep this repository's schemas in the
`quest-termux-lab.*` namespace. Promote reusable lessons into Morphospace
through a separate Rusty Quest, Manifold, Lattice, Hostess, or sidecar repo
slice with its own validation.

Keep committed content portable and sanitized:

- Do not commit local filesystem paths, headset serial numbers, package IDs from
  private applications, captured screenshots, logs, pairing material, signing
  material, tokens, or device-specific run roots.
- Do not copy source from third-party projects unless the license has been
  checked and the license obligations are represented in this repository.
- Treat Termux, Termux:X11, Termux:Boot, and Proot as user-installed upstream
  dependencies. Link to upstream sources; do not vendor their APKs or source.
- Keep Quest automation bounded and operator-visible. Do not document root,
  SELinux changes, ADB authorization bypasses, hidden boot daemons, or default
  LAN VNC exposure.
- For on-device APK work, treat WiFi ADB as an explicit operator-approved shell
  lease. Termux may run an ADB client after pairing or external enablement, but
  Termux itself is not Android shell authority.
- An Accessibility foreground watchdog belongs in its own installed APK.
  Termux may build it or inspect/configure it only through an authorized ADB
  shell lease; Accessibility is not HOME interception, kiosk authority, or a
  reason to expose arbitrary secure-setting and activity-launch commands.
- Do not commit generated APKs, idsig files, debug keystores, Android platform
  jars, native libraries, dex files, package-manager output, raw logcat, or
  launch screenshots.
- Prefer schemas, runbooks, and synthetic fixtures over real device artifacts.
- For live Quest builds, installs, launches, screenshots, logcat, ADB
  forwarding, or headset-visible validation, use the public
  `meta-quest-workflow` skill/workflow first. This repository owns the
  Termux/Linux sidecar recipes; the Meta Quest workflow owns device-operation
  discipline.
- Route Meta Home event grouping, privacy-minimized Accessibility service
  configuration, background foregrounding, and fresh Spatial-task return
  guidance through `docs/accessibility-foreground-watchdogs.md` and the public
  Meta Quest workflow.

Before committing, run:

```powershell
python tools/check_public_boundary.py --repo-root .
python -m py_compile tools/capture_vnc_screenshot.py tools/stream_vnc_mjpeg.py tools/check_public_boundary.py
python -m py_compile tools/fleet_control_plane.py scripts/termux_fleet_agent.py scripts/mirror_commander.py tools/test_fleet_control_plane.py tools/test_mirror_protocol.py
python -m unittest tools.test_fleet_control_plane
python -m unittest tools.test_mirror_protocol
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
python -m py_compile tools/peer_mesh_file_drop_staging.py tools/test_peer_mesh_file_drop_staging.py
python -m unittest tools.test_peer_mesh_file_drop_staging
python tools/peer_mesh_file_drop_staging.py --manifest examples/peer-file-drop-staging-manifest.synthetic.json --artifact-root . --output examples/peer-file-drop-staging-report.synthetic.json
python -m py_compile tools/peer_mesh_file_drop_copy_dry_run.py tools/test_peer_mesh_file_drop_copy_dry_run.py
python -m unittest tools.test_peer_mesh_file_drop_copy_dry_run
python tools/peer_mesh_file_drop_copy_dry_run.py --staging-report examples/peer-file-drop-staging-report.synthetic.json --outcomes examples/peer-file-drop-copy-outcomes.synthetic.json --output examples/peer-file-drop-copy-dry-run-report.synthetic.json
python -m py_compile tools/peer_mesh_file_drop_inbox_intake.py tools/test_peer_mesh_file_drop_inbox_intake.py
python -m unittest tools.test_peer_mesh_file_drop_inbox_intake
python tools/peer_mesh_file_drop_inbox_intake.py --copy-report examples/peer-file-drop-copy-dry-run-report.synthetic.json --manifest examples/peer-file-drop-inbox-intake-manifest.synthetic.json --artifact-root . --output examples/peer-file-drop-inbox-intake-report.synthetic.json
python -m py_compile tools/peer_mesh_send_dry_run.py tools/test_peer_mesh_send_dry_run.py
python -m unittest tools.test_peer_mesh_send_dry_run
python -m py_compile tools/peer_mesh_retry_plan.py tools/test_peer_mesh_retry_plan.py
python -m unittest tools.test_peer_mesh_retry_plan
python -m py_compile tools/peer_mesh_route_health.py tools/test_peer_mesh_route_health.py
python -m unittest tools.test_peer_mesh_route_health
python -m py_compile tools/peer_mesh_topology.py tools/test_peer_mesh_topology.py
python -m unittest tools.test_peer_mesh_topology
python -m py_compile tools/peer_mesh_route_history.py tools/test_peer_mesh_route_history.py
python -m unittest tools.test_peer_mesh_route_history
python -m py_compile tools/peer_mesh_live_lab_readiness.py tools/test_peer_mesh_live_lab_readiness.py
python -m unittest tools.test_peer_mesh_live_lab_readiness
python -m py_compile tools/peer_mesh_lab_bundle.py tools/test_peer_mesh_lab_bundle.py
python -m unittest tools.test_peer_mesh_lab_bundle
python -m py_compile tools/peer_mesh_trust_gate.py tools/test_peer_mesh_trust_gate.py
python -m unittest tools.test_peer_mesh_trust_gate
python -m py_compile tools/peer_mesh_rehearsal.py tools/test_peer_mesh_rehearsal.py
python -m unittest tools.test_peer_mesh_rehearsal
python -m py_compile tools/peer_mesh_evidence_intake.py tools/test_peer_mesh_evidence_intake.py
python -m unittest tools.test_peer_mesh_evidence_intake
python -m py_compile tools/peer_mesh_cleanup_plan.py tools/test_peer_mesh_cleanup_plan.py
python -m unittest tools.test_peer_mesh_cleanup_plan
python tools/peer_mesh_cleanup_plan.py --manifest examples/peer-cleanup-plan-manifest.synthetic.json --output examples/peer-cleanup-plan-report.synthetic.json
python -m py_compile tools/peer_mesh_scorecard.py tools/test_peer_mesh_scorecard.py
python -m unittest tools.test_peer_mesh_scorecard
python -m py_compile tools/peer_mesh_scorecard_history.py tools/test_peer_mesh_scorecard_history.py
python -m unittest tools.test_peer_mesh_scorecard_history
python -m py_compile tools/peer_mesh_scorecard_regression.py tools/test_peer_mesh_scorecard_regression.py
python -m unittest tools.test_peer_mesh_scorecard_regression
python -m py_compile tools/peer_mesh_repeated_scorecard_fixture.py tools/test_peer_mesh_repeated_scorecard_fixture.py
python -m unittest tools.test_peer_mesh_repeated_scorecard_fixture
python -m py_compile tools/peer_mesh_preflight_clear_fixture.py tools/test_peer_mesh_preflight_clear_fixture.py
python -m unittest tools.test_peer_mesh_preflight_clear_fixture
python -m py_compile tools/peer_mesh_review_bundle.py tools/test_peer_mesh_review_bundle.py
python -m unittest tools.test_peer_mesh_review_bundle
python tools/peer_mesh_review_bundle.py --manifest examples/peer-review-bundle-preflight-clear-manifest.synthetic.json --artifact-root . --output examples/peer-review-bundle-preflight-clear-report.synthetic.json
python -m py_compile tools/peer_mesh_private_run_handoff.py tools/test_peer_mesh_private_run_handoff.py
python -m unittest tools.test_peer_mesh_private_run_handoff
python -m py_compile tools/peer_mesh_private_evidence_checklist.py tools/test_peer_mesh_private_evidence_checklist.py
python -m unittest tools.test_peer_mesh_private_evidence_checklist
python -m py_compile tools/peer_mesh_private_evidence_redaction.py tools/test_peer_mesh_private_evidence_redaction.py
python -m unittest tools.test_peer_mesh_private_evidence_redaction
python -m py_compile tools/peer_mesh_fixture_index.py tools/test_peer_mesh_fixture_index.py
python -m unittest tools.test_peer_mesh_fixture_index
python -m py_compile tools/peer_mesh_public_package.py tools/test_peer_mesh_public_package.py
python -m unittest tools.test_peer_mesh_public_package
python -m py_compile tools/peer_mesh_private_import_plan.py tools/test_peer_mesh_private_import_plan.py
python -m unittest tools.test_peer_mesh_private_import_plan
python -m py_compile tools/peer_mesh_private_result_placeholder.py tools/test_peer_mesh_private_result_placeholder.py
python -m unittest tools.test_peer_mesh_private_result_placeholder
python -m py_compile tools/peer_mesh_private_result_acceptance.py tools/test_peer_mesh_private_result_acceptance.py
python -m unittest tools.test_peer_mesh_private_result_acceptance
python tools/peer_mesh_workflow_profile.py examples/peer-workflow-source-profile.synthetic.json
python -m unittest tools.test_peer_mesh_workflow_profile
python tools/peer_authority_source_handoff.py examples/peer-authority-source-handoff.synthetic.json
python -m unittest tools.test_peer_authority_source_handoff
powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw tools/capture_x11_surface_metrics.ps1)) | Out-Null"
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_android_vnc_panel_viewer.ps1 -Unsigned
bash -n scripts/build-minimal-android-apk-on-device.sh scripts/wifi-adb-keepawake-watchdog.sh scripts/quest-x11-wide-prefs.sh scripts/start-quest-x11-wide.sh
```
