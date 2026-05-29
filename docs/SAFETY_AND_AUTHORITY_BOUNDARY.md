# Safety And Authority Boundary

Termux on Quest is a normal Android application. This repository treats it as
a lab sidecar that can run userland tools, display X11 clients, and expose
operator-approved local diagnostics.

Use the public `meta-quest-workflow` skill or an equivalent team workflow for
live headset operations such as ADB, APK install/launch, screenshots, logcat,
port forwarding, capture, and readiness checks. This repository describes the
Termux sidecar layer; it does not replace device-operation discipline.

It is not:

- Android `shell`
- device owner
- a HOME replacement
- a kiosk policy engine
- a hidden watchdog
- an ADB authorization bypass
- an XR compositor or runtime authority

## Safe Defaults

- Start visible sessions manually.
- Keep every session stoppable.
- Bind local dashboards and VNC to localhost unless a separate, explicit LAN
  test is being run.
- Record cleanup evidence after VNC, HTTP servers, wake locks, Proot sessions,
  and X11 sessions.
- Keep APK sourcing and signing families explicit.

## Sensitive Data

Do not commit:

- headset serial numbers
- local machine paths
- pairing keys or QR data
- screenshots or logs from real devices
- package names from private applications
- real IP addresses from private networks
- generated APKs or downloaded upstream artifacts

Use synthetic fixtures and redacted examples instead.

## Quest Readiness

Screen-on does not always mean XR-ready. After reboot or sleep, verify display,
tracking, controller/hand input, foreground surface, and camera availability
before interpreting app failures as meaningful evidence.
