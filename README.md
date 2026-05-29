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

1. Baseline: record device model, Android version, focused surface, package
   state, and recovery route.
2. Termux CLI: verify app UID, package updates, bounded child processes, and
   cleanup.
3. Termux:X11: start a minimal X server and one small client.
4. Proot: run a CLI smoke test, then one small GUI client only after X11 is
   visible and stoppable.
5. Local dashboard: bind to device localhost and consume through an explicit
   host forward.
6. VNC: keep it localhost-only or ADB-forwarded, record evidence, then stop it.
7. Boot, wake-lock, desktop environments, audio, and graphics acceleration:
   treat each as a separate high-risk gate.

## Validation

```powershell
python tools/check_public_boundary.py --repo-root .
python -m py_compile tools/capture_vnc_screenshot.py tools/check_public_boundary.py
```

