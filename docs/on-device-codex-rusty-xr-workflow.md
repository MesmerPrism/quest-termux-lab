# On-Device Codex Engineering Workflow

This runbook describes a public-safe way to test Codex CLI from a Quest
Termux or Proot sidecar. It assumes Termux is a normal Android app that can run
developer tools, not an Android shell, HOME surface, broker, watchdog, or
deployment authority.

## Scope

Use this lane to prove:

- Codex CLI can start in the sidecar.
- The filesystem and sandbox behavior are understood.
- A small public repo patch can be produced and validated.
- Build, install, launch, screenshot, and logcat authority stays with the
  external workflow that owns those operations, unless a separate
  operator-approved WiFi ADB lease is being tested.

Do not use this lane for hidden ADB authorization, root, stored pairing data,
automatic HOME changes, unattended deployment, high-rate media transport,
keystores, generated APK storage, or raw device evidence.

## Authority Split

Termux or Proot owns the local Linux process, package cache, checked-out repo,
and temporary Codex home. Codex owns only the edit and validation process inside
the checked-out workspace. The external Quest workflow owns ADB, installs,
launches, screenshots, logcat, port forwarding, and recovery. Any broker or XR
runtime involved in later phases remains the runtime authority.

## Records

Use `schemas/codex-xr-workflow-evidence.schema.json` for synthetic or redacted
public records. Keep raw device outputs in a private run root. The five record
kinds are:

- `codex_xr_environment.v1`
- `codex_xr_step.v1`
- `codex_xr_toolchain_classification.v1`
- `codex_xr_agent_patch.v1`
- `codex_xr_deploy_attempt.v1`

## Phase Gates

1. Environment: record app-side Linux runtime, shell, Python, Git, Node, npm,
   storage, memory, process limits, and whether a Proot distribution is
   available.
2. Codex: run `codex --version`, then classify install method, authentication
   status, and sandbox behavior. Use a dedicated Codex home outside the repo.
   If read-only or workspace-write sandbox helpers fail on Android or Proot,
   classify sandboxing as best-effort. Use danger-full-access only in a
   throwaway or public-safe checkout, with operator review, the dedicated Codex
   home outside the repo, and the public boundary scan.
3. Public patch: create a branch in this repo, ask Codex to make a small
   public-safe runbook, schema, or synthetic-fixture change, then review the
   diff before any push.
4. Validation: run the public boundary scan and compile checks. Do not stage
   raw device paths, serials, screenshots, logs, package identities, APKs,
   credentials, or generated artifacts.
5. Build/deploy: start only after the public patch lane is clean. The first
   positive on-device build/deploy lane uses an externally enabled or paired
   WiFi ADB endpoint, then requires Termux `adb shell id` to report Android
   shell UID before any install or launch command. Keep generated APKs,
   keystores, platform jars, logs, screenshots, and package-manager output out
   of Git. See `docs/on-device-apk-build-install-launch.md`.

## Cleanup

Stop any sidecar service, remove temporary port forwards, leave generated
artifacts out of the repo, and record whether the checked-out branch contains a
reviewable patch, an empty diff, or a classified blocker.
