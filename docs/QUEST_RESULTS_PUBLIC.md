# Public Quest Findings

These findings are generalized from local lab work and intentionally omit
private paths, serials, screenshots, package identities, and project names.

## Current Findings

- Termux can act as a useful normal-app diagnostics sidecar.
- Termux app UID is distinct from Android `shell`; package queries may work
  while launch or privileged actions remain blocked.
- Termux:X11 can present a foreground 2D panel with small X11 clients.
- Pointer behavior can depend on Quest focus/click capture rather than hover.
- Proot can be useful for CLI tools and small GUI clients, but compatibility is
  package-specific.
- A full XFCE desktop can be launched as a lab sidecar through Termux:X11, and
  a Proot-hosted XFCE session can render through the same display path.
- A full desktop can render in the Quest 2D panel at the native phone-like X
  root size, but this is not yet an ergonomic desktop layout.
- A Proot-hosted terminal window can run ordinary Linux userland commands
  inside the desktop session.
- Host-visible VNC capture can work through localhost/ADB forwarding when the
  VNC server is configured to avoid shared-memory paths that Android blocks.
- Host-visible VNC can also be bridged into a local browser MJPEG stream for
  continuous observation instead of one-off screenshot capture.
- Automated VNC stream evidence should pull the stream frame/status endpoints
  directly. Browser-window or cast-window captures are optional human-visible
  witnesses, not the primary evidence path.
- VNC mirrors the X display; it does not fix headset-side panel geometry.
- Full-desktop evidence may be clearer through VNC than through the headset's
  Android panel screenshot path, which can show a black panel while the X root
  is alive.
- A resized landscape X root can be valid through VNC while the Quest 2D panel
  remains black or incomplete. Keep X-root evidence and headset-panel evidence
  labeled separately.
- Termux:X11 can expose a clean 1280x720 X root when its display resolution is
  set to an exact landscape value before the desktop starts. This can remove
  the left-slice desktop symptom in the X display and VNC stream.
- Termux:X11 preference-only native-wide probes can also create wider custom X
  roots such as 1600x900, 1920x1080, and 2560x1440.
- A full XFCE desktop can render visibly through the native Termux:X11 surface
  with an exact 1280x720 X root, without going through the VNC/MJPEG viewer.
  This is a partial success, not a finished interaction route: panel/layer
  alignment still needs manual input testing and may need activity manifest
  hints before it is ergonomic.
- Termux:X11's own Android activity may still present as a constrained
  phone-like Quest panel even when the X root is landscape. For headset-visible
  ergonomics, a separate landscape Android viewer panel can display the
  localhost MJPEG bridge without changing Termux's authority boundary.
- A minimal Android viewer panel with an explicit landscape 2D layout can show
  the full 1280x720 desktop from the localhost MJPEG bridge in headset. This is
  an observation surface only; Termux still owns the desktop session.
- A headset interaction check confirmed the small foreground Termux:X11 panel
  can receive Quest cursor input well enough to move the X cursor, click, and
  open desktop items. The larger Android viewer panel is not yet interactive
  and is visibly slower because it observes the MJPEG stream.
- A short headless-sidecar test confirmed that a Termux-owned localhost JSON
  command service can continue executing allowlisted commands while another
  headset app is foregrounded. This route does not require an X11 window or a
  visible Linux desktop.
- Shell-level Android task resizing is not a reliable product route for this
  case. It can create mismatched task and root bounds that reintroduce cropped
  or sliced desktop output.

## Still Open

- Robust landscape desktop-size geometry directly inside the Termux:X11
  Android activity, including clean activity/surface alignment.
- Manual Quest cursor input and keyboard behavior against the native-wide
  Termux:X11 surface.
- Longer validation of the landscape viewer panel, including sustained MJPEG
  frame rate, input expectations, and cleanup behavior.
- Low-latency large-panel rendering and input forwarding from the viewer panel
  back into the Linux desktop.
- Background desktop execution while another Quest app is foregrounded, with a
  controlled message route for commands or launch requests.
- Longer background-service survival tests across sleep, focus changes,
  battery policy, and foreground-service constraints.
- Text-heavy terminal or editor ergonomics.
- Full desktop performance and long-session stability.
- Live stream frame rate, latency, and CPU cost across longer sessions.
- Wake-lock behavior without external guard conditions.
- Termux:Boot behavior after reboot.
- Graphics acceleration and renderer classification.
- Audio and remote shell services.
