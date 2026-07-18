# Codex CLI + Git + Quest APK round-trip showcase

This is the operator-visible command shape proven by the public
[`spatial-codex-quest-apk-showcase`](https://github.com/MesmerPrism/spatial-codex-quest-apk-showcase)
repository. It demonstrates both directions of Git transport and keeps source
history separate from generated APKs and private device evidence.

The corresponding on-device draft pull request is
[`spatial-codex-quest-apk-showcase#1`](https://github.com/MesmerPrism/spatial-codex-quest-apk-showcase/pull/1).

## 1. Authenticate visibly

Run the login flows from a visible Termux session. Do not collect credentials
in an APK or pass them through a workbench prompt.

```sh
codex login --device-auth
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git --hostname github.com
codex login status
gh auth status --hostname github.com
```

On Termux, GitHub CLI may fall back to a mode-`600` plaintext token file in
Termux-private storage. That is acceptable for the lab proof but is readable
by processes running with the same Termux application identity, including a
broadly permitted Codex process.

## 2. Prove the inbound Git path

Clone once, then require a fast-forward pull before building updated source:

```sh
mkdir -p "$HOME/codex-workspaces/showcase"
cd "$HOME/codex-workspaces/showcase"
git clone https://github.com/MesmerPrism/spatial-codex-quest-apk-showcase.git
cd spatial-codex-quest-apk-showcase
git pull --ff-only origin main
git status --short
```

The status must be clean. Record the pulled commit privately and confirm that
the intended source change is present before accepting it as a build input.

## 3. Compile and verify the pulled source on Quest

The project is deliberately Gradle-free. It uses public Termux packages for
Java compilation, resource linking, DEX generation, and APK signing:

```sh
export ANDROID_JAR="$HOME/quest-lab/android-sdk/platforms/android-33/android.jar"
export OUT_DIR="$HOME/codex-workspaces/artifacts/pulled-main-$(date +%Y%m%d-%H%M%S)"
sh ./build.sh
apksigner verify --verbose --print-certs \
  "$OUT_DIR/spatial-codex-demo-v1.0.0.apk"
sha256sum "$OUT_DIR/spatial-codex-demo-v1.0.0.apk"
```

Keep the platform jar, debug keystore, APK, signature output, and exact hash
outside Git.

## 4. Gate install and launch

Set `ADB_TARGET` only after inspecting `adb devices`. Do not select the first
target implicitly, and stop if the identity gate does not return Android shell
UID `2000`.

```sh
export ADB_TARGET='<explicit-authorized-target>'
adb -s "$ADB_TARGET" shell id
adb -s "$ADB_TARGET" install -r -g \
  "$OUT_DIR/spatial-codex-demo-v1.0.0.apk"
adb -s "$ADB_TARGET" shell am start -W -n \
  io.github.mesmerprism.questtermuxlab.codexdemo/.MainActivity
adb -s "$ADB_TARGET" shell dumpsys package \
  io.github.mesmerprism.questtermuxlab.codexdemo
adb -s "$ADB_TARGET" shell pidof \
  io.github.mesmerprism.questtermuxlab.codexdemo
```

Accept the run only when launch reports `Status: ok`, the process remains
running, installed version readback matches the artifact metadata, and the
bounded package log window contains no fatal.

## 5. Ask Codex for one bounded change

Create a feature branch first. Horizon OS/Termux cannot provide the Linux
bubblewrap interface required by the normal `workspace-write` sandbox, so the
proof uses `danger-full-access`. Review the exact diff because this mode is not
an operating-system filesystem boundary.

```sh
git switch -c codex/quest-apk-showcase-v1

codex -a never exec --json -s danger-full-access -C "$PWD" \
  "Edit only MainActivity.java. Make the requested showcase text change. Do not commit and do not build."

git status --short
git diff --check
git diff -- src/io/github/mesmerprism/questtermuxlab/codexdemo/MainActivity.java
```

Reject the turn if an unexpected file changed.

## 6. Version and commit reviewed source

`version.properties` is the version authority. Increment both fields, review
the combined diff, and commit only the selected source and version file:

```sh
sed -i \
  's/^VERSION_CODE=10$/VERSION_CODE=11/; s/^VERSION_NAME=1.0.0$/VERSION_NAME=1.0.1/' \
  version.properties

git diff --check
git diff --stat
git add -- \
  src/io/github/mesmerprism/questtermuxlab/codexdemo/MainActivity.java \
  version.properties
git commit -m 'Build Codex and Git APK showcase on Quest'
git status --short
```

Build the candidate into a fresh output directory and bind its metadata to the
clean commit in the private run record:

```sh
export OUT_DIR="$HOME/codex-workspaces/artifacts/candidate-$(date +%Y%m%d-%H%M%S)"
sh ./build.sh
apksigner verify --verbose --print-certs \
  "$OUT_DIR/spatial-codex-demo-v1.0.1.apk"
sha256sum "$OUT_DIR/spatial-codex-demo-v1.0.1.apk"
git rev-parse HEAD
git status --short
```

## 7. Prove the outbound Git path

Push only the current feature branch and create a fully specified draft pull
request:

```sh
branch="$(git branch --show-current)"
git push --set-upstream origin "$branch"
gh pr create \
  --draft \
  --base main \
  --head "$branch" \
  --title '[codex] Build and deploy a versioned Quest APK on-device' \
  --body 'Created on Quest after a reviewed Codex change and clean candidate build.'
```

Finally, repeat the exact-target hash, shell-UID, install, launch, installed
version, process, and bounded-fatal gates for the candidate. The demonstrated
round trip upgraded the installed app from `1.0.0` to `1.0.1` and produced the
draft PR linked above.

## Cleanup boundary

Stop the tested application and any workbench-owned localhost proxy when the
run is complete. Remove run-owned ADB forwards and release shared-device
leases. Uninstalling packages or deleting Termux-private workspaces, toolchains,
authentication state, keys, or artifacts requires a separate operator choice.
