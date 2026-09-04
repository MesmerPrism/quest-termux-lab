# Third-party dependencies

This example is MIT-licensed source, but it integrates user-installed and
build-resolved upstream components. Their own licenses and terms continue to
apply. The repository does not redistribute their APKs, binaries, platform
jars, credentials, or signing material.

| Component | Role | How it is obtained | Repository treatment |
| --- | --- | --- | --- |
| Meta Spatial SDK `0.13.2` | Spatial panel runtime | Gradle from Meta's documented repository path | Referenced as a build dependency; not vendored. Subject to Meta's applicable SDK and developer terms. |
| Android Gradle Plugin `8.11.1` | Android build | Gradle plugin portal/Google repository | Referenced by version; not vendored. |
| Kotlin Android plugin `2.1.0` | Kotlin compilation | Gradle plugin portal | Referenced by version; not vendored. Kotlin is Apache-2.0 upstream. |
| AndroidX Core `1.15.0` | Android compatibility APIs | Google Maven | Referenced by version; not vendored. AndroidX source is Apache-2.0 upstream. |
| JUnit `4.13.2` | Host unit tests | Maven Central | Test-only dependency; not vendored. See the upstream JUnit license. |
| Node.js `20+` | Typed sidecar runtime | User-installed Termux package or host runtime | The sidecar uses Node built-ins and has no npm runtime dependencies. |
| Codex CLI | Bounded agent edit | Installed and authenticated visibly by the operator | Executed as an external tool; no authentication state or binary is stored here. |
| Git and GitHub CLI | Local history and optional draft PR | User-installed Termux packages | Executed as external tools; GitHub authentication remains in operator-owned Termux storage. |
| OpenJDK, AAPT2, D8, zipalign, apksigner, Android platform jar | Source-only demo APK build | User-provided Termux/Android toolchain | External build inputs. The platform jar, tool binaries, keystore, and generated APK remain outside Git. |
| ADB client | Explicit install and launch gate | User-installed Termux Android tools | Used only after selecting an authorized target and verifying Android shell UID `2000`. Pairing material is never part of the example. |

Review the upstream license and terms for the exact versions installed in a
live environment. Generated Gradle metadata and reports may contain more
detailed transitive dependency information, but they are build output and must
not be committed.
