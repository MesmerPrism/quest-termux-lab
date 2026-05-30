# On-Device APK Build, Install, And Launch

This runbook captures the public-safe milestone where a Quest Termux sidecar
can build a small Android APK, install it back onto the same headset through an
authorized WiFi ADB connection, and launch it into a visible Quest panel.

It is intentionally narrow. Termux is still a normal Android app unless it is
using an explicitly authorized ADB TCP endpoint. ADB shell authority comes from
the user-approved debugging session, not from Termux itself.

## What This Proves

- Termux can run the Android `adb` client.
- After an external workflow enables or pairs WiFi ADB, the Termux client can
  connect to the headset over loopback and receive Android shell authority.
- A temporary Termux-side ADB watchdog can keep the headset awake while that
  authorized debugging session remains active.
- Termux can host a baseline Android APK build toolchain: Java, AAPT2, D8,
  zipalign, apksigner, and Rust/Cargo.
- A simple source-only Android Activity APK can be built, signed, installed,
  and launched from the headset.
- A Rust native library can be compiled on the headset and packaged into an
  APK-shaped experiment, but OpenXR rendering still needs its own proof.

## What This Does Not Prove

- No root, device-owner, HOME, kiosk, or hidden boot authority.
- No ADB authorization bypass.
- No persistence across reboot, `adb usb`, adbd restart, debugging timeout, or
  user revocation.
- No proof that a pre-granted normal helper app can restore WiFi ADB after
  reboot. A helper can record app-owned boot/status evidence, but shell lease
  recovery remains external or user-authorized.
- No Makepad or full XR app build loop yet.
- No OpenXR session creation or headset-rendered XR frame yet.
- No permission to commit generated APKs, keystores, platform jars, logs, or
  real device evidence.

## Authority Model

| Surface | Owner |
| --- | --- |
| Termux packages, scripts, source checkout, local build output | Termux sidecar |
| ADB shell commands after authorization | User-approved ADB debugging session |
| Headset readiness, protected prompts, controller requirement | Operator and Quest workflow |
| Runtime app state, broker state, stream registries | The app or broker under test |
| Public reusable knowledge | Sanitized docs, schemas, scripts, and fixtures |

The keep-awake script in this repository is a temporary shell-lease helper. It
must be started intentionally, must have a stop file, and must not be installed
as a hidden boot service.

## Preflight

1. Use your Meta Quest workflow or equivalent team process for live headset
   coordination.
2. Enable WiFi ADB from an already authorized route, such as USB ADB or the
   headset's own wireless-debugging pairing UI.
3. Keep the controller or hand input available. Quest launch-check prompts can
   block an otherwise valid launch until accepted.
4. Install Termux packages in the sidecar:

```sh
pkg update
pkg install android-tools openjdk-17 aapt2 d8 apksigner rust cmake ninja clang make git
```

Package names can vary by Termux repository state. Record the exact package
versions in private run evidence; publish only the generalized result.

## WiFi ADB Gate

From Termux, connect to the already enabled or paired ADB endpoint:

```sh
adb connect 127.0.0.1:5555
adb -s 127.0.0.1:5555 shell id
```

Pass condition:

```text
uid=2000(shell)
```

If this returns an app UID or cannot connect, the sidecar does not have ADB
shell authority. Stop and fix the external authorization route before install,
launch, logcat, or wake-state work.

Do not substitute Termux:Boot or a pre-granted ordinary helper APK for this
gate. Current public-safe lab evidence says those routes can at most provide
status evidence after reboot; they did not reopen classic WiFi ADB or create a
new shell lease.

## Temporary Keep-Awake Loop

Start the watchdog only for an attended lab run:

```sh
sh scripts/wifi-adb-keepawake-watchdog.sh
```

For a background run, keep the process visible in your terminal history and
record its pid:

