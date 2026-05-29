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
- Prefer schemas, runbooks, and synthetic fixtures over real device artifacts.
- For live Quest builds, installs, launches, screenshots, logcat, ADB
  forwarding, or headset-visible validation, use the public
  `meta-quest-workflow` skill/workflow first. This repository owns the
  Termux/Linux sidecar recipes; the Meta Quest workflow owns device-operation
  discipline.

Before committing, run:

```powershell
python tools/check_public_boundary.py --repo-root .
python -m py_compile tools/capture_vnc_screenshot.py tools/check_public_boundary.py
```
