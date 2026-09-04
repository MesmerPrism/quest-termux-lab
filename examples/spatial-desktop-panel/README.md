# Spatial Desktop Panel

This example is the interactive, foreground Quest presentation lane for an XFCE desktop owned by Termux:X11. It is a hybrid Android application with two exclusive presentations over one shared desktop-session implementation:

- **Window mode** is the default launcher activity. Horizon OS owns the 2D panel's placement, chrome, and resizing.
- **Spatial mode** is the existing immersive Spatial SDK activity. The application owns a grabbable 16:9 panel, viewer-relative recentering, and bounded physical scaling.

The **Spatial** or **Window** button switches modes, carries an active connection forward, and closes the outgoing activity. Both modes connect only to `127.0.0.1:5900` inside Android. Neither uses the host MJPEG evidence stream, ADB forwarding, fleet commands, shell authority, or peer-mesh input mirroring.

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

Launch the installed app through the public Meta Quest workflow. A normal launcher invocation opens Window mode; launch `.SpatialDesktopActivity` explicitly only when validating the immersive presentation. Select **Connect**. The app requests Raw plus DesktopSize, retains the framebuffer, requests one full update followed by incremental updates, and sends RFB PointerEvent/KeyEvent directly over device loopback. Stop the app connection and terminate the exact x11vnc process at session end. Never remove `-localhost`; None security is acceptable only for this operator-visible loopback lab session.

## Debug semantic-action CLI

Debug builds expose a narrow app-owned intent that reaches the same dispatcher as the panel buttons. The module CLI requires one explicit serial and accepts only `connect`, `disconnect`, `size-up`, `size-down`, `recenter-panel`, `switch-presentation`, `right-click`, `scroll-up`, `scroll-down`, `camera-50`, `camera-51`, `microphone-toggle`, `show-keyboard`, bounded pointer actions, printable-ASCII text, and Enter:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Invoke-SpatialDesktopPanelAction.ps1 `
  -Serial <quest-serial> -Action connect

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Invoke-SpatialDesktopPanelAction.ps1 `
  -Serial <quest-serial> -Action tap -X 640 -Y 360

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Invoke-SpatialDesktopPanelAction.ps1 `
  -Serial <quest-serial> -Presentation spatial -Action recenter-panel
```

The CLI targets Window mode by default; pass `-Presentation spatial` for spatial-only actions such as recentering and physical scaling. The debug-only `start-sidecar` preparation action dispatches only the fixed documented Termux:X11/XFCE recipe and fixed loopback x11vnc arguments through Termux RunCommand; it accepts no command text. `start-witness` opens one fixed titled XFCE terminal so RFB typing can be observed without direct Termux-side input injection; `stop-witness` quits that test-only terminal daemon. Release builds reject the control intent. The CLI has no raw-command or shell-text surface, waits for its matching request marker, and returns nonzero for rejection or timeout. Coordinates are desktop framebuffer coordinates, not Android display coordinates. This proves semantic app-handler and RFB-event equivalence only; it does not prove Meta Touch, hand-ray, or OpenXR controller parity.

## Input and presentation behavior

Both presentations inflate the same Android layout and use one `DesktopPanelSession` for RFB, rendering, input, camera import, diagnostics, and lifecycle cleanup. The framebuffer uses one contain/letterbox transform, so Horizon OS window resizing does not change desktop coordinates and input in a letterbox band is rejected.

In Spatial mode, the panel entity uses Spatial SDK `Grabbable` with `PIVOT_Y` and a 0.5–2.5 m height range; Interaction SDK exclusively writes its transform during a physical grab. The title is only a visual grab affordance, not custom Android drag chrome. The debug-only `recenter-panel` action performs one viewer-relative transform write while preserving the current scale. `−`/`+` changes physical size from 0.65× to 1.75× while preserving 16:9; framebuffer pixels never determine meters. In Window mode those controls are hidden because Horizon OS owns window placement and size.

