# Quest Spatial Development Showcase

This guide combines two independently useful demonstrations without claiming
that either one proves the other:

1. the Spatial Desktop runs Inkscape through the interactive Linux desktop and
   demonstrates panel placement plus mouse-like and keyboard input; and
2. Codex CLI, Git, the Android build tools, and an explicitly authorized ADB
   session perform a complete source-to-running-APK loop locally on Quest.

The first lane is a desktop/input demonstration. The second is a development
workflow demonstration. They share the Termux environment and can both be
shown through the Spatial Desktop, but their validation evidence remains
separate.

## Current evidence status

| Surface | Public state | Evidence boundary |
| --- | --- | --- |
| Spatial Desktop and Inkscape | Source, tests, CI, runbook, and a sanitized live result are published. | The live result is qualitative. It does not claim measured latency, arbitrary Linux compatibility, or long-duration thermal stability. |
| Workbench Spatial SDK shell | The current candidate installed and launched on a Quest 3S with first-draw, foreground, process, OpenXR-focus, frame-progression, and fatal-free evidence. | The connected headset lacked Termux and the Spatial Desktop, so this is not a current Codex/Git or Inkscape result. No wearer input was tested. |
| Codex CLI, Git, and local APK build | A bounded workflow, source-only demo app, host tests, and sanitized prior Quest results are published. | Host tests and the current shell-only device result do not prove Codex authentication, Termux package availability, ADB authority from inside Termux, or a current full Quest run. |
| Install and launch | Previously passed through an operator-authorized, explicit ADB target with Android shell UID verification. | A new release candidate still requires a fresh serial-scoped device run before making a current-version claim. |
| GitHub round trip | A prior Quest run pulled source, pushed a feature branch, and opened a draft pull request. | Authentication is operator-owned and never part of the app, prompt, repository, or public evidence. |

