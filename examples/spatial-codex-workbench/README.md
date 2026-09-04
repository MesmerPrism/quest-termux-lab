# Spatial Codex Workbench

Status: implemented proof of concept with host validation and sanitized prior
Quest evidence, including a live GitHub pull/push round trip. A fresh device
run is still required before claiming that a new release candidate passed on
the current headset software.

This example demonstrates an operator-visible Android development loop that
runs on a Quest headset. A Meta Spatial SDK panel talks only to a typed
localhost broker owned by Termux. The broker creates an isolated Git worktree,
runs one bounded Codex turn, exposes a reviewable diff, versions and builds a
small source-only Android app, records the source commit, and deploys the exact
verified APK through an explicitly authorized ADB shell lease.

The GitHub lane is optional. It uses an already authenticated GitHub CLI to
push the run branch and create a draft pull request; the workbench never
accepts or stores a GitHub token.

## What is included

- `app/`: the Meta Spatial SDK Android panel and native localhost bridge.
- `web/`: the bundled workbench interface.
- `sidecar/`: the typed Node.js broker and Codex, GitHub, build, and ADB
  adapters.
- `demo-project/`: the reproducible source-only Android target built with
  Java, AAPT2, D8, and apksigner.
- `fixtures/`: sanitized Codex and acceptance evidence.
- [`THIRD_PARTY.md`](THIRD_PARTY.md): dependency and redistribution boundary.
- `../../schemas/spatial-codex-workbench-*.schema.json`: public event and
  artifact contracts.

The full architecture, authority boundaries, failure model, and acceptance
gates are in
[`../../docs/spatial-codex-workbench-implementation-plan.md`](../../docs/spatial-codex-workbench-implementation-plan.md).
The concise, reproducible command sequence is in
[`CLI_SHOWCASE.md`](CLI_SHOWCASE.md).
The combined two-lane presentation—Inkscape as the Spatial Desktop input proof,
followed by Codex CLI, Git, build, install, and launch from a visible desktop
terminal—is in
[`../../docs/quest-spatial-development-showcase.md`](../../docs/quest-spatial-development-showcase.md).

## Build and test on a development machine

Use JDK 17, Android SDK 35, Node.js 20 or newer, and Gradle 9.4.1:

```powershell
node --test examples/spatial-codex-workbench/sidecar/tests/*.test.mjs
gradle -p examples/spatial-codex-workbench test lint assembleDebug assembleRelease assembleAndroidTest
bash -n examples/spatial-codex-workbench/demo-project/build.sh
python tools/check_public_boundary.py --repo-root .
```

Generated APKs and Gradle state are ignored and must not be committed.

These host checks validate source shape, the typed broker, isolated Git
worktrees, Android compilation, lint, and the instrumentation APK. They do not
run Codex, authenticate GitHub, invoke a Termux Android toolchain, or authorize
ADB. Keep those as explicit live-device acceptance gates.

## Quest prerequisites

The headset needs a user-installed Termux with permission to receive
`RUN_COMMAND`, plus Node.js, Git, GitHub CLI, Codex CLI, OpenJDK, ADB, AAPT2,
D8, and apksigner. The source-only demo also needs a compatible Android
platform jar stored in Termux-private storage and a private debug keystore.

Authenticate Codex visibly in Termux with the ChatGPT device-login flow. A
ChatGPT subscription login is sufficient; no OpenAI API key is required for
this path. Authentication remains in the Codex home owned by Termux.

If GitHub publication is wanted, authenticate it separately and visibly with
`gh auth login`. The local edit/build/commit/install workflow remains usable
when GitHub is unauthenticated or the demo repository has no remote.

Termux may lack a system credential store. GitHub CLI then keeps its token in a
mode-`600` plaintext file inside Termux-private storage. Other Android apps do
not receive that file, but processes running as the Termux application identity
can read it. Use a dedicated account or repository scope appropriate to that
lab boundary.

## Security and authority boundaries

- The broker listens on loopback only, rotates a native-held bearer token, and
  exposes typed actions rather than arbitrary shell text.
- Workspaces stay under a fixed Termux-private root. Codex runs only in a
  managed run worktree.
- On conventional Linux, the default Codex sandbox is `workspace-write`.
  Horizon OS/Termux cannot supply the required bubblewrap kernel interface, so
  the Android launcher selects `danger-full-access`. This is a compatibility
  setting, not an operating-system filesystem boundary; the managed worktree,
  typed broker policy, reviewed diff, and explicit deployment gates remain the
  proof-of-concept controls.
- Build success does not grant install authority. Deployment requires exactly
  one selected ADB target, a fresh `uid=2000(shell)` readback, an immutable
  artifact record, and an immediate hash recheck.
- Codex, GitHub, ADB, and signing credentials are never returned to the WebView
  or written into public evidence.
- Pairing, uninstall, clear-data, production signing, and unattended
  deployment are outside this proof of concept.

## Live acceptance result

A current source candidate also received a narrower unattended shell test on a
Quest 3S. The exact debug APK installed and launched; version readback,
foreground/process state, a `2304x1296` first draw, target-owned OpenXR focus
and frame progression, and a bounded zero-fatal check passed. That headset did
not contain Termux or the Spatial Desktop, and no wearer participated, so the
broker, Codex/Git/build/deploy path, Inkscape, and human input usability were
correctly left unexercised. See
[`fixtures/workbench-shell-validation.synthetic.json`](fixtures/workbench-shell-validation.synthetic.json).

The complete development workflow evidence below comes from the prior prepared
Quest environment and remains historical until that environment is available
for a current replay.

The complete local golden path passed on a Quest: capability preflight,
isolated run branch, real Codex edit, reviewed diff, version bump, clean Git
commit, candidate APK build and signature/hash verification, exact-target
install and launch, installed version readback, bounded crash check, and
workbench reconnection to the same clean run after the demo app took focus.

The first integrated workbench candidate reported version code `2` and version
name `0.1.1`.

A subsequent public GitHub round trip also passed. The Quest fast-forwarded
two remote source commits, built, signed, installed, and launched version
`1.0.0`, then used Codex CLI to make a bounded change on a feature branch. The
Quest reviewed and committed version `1.0.1`, rebuilt and verified its APK,
pushed the branch, created a draft pull request, installed the candidate, and
read back the matching installed version with no bounded package fatal.

- [Public showcase repository](https://github.com/MesmerPrism/spatial-codex-quest-apk-showcase)
- [Draft PR created from Quest](https://github.com/MesmerPrism/spatial-codex-quest-apk-showcase/pull/1)

The sanitized machine-readable result is
[`fixtures/acceptance-summary.synthetic.json`](fixtures/acceptance-summary.synthetic.json).
The GitHub pull/push result is
[`fixtures/github-round-trip-acceptance.synthetic.json`](fixtures/github-round-trip-acceptance.synthetic.json).

## Cleanup

After live validation, remove the workbench-owned ADB forwarding rule, stop
the broker and tested app processes, and release the corresponding Agent Board
leases. Do not uninstall packages or delete Termux-private SDK, authentication,
workspace, keystore, or artifact data without explicit operator approval.
