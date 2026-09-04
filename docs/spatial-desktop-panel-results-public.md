# Spatial Desktop Panel public validation

Status: live operator-observed proof of concept with explicit limits

This record summarizes the public-safe results of the July 2026 spatial-panel
development session and the September 2026 hybrid-panel validation. It
contains no headset serial, network address, captured image, raw log, printer
identity, credential, or signing material. The underlying checks combined
host-side automated tests, app-owned bounded actions, and live operator
observation on a Meta Quest 3S. They were not a controlled performance
benchmark.

## Validated configuration

- Meta Quest 3S running version 0.2.0 of the hybrid Android application.
- Meta Spatial SDK 0.13.2.
- Termux, Termux:X11, a 1280x720 XFCE desktop, and `x11vnc` restricted to
  Android loopback.
- Direct RFB 3.8 framebuffer and input transport between the Spatial SDK app
  and the local X desktop.
- Inkscape and CUPS installed as user-managed Termux dependencies.
- An OS-managed 2D Activity configured as the default launcher and the
  existing Spatial SDK Activity retained as the immersive presentation.

## Observed results

- The complete XFCE desktop was visible in a movable and resizable 16:9
  spatial panel.
- The panel could be grabbed without a continuous application transform
  fighting the Spatial SDK grab transform.
- Pointer movement was responsive enough for ordinary desktop navigation.
  Clicks opened desktop items, and the tuned gesture classifier supported
  jitter-tolerant double-clicks without making deliberate drags impractical.
- Right-click, wheel input, physical keyboard events, common modifiers, and
  navigation keys reached the desktop during the bounded interaction checks.
- Disconnect and reconnect controls recovered the local RFB session without a
  background reconnect loop.
- Inkscape opened and remained usable through the same panel and input path.
- Each allowlisted outside-camera action captured one 1280x960 still, passed it
  through an authenticated short-lived loopback endpoint, and opened the
  resulting embedded-image SVG in Inkscape.
- The print helper rendered the deliberately small monochrome SVG fixture,
  submitted it to the operator-configured network printer through local CUPS,
  and the operator confirmed that the physical page emerged.
- A normal launcher invocation opened the OS-managed 2D panel at a 1600x900
  runtime surface. It connected to the same 1280x720 loopback RFB desktop,
  decoded and presented framebuffer updates, and accepted bounded pointer,
  scroll, and printable-ASCII input actions with no RFB error.
- The app completed both exclusive hybrid transitions: Window mode to the
  Spatial SDK panel, and Spatial mode back to a Home panel through the
  platform `PendingIntent` route. Each outgoing client disconnected before
  transition and the incoming presentation automatically reconnected and
  presented a fresh full framebuffer.

## Validation boundaries

The run establishes live feasibility for this exact configuration. It does not
establish a numerical motion-to-photon or click-to-update latency, a sustained
frame budget, long-duration thermal behavior, battery cost, or indefinite
process survival. The optimized direct RFB route was qualitatively smoother
than the earlier MJPEG viewer, but no public benchmark trace is claimed.

The run also does not establish compatibility with arbitrary Linux
applications, other Quest models, future Horizon OS releases, every network
printer, or camera IDs other than the tested allowlist. Camera IDs are treated
as version-specific implementation details rather than a platform guarantee.
The September hybrid transition checks used the app's bounded debug intent;
manual hand/controller interaction with the new OS-managed mode and arbitrary
system window sizes remain operator acceptance gates rather than automated
claims.

The current input path remains a classic single desktop pointer. Arbitrary
Unicode composition, sophisticated IME behavior, clipboard integration,
multitouch, and stylus input are not validated. RFB None security is acceptable
only because the demonstrated server is restricted to the device loopback
interface; this project does not expose it as a LAN remote-access service.

## Reproduction and automated evidence

- Architecture and authority boundaries:
  [`spatial-desktop-panel.md`](spatial-desktop-panel.md)
- Build, launch, input, camera, and print instructions:
  [`../examples/spatial-desktop-panel/README.md`](../examples/spatial-desktop-panel/README.md)
- Synthetic coordinate fixture:
  [`../examples/spatial-desktop-panel/fixtures/click-grid.svg`](../examples/spatial-desktop-panel/fixtures/click-grid.svg)
- Synthetic low-ink print fixture:
  [`../examples/spatial-desktop-panel/fixtures/print-smoke.svg`](../examples/spatial-desktop-panel/fixtures/print-smoke.svg)
- Machine-readable evidence schema:
  [`../schemas/spatial-desktop-session-evidence.schema.json`](../schemas/spatial-desktop-session-evidence.schema.json)

The committed JSON fixture remains explicitly source-only. A future measured
headset run should publish a separate sanitized record conforming to that
schema rather than converting these qualitative observations into invented
counters.
