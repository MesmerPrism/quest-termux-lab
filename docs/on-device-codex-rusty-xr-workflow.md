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
  external workflow that owns those operations.

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
3. Public patch: create a branch in this repo, ask Codex to make a small
   public-safe runbook, schema, or synthetic-fixture change, then review the
   diff before any push.
4. Validation: run the public boundary scan and compile checks. Do not stage
   raw device paths, serials, screenshots, logs, package identities, APKs,
   credentials, or generated artifacts.
5. Build/deploy: defer until the public patch lane is clean. If later build or
   deploy steps are attempted, route them through the external Quest workflow
   unless an explicit, reversible ADB authority gate is being tested.

## Cleanup

Stop any sidecar service, remove temporary port forwards, leave generated
artifacts out of the repo, and record whether the checked-out branch contains a
reviewable patch, an empty diff, or a classified blocker.