The desktop surface is exclusively the classic VNC single pointer: extra contacts are ignored, not represented as Linux multitouch. Primary taps move the cursor with no button mask and emit their press/release pair only on up. Pointer movement within 18 desktop pixels remains a tap candidate; movement beyond that starts a normal drag by pressing at the original coordinate. A second tap within 350 ms and 32 desktop pixels snaps to the first tap's exact coordinate, making double-clicks tolerant of ray jitter without delaying the first click. Hover, right click, wheel steps, and CLI pointer actions remain unchanged. Cancel, focus loss, pause, write failure, mode switching, and disconnect release only a held button and discard gesture state.

The visible **Right-click mode** control arms one secondary click instead of clicking the old cursor position. After arming it, the next press on the Linux framebuffer moves to that target, emits RFB button 3, and automatically returns to primary-click mode. Cancelling the button, focus loss, pause, mode switching, and disconnect clear the arm.

While RFB is connected, the right Touch controller's A button also attempts one Linux secondary click at the current mapped desktop cursor position. Spatial mode reads the Spatial SDK right-controller `ButtonA` component before panel interaction and suppresses the corresponding synthesized primary gesture. Both Activities retain Android key and raw-joystick motion routes for environments that expose A separately. Horizon OS may expose only a synthesized primary panel gesture in Window mode, so the armed control is the guaranteed cross-mode route. Repeat/duplicate sources are deduplicated and the normal keyboard letter A remains distinct. ADB-synthesized `KEYCODE_BUTTON_A` establishes only Android routing; a real controller remains the acceptance source.

The right Touch controller's B button is a synchronized voice-input action. Put the Linux cursor over the Codex voice button and press B once: the app first starts Quest microphone capture and confirms the loopback PCM stream, then emits one Linux primary click at that cursor position. Press B again to click the same control and stop capture. Starting before the first click prevents the Codex session from opening against an empty source; the stop click is sent before Android capture is released. Spatial mode reads `ButtonB` directly from the same Spatial SDK controller component as A. Horizon OS maps B/Y to Android Back for ordinary 2D applications, so Window mode intentionally consumes that Back action for the same voice toggle while the desktop is connected. Android gamepad-style B routes remain accepted as a compatibility path, but real-controller acceptance is required in both modes.

Actual Android `AudioRecord` state owns two app-side indicators in both presentations: the top control changes from `MIC OFF` to a red `● MIC LIVE`, and a full-width red `QUEST MICROPHONE LIVE` banner overlays the desktop without resizing it. Both disappear only after capture stops or fails; merely requesting a start does not show a false live state. This makes an accidental B press visible even when the Linux cursor was not over Codex Voice. The visible microphone button toggles only capture and remains the recovery stop; it does not click Linux.

Physical Android keys map press and release for printable ASCII, modifiers, Escape, Tab, arrows, navigation, F1–F12, repeats, and therefore ordinary Ctrl/Alt/Shift chords. A paired Bluetooth keyboard does not require Meta's floating keyboard, but the app must be foreground and the framebuffer must own focus. The `Virtual keyboard` panel button focuses the explicit edit field and asks Horizon OS to show its current input method; printable ASCII entered there is forwarded as paired RFB key events and the field is immediately cleared. This provides three complementary input routes: Horizon's virtual keyboard, a paired physical Bluetooth keyboard, and the Quest microphone bridge. Non-ASCII composition, dead keys, clipboard transfer, and arbitrary Unicode are not claimed; use the XFCE on-screen keyboard or an application-specific ASCII transliteration.

## Protocol and security limits

The client speaks RFB 3.8, selects None security only when offered, sets 32-bit little-endian true color, accepts bounded Raw rectangles and DesktopSize, and safely disconnects on malformed dimensions, oversized names/rectangles, unknown encodings, or unsupported server messages. Bounds are 4096×4096, 8,388,608 retained pixels, 32 MiB per rectangle, 4096 rectangles/update, and 4096-byte names/cut text. Cursor pseudo-encoding is not implemented; the server cursor is expected to be composited into the framebuffer. No reconnect loop runs in the background; reconnect is an explicit button action.