The existing public round-trip evidence points to the
[`spatial-codex-quest-apk-showcase`](https://github.com/MesmerPrism/spatial-codex-quest-apk-showcase)
repository and its
[`#1` draft pull request](https://github.com/MesmerPrism/spatial-codex-quest-apk-showcase/pull/1).

## Architecture

```text
Spatial Desktop app
    |
    | Android loopback RFB and bounded input events
    v
Termux:X11 + XFCE
    |
    +-- Inkscape              input demonstration
    |
    +-- visible terminal
          |
          +-- Codex CLI       bounded source edit
          +-- Git / gh        diff, commit, optional push and draft PR
          +-- Java/AAPT2/D8   local source-only APK build
          +-- apksigner       private debug signing and verification
          +-- adb             explicit authorized target only
```

The optional
[`Spatial Codex Workbench`](../examples/spatial-codex-workbench/README.md)
provides a dedicated Spatial SDK interface over the same bounded development
steps. It is useful as a product prototype, but it is not necessary for the
transparent showcase: running the commands in a visible XFCE terminal makes it
obvious that the development toolchain itself is local to the headset.

## Showcase A: Inkscape input

Use the already-published
[`Spatial Desktop operating guide`](../examples/spatial-desktop-panel/README.md)
to start Termux:X11, XFCE, the loopback-only VNC server, and the Spatial Desktop
app.

For a concise input demonstration:

1. Connect the Spatial Desktop panel and move it into a comfortable position.
2. Open Inkscape from XFCE.
3. Draw a short freehand line and two or three letter shapes or text glyphs.
4. Select and move one object to show deliberate dragging.
5. Double-click an object or tool target to show the spatially tolerant
   double-click path.
6. Zoom or scroll, enter a few characters with a physical keyboard, and save
   the SVG to a private working directory.
7. Grab and resize the panel once while Inkscape remains open.

This sequence demonstrates pointer mapping, hover, click, double-click, drag,
wheel, keyboard input, and panel manipulation without relying on a complicated
Linux workload. Printing and camera-to-Inkscape import are separate optional
extensions and should not distract from the core input story.

## Showcase B: Codex CLI, Git, and a local APK

Open a terminal inside the same Linux desktop. Follow the exact bounded command
sequence in
[`CLI_SHOWCASE.md`](../examples/spatial-codex-workbench/CLI_SHOWCASE.md).
The visible sequence should establish these facts in order:

1. `codex login status`, `git --version`, and the required Android build tools
   are available in Termux.
2. The public showcase repository is cloned or fast-forwarded and begins clean.
3. A new `codex/` feature branch is created.
4. One bounded `codex exec` turn changes only the requested Java source file.
5. `git status`, `git diff --check`, and a visible diff establish the review
   boundary before committing.
6. `version.properties` is updated and only the intended source files are
   committed.
7. The app is compiled, packaged, signed with a private debug key, and verified
   into a fresh output directory outside Git.
8. The feature branch is optionally pushed and a draft pull request is created
   with an already-authenticated GitHub CLI session.
9. Only after selecting one explicit ADB target and verifying
   `uid=2000(shell)`, the exact hashed candidate is installed and launched.
10. The installed version and running process are read back and compared with
    the source commit and artifact record.

Do not paste a token, pairing secret, keystore path, device serial, or raw log
into the terminal while recording. A public video may show that authentication
status passed, but it should not show authentication material.

## Host acceptance before a headset run

Run these checks from a clean checkout:

```sh
python tools/check_public_boundary.py --repo-root .
python tools/check_repository_integrity.py --repo-root .
node --test examples/spatial-codex-workbench/sidecar/tests/*.test.mjs
bash -n examples/spatial-codex-workbench/demo-project/build.sh
gradle -p examples/spatial-desktop-panel test lint assembleDebug assembleRelease
gradle -p examples/spatial-codex-workbench test lint assembleDebug assembleRelease assembleAndroidTest
```

These checks validate repository hygiene, the typed broker and isolated Git
workflow, both Android applications, and the instrumentation APK. They do not
run Codex, build the demo APK with the Termux toolchain, authenticate GitHub,
or exercise ADB.

## Device acceptance

A current release claim requires an attended run on one explicitly leased
headset. Record raw evidence privately and publish only a sanitized summary.

- Confirm the Spatial Desktop package and candidate commit before installation.
- Confirm the VNC listener remains on Android loopback.
- Exercise the Inkscape input sequence, disconnect/reconnect, and panel resize.
- Confirm the Codex and Git worktree begins clean.
- Run one bounded Codex source edit and reject any unexpected changed path.
- Build into a new untracked artifact directory and verify signature and hash.
- Confirm exactly one ADB target is selected and its shell UID is `2000`.
- Install and launch the exact verified candidate.
- Read back package version, process state, and a bounded package-specific fatal
  window.
- Stop only the tested packages and run-owned services, remove run-owned
  forwards, and release the headset lease.

The
[`Spatial Codex Workbench instrumentation`](../examples/spatial-codex-workbench/app/src/androidTest/java/io/github/mesmerprism/questtermuxlab/spatialcodex/WorkbenchE2eInstrumentation.kt)
can automate the structured Workbench path after the same device and ADB
authority gates are satisfied. The terminal-driven video remains the clearest
proof that Codex CLI and the Android toolchain execute locally.

## Suggested video sequence

Target four to six minutes and remove installation/setup dead time.

1. Open the Spatial Desktop and connect to the already-running local XFCE
   session.
2. Use Inkscape for a compact pointer, drag, double-click, wheel, keyboard, and
   resize demonstration.
3. Open the visible terminal and show a clean Git checkout and feature branch.
4. Run the bounded Codex edit, then review the changed file and diff.
5. Build and verify the APK; show concise success, version, and hash summaries.
6. Commit the reviewed change and, if desired, push it and display the draft PR
   URL.
7. Show the shell-UID gate without exposing the serial, install the exact APK,
   and launch the resulting Quest panel.
8. End on the running demo app and a simple architecture graphic explaining
   that the full loop ran locally after dependencies and authentication were
   prepared.

## Claims after a successful current run

It is reasonable to say that the tested Quest configuration:

- displayed and controlled the specified XFCE/Inkscape workflow through a
  movable Spatial SDK panel;
- ran the specified Codex CLI edit and Git workflow locally in Termux;
- compiled and signed the source-only Android app locally;
- installed and launched the exact verified candidate through an explicitly
  authorized ADB session; and
- completed the documented GitHub round trip if that optional step was
  exercised during the accepted run.

Do not claim arbitrary Linux GUI compatibility, unattended deployment, an ADB
authorization bypass, production signing, indefinite thermal stability, or
that host CI proves current headset behavior.
