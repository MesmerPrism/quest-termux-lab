# Spatial desktop panel architecture

`examples/spatial-desktop-panel` is the foreground interactive route. Termux, Termux:X11, XFCE, and x11vnc own the desktop and framebuffer. The Android application is hybrid: a normal panel Activity is the default OS-managed 2D presentation, while the Spatial SDK Activity preserves the custom immersive presentation. A shared `DesktopPanelSession` owns retained-pixel rendering, loopback RFB, bounded input, camera handoff, diagnostics, and cleanup in both modes. Presentation hosts own only their window or spatial-panel policy.

The media plane is a direct Android loopback socket; the input plane shares that session. Neither plane enters fleet control or peer mesh. The existing MJPEG streamer remains low-rate, input-free evidence plumbing. The activity is not HOME, device owner, an ADB client, a command runner, a VNC server, or a LAN listener.

The operator must use the active Termux:X11 display rather than assuming an X
display number. The established wide-session script defaults an unset
`DISPLAY` to `:1`; validate that display with `xdpyinfo` before starting
`x11vnc`, and keep the app-facing RFB endpoint fixed at Android loopback port
`5900`:

```sh
export DISPLAY="${DISPLAY:-:1}"
xdpyinfo -display "$DISPLAY" >/dev/null || {
  printf 'Termux:X11 is not ready on DISPLAY=%s\n' "$DISPLAY" >&2
  return 1 2>/dev/null || exit 1
}
x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -nopw -forever -shared
```

For bounded remote validation of a debug build, use
`examples/spatial-desktop-panel/tools/Invoke-SpatialDesktopPanelAction.ps1`
with an explicit `-Serial`. It calls an allowlisted app-owned intent and shares
the panel button dispatcher; it never accepts raw shell text. Pointer values
are bounded framebuffer coordinates and typed text is limited to 128 printable
ASCII characters. Release builds reject the intent. Treat results as semantic
panel-action/RFB proof, never as Touch, hand-ray, or OpenXR controller parity.

The default 2D panel declares a 1280x720 preferred size and an 800x450 minimum,
but Horizon OS owns its actual placement, chrome, and resizing. The immersive
panel remains 16:9 and spatially movable through the Spatial SDK `Grabbable`
component. Its top title chrome is a visual grab affordance, not a second
Android-coordinate transform writer. Spatial resize controls adjust meters
independently from desktop resolution and are hidden in OS-managed mode.

Mode changes use Meta's exclusive hybrid-activity pattern: panel-to-immersive
launches the VR Activity and removes the old task; immersive-to-panel supplies
an immutable `PendingIntent` while returning to Home. The outgoing RFB client
is disconnected before the transition and the incoming presentation reconnects
to the same loopback server. A single pure contain transform owns desktop
coordinate mapping, and the primary-pointer classifier separates taps,
double-clicks, and deliberate drags before emitting RFB button events. Every
lifecycle exit releases all held RFB button bits before disconnect. See the
example README for build, startup, cleanup, limitations, performance counters,
validation gates, and troubleshooting. Evidence uses only
`quest-termux-lab.spatial-desktop-session-evidence.v1`.