The raw transport diagnostics strip is hidden in the normal panel because its counters are intended for engineering rather than end users. The top connection control still changes between `Connect` and `Disconnect` as a human-readable state cue. The same sanitized dimensions/generation, update/frame, changed-pixel/byte, decode/render, input, reconnect/error/focus/forced-release, and physical-scale diagnostics remain available in structured Android logs. They contain no endpoint beyond the fixed loopback route.

## Quest microphone as a Linux input source

Linux cannot directly open the Quest ALSA devices: the Termux UID has no `/dev/snd` access. This example therefore uses the supported Android `AudioRecord` API with `RECORD_AUDIO`, streams mono 48 kHz signed 16-bit PCM to `127.0.0.1:5911`, and feeds a PulseAudio `module-pipe-source` named `quest_mic`. WASAPI is Windows-only and is not part of this path.

Install and start the fixed Termux helper from the checked-out example:

```sh
cd ~/quest-termux-lab/examples/spatial-desktop-panel/linux
bash ./install-quest-mic-bridge.sh
quest-mic-pulse-bridge start
quest-mic-pulse-bridge status
```

The helper binds its PCM receiver and PulseAudio native protocol to IPv4 loopback only, sets `quest_mic` as the default source, and accepts no paths, ports, or command text from the Android app. Keep it running for the whole Linux desktop session. While Android capture is off it supplies real-time silence, so Linux applications can enumerate and open a stable microphone before a controller starts live capture. In the Debian Proot that runs the Codex desktop app, install the Pulse and ALSA client libraries and expose the native Termux server:

```sh
apt-get install -y pulseaudio-utils libasound2-plugins alsa-utils
export PULSE_SERVER=127.0.0.1
pactl list short sources
pactl get-default-source
```

The expected default is `quest_mic`. Start the helper and verify that default **before** launching Codex; Electron discovers audio devices during process startup, so restart Codex after adding or repairing the source. Keep `PULSE_SERVER=127.0.0.1` in the Codex launch environment. The Android app never writes a recording; only byte counts and a coarse RMS value enter diagnostics. Capture stops on the explicit second toggle, Activity pause, mode switch, or destruction, but the Linux source remains present and returns to silence. The first use requires the ordinary visible microphone permission unless it was granted during an inspected developer installation.

For manual acceptance, launch Codex and connect the desktop, hover its voice button, press right-controller B, speak a short phrase, and press B again. Accept only when the panel reports `MIC LIVE`, Android reports an active non-silenced `VOICE_RECOGNITION` recording, Codex visibly transcribes the phrase, the second B press returns to `MIC OFF`, and the Android recording monitor reports a stop. A synthetic `KEYCODE_BUTTON_B` validates the Android handler and synchronized RFB click but is not proof of a real Touch-controller route or speech recognition.

## Deterministic acceptance

Open `fixtures/click-grid.svg` full-screen at exactly 1280×720 in XFCE and run `xev -event mouse -event keyboard` beside it. In Window mode, record the applied coordinates for center `(640,360)` and corners `(0,0)`, `(1279,0)`, `(0,719)`, `(1279,719)`, resize the Horizon OS window, and repeat. Switch to Spatial mode, confirm automatic reconnection, repeat center/corners, grab and resize the panel, then switch back to Window mode. In both presentations deliberately select letterbox bands, drag across cells, right-click, scroll both ways, test Ctrl+C/arrows/F keys, and background the app while holding left. The focus-loss event must emit mask zero and every outgoing activity must disconnect its RFB client. Complete `../spatial-desktop-session-evidence.synthetic.json` as a private run artifact; publish only a sanitized copy conforming to the schema.

Live acceptance additionally gates bounded pointer-to-visible response and headset frame budget. Source/unit completion does not claim either device result. Troubleshoot connection refusal by checking `printf '%s\n' "$DISPLAY"`, requiring `xdpyinfo -display "$DISPLAY"` to succeed, and confirming x11vnc is listening on loopback port `5900` for that same display. Do not assume `:0`; the established wide Termux:X11 startup defaults to `:1`, while an explicitly active `DISPLAY` remains authoritative. A protocol error usually means the server selected an encoding outside this intentionally small subset.

