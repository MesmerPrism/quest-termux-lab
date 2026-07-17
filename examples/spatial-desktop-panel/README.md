# Spatial Desktop Panel

This example is the interactive, foreground Quest presentation lane for an XFCE desktop owned by Termux:X11. It connects only to `127.0.0.1:5900` inside Android. It does not use the host MJPEG evidence stream, ADB forwarding, fleet commands, shell authority, or peer-mesh input mirroring.

## Pinned toolchain and licenses

- Meta Spatial SDK `0.13.2` (Meta SDK license), Kotlin `2.1.0` (Apache-2.0), AGP `8.11.1` (Apache-2.0), Gradle `9.4.1` (Apache-2.0), and JDK 17.
- AndroidX Core `1.15.0` (Apache-2.0) and JUnit `4.13.2` (EPL-1.0). The RFB subset is original MIT repository code; no VNC implementation is vendored.

Use JDK 17 and an installed Gradle 9.4.1 distribution:

```sh
cd examples/spatial-desktop-panel
gradle test assembleDebug
```

Generated APKs, caches, SDK files, and debug keys must remain untracked.

## Operator session

In Termux, start the already configured Termux:X11/XFCE session, then expose only its local display:

```sh
export DISPLAY="${DISPLAY:-:1}"
xdpyinfo -display "$DISPLAY" >/dev/null || {
  printf 'Termux:X11 is not ready on DISPLAY=%s\n' "$DISPLAY" >&2
  return 1 2>/dev/null || exit 1
}
x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -nopw -forever -shared
```

Launch the installed app through the public Meta Quest workflow, then select **Connect**. The app requests Raw plus DesktopSize, retains the framebuffer, requests one full update followed by incremental updates, and sends RFB PointerEvent/KeyEvent directly over device loopback. Stop the app connection and terminate the exact x11vnc process at session end. Never remove `-localhost`; None security is acceptable only for this operator-visible loopback lab session.

## Debug semantic-action CLI

Debug builds expose a narrow app-owned intent that reaches the same dispatcher as the panel buttons. The module CLI requires one explicit serial and accepts only `connect`, `disconnect`, `size-up`, `size-down`, `recenter-panel`, `right-click`, `scroll-up`, `scroll-down`, bounded pointer actions, printable-ASCII text, and Enter:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Invoke-SpatialDesktopPanelAction.ps1 `
  -Serial <quest-serial> -Action connect

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Invoke-SpatialDesktopPanelAction.ps1 `
  -Serial <quest-serial> -Action tap -X 640 -Y 360

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Invoke-SpatialDesktopPanelAction.ps1 `
  -Serial <quest-serial> -Action recenter-panel
```

The debug-only `start-sidecar` preparation action dispatches only the fixed documented Termux:X11/XFCE recipe and fixed loopback x11vnc arguments through Termux RunCommand; it accepts no command text. `start-witness` opens one fixed titled XFCE terminal so RFB typing can be observed without direct Termux-side input injection; `stop-witness` quits that test-only terminal daemon. Release builds reject the control intent. The CLI has no raw-command or shell-text surface, waits for its matching request marker, and returns nonzero for rejection or timeout. Coordinates are desktop framebuffer coordinates, not Android display coordinates. This proves semantic app-handler and RFB-event equivalence only; it does not prove Meta Touch, hand-ray, or OpenXR controller parity.

## Input and panel behavior

The framebuffer uses one contain/letterbox transform. Letterbox input is rejected. The panel entity uses Spatial SDK `Grabbable` with `PIVOT_Y` and a 0.5–2.5 m height range; Interaction SDK exclusively writes its transform during a physical grab. The title is only a visual grab affordance, not custom Android drag chrome. The debug-only `recenter-panel` action performs one viewer-relative transform write while preserving the current scale. `−`/`+` changes physical size from 0.65× to 1.75× while preserving 16:9; framebuffer pixels never determine meters. The desktop surface is exclusively the classic VNC single pointer: extra contacts are ignored, not represented as Linux multitouch. Primary taps move the cursor with no button mask and emit their press/release pair only on up. Spatial-ray movement within 18 desktop pixels remains a tap candidate; movement beyond that starts a normal drag by pressing at the original coordinate. A second tap within 350 ms and 32 desktop pixels snaps to the first tap's exact coordinate, making double-clicks tolerant of ray jitter without delaying the first click. Hover, right click, wheel steps, and CLI pointer actions remain unchanged. Cancel, focus loss, pause, write failure, and disconnect release only a held button and discard gesture state.

Physical Android keys map press and release for printable ASCII, modifiers, Escape, Tab, arrows, navigation, F1–F12, repeats, and therefore ordinary Ctrl/Alt/Shift chords. The explicit edit field accepts IME text but intentionally transmits only printable ASCII as paired key events. Non-ASCII composition, dead keys, clipboard transfer, and arbitrary Unicode are not claimed; use the XFCE on-screen keyboard or an application-specific ASCII transliteration.

## Protocol and security limits

The client speaks RFB 3.8, selects None security only when offered, sets 32-bit little-endian true color, accepts bounded Raw rectangles and DesktopSize, and safely disconnects on malformed dimensions, oversized names/rectangles, unknown encodings, or unsupported server messages. Bounds are 4096×4096, 8,388,608 retained pixels, 32 MiB per rectangle, 4096 rectangles/update, and 4096-byte names/cut text. Cursor pseudo-encoding is not implemented; the server cursor is expected to be composited into the framebuffer. No reconnect loop runs in the background; reconnect is an explicit button action.

Diagnostics shown in the panel are sanitized counters: dimensions/generation, updates/frames, changed pixels and bytes, decode/render time, input sequence/coordinate/mask, reconnect/error/focus/forced-release counts, and physical scale. They contain no endpoint beyond the fixed loopback route.

## Deterministic acceptance

Open `fixtures/click-grid.svg` full-screen at exactly 1280×720 in XFCE and run `xev -event mouse -event keyboard` beside it. Record the applied coordinates for center `(640,360)` and corners `(0,0)`, `(1279,0)`, `(0,719)`, `(1279,719)`. Resize the panel and switch the X root resolution, repeat center/corners, deliberately select both letterbox bands, drag across cells, right-click, scroll both ways, test Ctrl+C/arrows/F keys, then background the app while holding left. The focus-loss event must emit mask zero. Complete `../spatial-desktop-session-evidence.synthetic.json` as a private run artifact; publish only a sanitized copy conforming to the schema.

Live acceptance additionally gates bounded pointer-to-visible response and headset frame budget. Source/unit completion does not claim either device result. Troubleshoot connection refusal by checking `printf '%s\n' "$DISPLAY"`, requiring `xdpyinfo -display "$DISPLAY"` to succeed, and confirming x11vnc is listening on loopback port `5900` for that same display. Do not assume `:0`; the established wide Termux:X11 startup defaults to `:1`, while an explicitly active `DISPLAY` remains authoritative. A protocol error usually means the server selected an encoding outside this intentionally small subset.
