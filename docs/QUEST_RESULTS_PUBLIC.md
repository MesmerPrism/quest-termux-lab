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
- Host-visible VNC capture can work through localhost/ADB forwarding when the
  VNC server is configured to avoid shared-memory paths that Android blocks.
- VNC mirrors the X display; it does not fix headset-side panel geometry.

## Still Open

- Robust desktop-size geometry.
- Text-heavy terminal or editor ergonomics.
- Full desktop environments.
- Wake-lock behavior without external guard conditions.
- Termux:Boot behavior after reboot.
- Graphics acceleration and renderer classification.
- Audio and remote shell services.

