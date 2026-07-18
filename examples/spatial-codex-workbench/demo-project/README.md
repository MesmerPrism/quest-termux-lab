# Spatial Codex demo project

This tiny source-only Android application is the reproducible workbench target.
It intentionally avoids Gradle so a Quest Termux sidecar can build it with
Java, AAPT2, D8, and apksigner. If `zipalign` is available the build uses it;
the Termux package profile treats alignment as an optional optimization and
still requires signing verification plus live package-manager acceptance.

Codex edits `MainActivity.java`. The typed workbench version action owns
`version.properties`. Generated APKs and the external debug keystore are never
committed.

```sh
ANDROID_JAR="$HOME/quest-lab/android-sdk/platforms/android-33/android.jar" \
  OUT_DIR="$HOME/codex-workspaces/artifacts/manual-build" \
  sh build.sh
```
