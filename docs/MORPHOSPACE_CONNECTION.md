# Rusty Morphospace Connection

Quest Termux Lab is related to Rusty Morphospace, but it is not a Morphospace
core layer.

The clean relationship is:

- `quest-termux-lab`: public MIT lab/reference material for Termux,
  Termux:X11, Proot, localhost dashboards, VNC, outbound fleet-agent models,
  and peer-mesh preparation on Quest.
- `rusty-quest-sidecar-mesh`: AGPL Rusty Morphospace integration lane under
  Rusty Quest. It consumes declared public-safe lab artifacts, checks drift,
  and packages advisory sidecar evidence for future Manifold review.
- Rusty Manifold: future owner of accepted command/session/lease/registry,
  route, revision, and audit state.
- Rusty Lattice: future owner only if a generic situated-relation contract
  emerges from the lab evidence.
- Rusty Hostess or other operator workflows: future downstream consumers only
  after Manifold accepted state or an explicit operator request.

## Keep As-Is

Keep this repository named and scoped as Quest Termux Lab. The Termux family is
an upstream/user-installed Android and Linux-userland toolset, not a Rusty
module. Renaming this repo into Morphospace would blur an important boundary:
the lab discovers capabilities and failure modes; Morphospace-owned repos
decide which sanitized contracts become part of the architecture.

The MIT license is also intentional. It lets the lab remain a broadly reusable
public runbook and fixture source while Morphospace-owned integration source
stays AGPL-first in the Rusty repos that accept or transform the evidence.

## What May Flow Into Morphospace

Reusable findings can be promoted when they are sanitized, bounded, and mapped
to the right owner:

- Quest platform constraints and sidecar profiles belong under Rusty Quest.
- Sidecar status, public-lab intake, handoff packages, and boundary reviews
  belong in `rusty-quest-sidecar-mesh`.
- Accepted command/session/route behavior belongs in Rusty Manifold.
- Generic pose, reference-space, frame-state, view-set, calibration, or spatial
  input lessons belong in Rusty Lattice.
- Host recovery and validation descriptors belong in Rusty Hostess or another
  explicit operator workflow lane.

## What Should Not Flow Directly

Do not promote raw live evidence, endpoint values, device identifiers, logs,
screenshots, package identities, pairing material, shell commands, install
requests, launch requests, or private network details into public Morphospace
repos.

Do not turn Termux into:

- Manifold authority;
- Android shell authority;
- recovery authority;
- a hidden watchdog;
- a cross-headset ADB router;
- an XR runtime, compositor, or tracked-space authority;
- the primary operational control plane.

## Current Bridge

The current bridge is the public-lab artifact intake in
`rusty-quest-sidecar-mesh`. That bridge reads declared public-safe fixture
reports from this repo, compares drift, and keeps the result advisory. It does
not copy raw evidence, execute lab validators, approve live work, open sockets,
use ADB, install apps, launch apps, or mutate Manifold state.