```sh
nohup sh scripts/wifi-adb-keepawake-watchdog.sh > "$HOME/quest-lab/watchdogs/wifi-adb-keepawake.log" 2>&1 &
echo "$!" > "$HOME/quest-lab/watchdogs/wifi-adb-keepawake.pid"
```

Status is written to:

```text
$HOME/quest-lab/watchdogs/wifi-adb-keepawake.status
```

Stop it with:

```sh
touch "$HOME/quest-lab/watchdogs/stop-wifi-adb-keepawake"
```

This loop calls `adb connect`, verifies `uid=2000(shell)`, applies
`svc power stayon true`, sends `KEYCODE_WAKEUP`, and records a small power
state summary. It does not create ADB authority and it does not survive reboot.

## Android Platform Jar

AAPT2 and `javac` need an Android SDK platform `android.jar`.

Do not commit `android.jar` to this repository. Put a user-provided SDK
platform jar in a sidecar path such as:

```text
$HOME/quest-lab/android-sdk/platforms/android-33/android.jar
```

Then set:

```sh
export ANDROID_JAR="$HOME/quest-lab/android-sdk/platforms/android-33/android.jar"
```

The public lesson is that a known-good SDK platform jar is an input to the
on-device build. The jar itself is not a repository artifact.

## Build, Install, Launch

Build the source-only smoke APK:

```sh
sh scripts/build-minimal-android-apk-on-device.sh
```

Build and install through the authorized loopback ADB endpoint:

```sh
INSTALL=1 sh scripts/build-minimal-android-apk-on-device.sh
```

Build, install, and launch:

```sh
INSTALL=1 LAUNCH=1 sh scripts/build-minimal-android-apk-on-device.sh
```

Expected launch result is a simple white Android panel with public smoke text.
If Quest shows a launch-check or controller prompt, satisfy it manually and
record that as operator-gated evidence rather than an app build failure.

## Git-Backed APK Flows

Git can participate in two safe ways:

- source route: clone or pull source, build locally in Termux, then install the
  generated APK through authorized ADB;
- artifact route: download a release asset or CI artifact referenced by Git
  metadata, verify its hash/provenance, then install through authorized ADB.

Do not commit APKs to ordinary Git history. Prefer source, release artifacts,
or CI artifacts with checksums and release notes.

Example source route:

```sh
git clone https://example.invalid/public/project.git
cd project
sh scripts/build-minimal-android-apk-on-device.sh
adb -s 127.0.0.1:5555 install -r build/on-device-smoke-apk/smoke-debug.apk
adb -s 127.0.0.1:5555 shell am start -W -n org.questtermuxlab.ondevice.smoke/.MainActivity
```

Example artifact route:

```sh
git clone https://example.invalid/public/project-metadata.git
cd project-metadata
# Download the documented release APK through your normal authenticated or
# public release channel, then verify its checksum before install.
adb -s 127.0.0.1:5555 install -r downloaded-release.apk
```

Keep release APKs, debug keystores, idsig files, and downloaded artifacts out
of this repository.

## Cleanup

```sh
touch "$HOME/quest-lab/watchdogs/stop-wifi-adb-keepawake"
adb -s 127.0.0.1:5555 uninstall org.questtermuxlab.ondevice.smoke || true
adb disconnect 127.0.0.1:5555 || true
```

If the workflow that enabled WiFi ADB wants to return to USB-only ADB, that
workflow should own the reset. Do not assume the Termux sidecar can restore
the original transport state after reboot or adbd restart.

## Evidence To Publish

Publish only sanitized evidence:

- tool categories and pass/partial/fail classification;
- authority boundary;
- whether the ADB gate returned shell UID;
- whether the smoke panel became visible;
- whether launch was blocked by a protected prompt or controller requirement;
- whether cleanup was attempted and verified.

Keep private:

- raw logs;
- real device serials and network addresses;
- package IDs from downstream apps;
- screenshots;
- generated APKs, idsig files, debug keystores, platform jars, and local run
  roots.