## Small Inkscape export-and-print action

`linux/quest-inkscape-print` provides the deliberately small GUI path used by
this example. The desktop launcher accepts a dropped SVG or opens a Zenity file
chooser, confirms the default CUPS destination, renders the SVG page through
Inkscape, flattens it to JPEG with Pillow, and submits one A4, one-sided job.
Monochrome is the default; pass `--color` only when color is intentional. The
temporary PNG, JPEG, and log are removed when the action exits.

Install the user-facing dependencies from the public Termux repositories:

```sh
pkg install cups inkscape python-pillow zenity
```

Configure a driverless queue separately, with a printer address discovered by
the operator. Keep the scheduler on Termux's loopback-only port and explicitly
disable queue sharing:

```sh
cupsd
lpadmin -h 127.0.0.1:8631 -p <queue> -E \
  -v ipp://<printer-address>/ipp/print -m everywhere \
  -o printer-is-shared=false
lpadmin -h 127.0.0.1:8631 -d <queue>
```

The stock Termux CUPS `SystemGroup` may not include the current Android app
username. If `lpadmin` returns `Unauthorized`, add the exact output of
`id -un` to `SystemGroup` in `$PREFIX/etc/cups/cups-files.conf`, validate with
`cupsd -t`, and restart only the CUPS process. Do not weaken the location or
policy blocks and do not expose the scheduler to the LAN.

Install the action and its XFCE desktop entry:

```sh
cd examples/spatial-desktop-panel/linux
bash ./install-quest-inkscape-print.sh
```

For a no-paper pipeline check, use the synthetic fixture:

```sh
quest-inkscape-print --file ../fixtures/print-smoke.svg --yes --dry-run --no-dialogs
```

The fixture contains only `QTL` and one thin dark line. It exists specifically
to keep a live printer validation page low-ink and unambiguous. A CUPS completed
state proves submission through the printer endpoint; the operator must still
confirm that the physical page emerged.

## One-shot outside-camera import into Inkscape

The panel's `CAM 50` and `CAM 51` buttons provide a deliberately bounded still
image route. The Android application owns Camera2 permission and lifecycle,
captures one `YUV_420_888` frame from the selected Quest outside camera,
converts that frame once to JPEG, and serves it from a random-port
`127.0.0.1` endpoint. The endpoint requires a per-capture random bearer token,
permits one successful download, expires after 30 seconds, and is never exposed
to the LAN.

Termux consumes the still with `quest-camera2-to-inkscape`, verifies the JPEG
type, byte count, dimensions, and decode, then writes a user-owned `.jpg` and an
SVG with the JPEG embedded under `~/Pictures/Quest Camera Imports/`. It opens
that SVG on `DISPLAY=:1`. The Android side does not persist the raw YUV frame,
and no image bytes travel through JSON, intent extras, logs, VNC control
messages, or the high-rate H.264 streaming path.

Install the additional Termux dependency and helper from the checked-out
example:

```sh
pkg install -y python-pillow inkscape
cd ~/quest-termux-lab/examples/spatial-desktop-panel/linux
bash ./install-quest-camera2-inkscape.sh
```

Termux must already allow the app's explicit `RUN_COMMAND` integration, as it
does for the documented desktop sidecar flow. On first use, grant the visible
Android camera permission request. Lab builds may also require the documented
headset-camera permission grant for the public package, depending on the
Horizon OS build. Camera IDs `50` and `51` are the only accepted IDs; they are
the outside pair validated by the referenced custom Camera2 projection work.

This is a still-image interoperability demonstration, not a camera application,
continuous capture service, calibrated stereo camera, or promise that these IDs
remain stable across other headset models or OS versions. Captured images are
private user artifacts and must not be committed to this public repository.
