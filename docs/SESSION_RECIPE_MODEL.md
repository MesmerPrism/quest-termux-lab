# Session Recipe Model

Session recipes describe how to run a lab sidecar without turning it into a
runtime authority. They are data records first; scripts can be generated or run
only after a recipe is reviewed.

Core fields:

- `id`: stable recipe identifier.
- `purpose`: why the session exists.
- `authority_boundary`: what the recipe is not allowed to control.
- `preflight`: checks before starting.
- `start`: ordered commands or operator steps.
- `status`: checks that prove the session is alive.
- `stop`: graceful shutdown steps.
- `cleanup`: fallback cleanup and verification.
- `evidence`: artifacts expected from a run.
- `risks`: known risks and recovery notes.

Design rules:

- Prefer small recipes over full desktop bootstrap scripts.
- Treat Proot app launchers as inventory records before generating wrappers.
- Keep VNC localhost-only by default.
- Treat graphics acceleration, audio, boot autostart, wake locks, and LAN
  exposure as separate gates.
- Full desktop recipes should remain opt-in lab sessions with explicit
  start/status/stop/cleanup checks. A working desktop does not make Termux a
  HOME surface, broker authority, watchdog, or product dependency.
