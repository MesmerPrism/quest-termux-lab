# Agent Notes

This repository is intended to be public.

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
- Do not commit generated APKs, idsig files, debug keystores, Android platform
  jars, native libraries, dex files, package-manager output, raw logcat, or
  launch screenshots.
- Prefer schemas, runbooks, and synthetic fixtures over real device artifacts.
- For live Quest builds, installs, launches, screenshots, logcat, ADB
  forwarding, or headset-visible validation, use the public
  `meta-quest-workflow` skill/workflow first. This repository owns the
  Termux/Linux sidecar recipes; the Meta Quest workflow owns device-operation
  discipline.

Before committing, run:

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
powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw tools/capture_x11_surface_metrics.ps1)) | Out-Null"
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_android_vnc_panel_viewer.ps1 -Unsigned
bash -n scripts/build-minimal-android-apk-on-device.sh scripts/wifi-adb-keepawake-watchdog.sh scripts/quest-x11-wide-prefs.sh scripts/start-quest-x11-wide.sh
```
