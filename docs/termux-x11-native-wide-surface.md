# Termux:X11 Native Wide Surface

This lane tests whether the upstream Termux:X11 Android activity can become a
usable wide Quest 2D panel before maintaining a fork. It keeps Termux:X11 as a
normal Android app sidecar. It does not make Termux a launcher, managed-device
surface, broker/runtime authority, watchdog authority, or hidden daemon.

The working fallback remains the localhost VNC/MJPEG route plus the public
landscape viewer panel. That path is useful evidence plumbing, but it is slower
and observation-only. The native-wide milestone is specifically about making
the actual Termux:X11 surface wide, interactive, and measurable.

## Hypothesis

Termux:X11 can already create wide X roots through preferences. The open
question is whether Horizon OS gives the Termux:X11 activity a wide panel and
maps input correctly after those preferences are applied.

Keep three evidence routes separate:

- X server root: `xdpyinfo`, `xrandr`, and VNC evidence from display `:1`.
- Android activity panel: ADB screenshot, window, activity, SurfaceFlinger, and
  `gfxinfo` evidence for the Termux:X11 activity.
- Fallback viewer panel: the separate landscape viewer that observes VNC/MJPEG.

## Tiered Plan

| ID | Test | Pass condition |
| --- | --- | --- |
| X11-WIDE-00 | Upstream preference-only probe | Upstream Termux:X11 can be forced to a wide X root such as `1280x720`, `1600x900`, or `1920x1080`. |
| X11-WIDE-01 | Quest panel geometry capture | Evidence proves whether the Android activity is wide, phone-like, cropped, black, or unknown. |
| X11-WIDE-02 | Manifest-only fork patch | A patched activity requests a wide Quest panel without changing X server code. |
| X11-WIDE-03 | Default preference patch | A fresh Quest-flavored install defaults to a wide desktop. |
| X11-WIDE-04 | Side-by-side package | `TERMUX_X11_OVERRIDE_PACKAGE` connects the Termux-side command to the forked Android activity. |
| X11-WIDE-05 | Input transform | Quest controller, pointer, mouse, and keyboard modes map correctly enough for desktop interaction. |
| X11-WIDE-06 | Focus/Menu/Home | The surface survives or cleanly resumes after Quest menu, Home, and focus changes. |
| X11-WIDE-07 | Performance | Native surface latency and frame rate beat the VNC/MJPEG viewer enough to justify retiring VNC for interactive use. |
| X11-WIDE-08 | Cleanup | Stop server, close activity, remove test forwards, and leave no hidden X11/VNC process. |

Stop condition: if the preference-only probe and the manifest-only patch both
produce only a narrow or cropped Quest panel, classify the blocker as Quest
panel policy for this activity and keep VNC/MJPEG as the bounded observation
fallback.

## Preference-Only Probe

Open the Termux:X11 Android activity once, then run the preference script from
Termux:

```sh
cd "$HOME/quest-termux-lab"
QUEST_X11_RESOLUTION_MODE=custom \
QUEST_X11_RESOLUTION=1920x1080 \
QUEST_X11_STRETCH=true \
QUEST_X11_FULLSCREEN=true \
QUEST_X11_TOUCH_MODE=1 \
QUEST_X11_POINTER_CAPTURE=false \
sh scripts/quest-x11-wide-prefs.sh
```

Restart the X server after changing preferences:

```sh
QUEST_X11_RESOLUTION_MODE=custom \
QUEST_X11_RESOLUTION=1920x1080 \
QUEST_X11_STRETCH=true \
QUEST_X11_FULLSCREEN=true \
sh scripts/start-quest-x11-wide.sh
```

Recommended matrix:

| Resolution | Stretch | Input note |
| --- | --- | --- |
| `1280x720` | `false`, then `true` | Known-good X-root control. |
| `1600x900` | `false`, then `true` | Intermediate Quest readability probe. |
| `1920x1080` | `false`, then `true` | Main native-wide target. |
| `2560x1440` | `true` only after stable lower resolutions | Stress probe. |

Test `touchMode=1`, `touchMode=2`, and `touchMode=3` only after a wide panel is
visible. Test `pointerCapture=true` separately because it can change recovery
and focus behavior.

## Evidence Capture

From a host with ADB access:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools\capture_x11_surface_metrics.ps1 `
  -Package com.termux.x11
```

The capture tool writes under `runs/` by default. Keep real evidence out of git.

Capture at least:

- `wm size`
- `wm density`
- `dumpsys activity top`
- `dumpsys window`
- `dumpsys SurfaceFlinger`
- `dumpsys gfxinfo com.termux.x11`
- a headset screenshot
- optional Termux-side `xdpyinfo`, `xrandr`, and `glxinfo -B`

Record the compact result with `schemas/x11_surface_evidence.schema.json`.

## Interpretation

| Result | Meaning |
| --- | --- |
| Wide desktop fills a wide Quest panel | No fork needed; package the preference recipe. |
| X root is wide but the activity panel is narrow | Android activity/window geometry is the blocker. |
| Desktop is cropped or rotated | `adjustResolution`, `displayStretch`, orientation, or panel bounds are conflicting. |
| Surface is wide but input coordinates are wrong | Fork or configure input transform/pointer mode, not the X server first. |
| Panel remains phone-shaped across preferences | Move to manifest/activity window hints. |

## Current Public Finding

Initial Quest probes show that preference-only native-wide geometry is worth
continuing:

- custom X roots at `1280x720`, `1600x900`, `1920x1080`, and `2560x1440`
  reported correctly through `xdpyinfo` and `xrandr`;
- exact `1280x720` plus a full XFCE session rendered visibly through the native
  Termux:X11 surface, without using the VNC/MJPEG viewer;
- the result is still only `pass_with_limits` because the headset-visible
  activity/surface alignment is not clean enough to call the route ergonomic,
  and manual input has not been validated against the native-wide surface.

The next evidence gate is manual input and focus testing on the exact
`1280x720` native-wide XFCE surface. If input or surface alignment fails there,
move to the manifest-only patch tier before touching X server code.

## Minimal Fork Target

Do not rewrite the X server first. Start with Android activity hints:

1. Add a manifest activity `screenOrientation` value for a Quest flavor.
2. Add an activity `<layout>` block with wide default/minimum dimensions.
3. Keep `resizeableActivity="true"`.
4. Only then consider default preferences and side-by-side package routing.

Patch scaffolds live under `patches/termux-x11-quest-wide/`. They are not a
vendored fork. Review upstream licenses before distributing any patched APK.

## Side-By-Side Package Rule

For A/B testing, a Quest-flavored package can use a separate application id.
When it does, launch Termux:X11 from Termux with:

```sh
export TERMUX_X11_OVERRIDE_PACKAGE=org.questtermuxlab.x11
```

Patch hardcoded Android package broadcasts only when they prevent the side-by-
side package from receiving preference or stop events. Prefer using the app's
runtime package id instead of adding more hardcoded package strings.

If a side-by-side build changes the application id but keeps the activity class
under the upstream Java package, set `QUEST_X11_ACTIVITY` explicitly in the
start wrapper, for example `org.questtermuxlab.x11/com.termux.x11.MainActivity`.

## Non-Goals

- No root, SELinux changes, bootloader changes, or ADB authorization bypasses.
- No LAN VNC exposure as part of this lane.
- No hidden boot daemon or launcher replacement.
- No GPL source vendoring into this MIT repository.
- No high-rate media or XR runtime payload routing through JSON control paths.
