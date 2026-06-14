# Quest Termux Lab

Quest Termux Lab is a public, MIT-licensed place to explore Termux, Termux:X11,
Proot, local dashboards, and localhost-only VNC as developer lab sidecars on
Meta Quest headsets.

The repository is not a replacement launcher, not a managed-device system, not
a broker/runtime authority, and not a way to bypass Android or Quest security
boundaries. It collects small, auditable recipes and data models that can later
inform downstream XR tools.

## Rusty Morphospace Relationship

Quest Termux Lab should stay as a public MIT lab/reference repo. It is related
to Rusty Morphospace through the Rusty Quest sidecar lane, but it is not itself
a Morphospace core layer or runtime authority.

The Morphospace bridge is
[`rusty-quest-sidecar-mesh`](https://github.com/MesmerPrism/rusty-quest-sidecar-mesh):
that AGPL repo consumes selected public-safe lab artifacts, checks drift, and
packages advisory sidecar evidence for future Rusty Manifold review. This repo
keeps the upstream Termux-family experiments, `quest-termux-lab.*` schemas,
runbooks, and synthetic fixtures separate from `rusty.quest.sidecar.*`
integration contracts.

See [`docs/MORPHOSPACE_CONNECTION.md`](docs/MORPHOSPACE_CONNECTION.md) for the
full boundary.

## Current Scope

- Data-only session recipe and evidence schemas.
- Synthetic examples for Termux:X11, Proot, and localhost VNC flows.
- Public-safe runbooks for capability testing and cleanup.
- Small host-side helper tools that do not require private project state.
- Localhost-only host helpers for VNC screenshots, direct stream frame pulls,
  and browser-readable MJPEG streams.
- A small Android 2D panel viewer example for showing the localhost MJPEG
  stream in a landscape Quest panel.
- Public-safe native-wide Termux:X11 preference probes, evidence schema,
  capture helper, and patch scaffolds for a possible Quest-flavored activity.
- Public-safe on-device Codex engineering runbooks and synthetic evidence
  records for treating Termux or Proot as a normal-app developer sidecar.
- Public-safe on-device APK build/install/launch guidance for an
  operator-authorized WiFi ADB loopback route.
- Public-safe cross-package XR questionnaire panel handoff guidance for testing
  a foreground XR app launching a separate 2D panel app and returning to the
  same XR app with a caller-owned `content://` result URI, without ADB,
  force-stop, package killing, public shared storage, Termux file drops, or Meta
  menu navigation in the product path.
- Public-safe outbound fleet-agent schemas, examples, and simulator tooling
  for Termux agents that report heartbeats and execute bounded allowlisted
  commands without exposing a headset listener.
- Public-safe peer-gossip preparation for future Termux agent meshes, limited
  to compact status observations, synthetic merge tests, and file-drop round
  simulation.
- Public-safe peer delivery-state modeling for future configured peers,
  limited to pending, accepted, duplicate, rejected, and expired gossip
  delivery status.
- Public-safe configured-peer dispatch planning that decides whether pending
  gossip would use loopback HTTP, file-drop, disabled, missing, expired, or
  terminal routes without sending anything.
- Public-safe file-drop staging plans that turn ready file-drop dispatches
  into deterministic relative inbox filenames without copying files or reading
  gossip bodies.
- Public-safe file-drop copy dry runs that consume staging reports and
  synthetic outcomes, then report simulated copy results without copying files,
  creating inbox directories, or reading gossip bodies.
- Public-safe file-drop inbox intake dry runs that consume copy dry-run reports
  and declared synthetic inbox entries, then validate explicit public fixture
  envelopes without scanning inbox directories or touching devices.
- Public-safe peer send dry runs that consume delivery state, route config, and
  synthetic outcomes, then write updated sender-side delivery state without
  opening sockets, copying files, or embedding gossip bodies.
- Public-safe peer retry/backoff planning that decides whether pending
  deliveries are due, waiting, expired, terminal, non-retryable, or over max
  attempts without sending anything.
- Public-safe peer route-health inference that combines configured routes,
  synthetic send dry-run reports, and retry plans into healthy, degraded,
  unavailable, disabled, or unknown status without probing peers.
- Public-safe peer topology reports that compare expected agents, configured
  routes, and synthetic route-health evidence into ready, manual-review, or
  blocked coverage without discovering peers.
- Public-safe route-health history that summarizes repeated synthetic
  route-health reports into per-route stability trends without live monitoring.
- Public-safe live-lab readiness reports that evaluate route-health history
  against a policy before any private configured-peer gossip experiment.
- Public-safe lab bundle reports that package route config, topology,
  route-health history, and readiness evidence into a blocked, manual-review,
  or synthetic-ready preflight report without enabling live transport.
- Public-safe peer trust reports that evaluate configured peers, simulator
  route modes, bundle status, gossip schema, sample envelope TTL, and operator
  review boundaries before any private LAN experiment.
- Public-safe peer rehearsal reports that package bundle/trust status and
  private evidence requirements into a blocked, manual-review, or
  rehearsal-ready plan without selecting endpoints or running transport.
- Public-safe evidence intake reports that validate rehearsal, trust, gossip
  receipt, route-health, route-history, and cleanup artifacts without replaying
  or performing a live run.
- Public-safe peer cleanup plans that declare required cleanup categories and
  expected evidence slots before any private live run, without executing
  cleanup or touching devices.
- Public-safe peer scorecards that summarize readiness, bundle, trust,
  rehearsal, evidence-intake, route-health, route-history, and cleanup status
  into a blocked, manual-review, or synthetic-clear operator view.
- Public-safe scorecard history reports that compare scorecards over time and
  surface resolved, new, persistent, improving, and regressing pressure points
  without becoming a live monitor.
- Public-safe scorecard regression reports that evaluate scorecard history
  against an explicit policy before treating repeated synthetic evidence as
  stable.
- Public-safe repeated-scorecard fixtures that generate a clearly synthetic
  two-scorecard clear path, scorecard history, and regression-clear report
  without proving live readiness.
- Public-safe preflight clear fixtures that generate a clearly synthetic
  route-health/history, readiness, topology, and lab-bundle clear path without
  proving live readiness.
- Public-safe review bundles that verify the sanitized peer-mesh artifacts,
  docs, tools, tests, schemas, and terminal status gates are present and
  reviewable before any private live run.
- Public-safe repeated-scorecard clear review bundles that keep the generated
  happy-path fixture review separate from the intentionally blocked baseline.
- Public-safe preflight clear review bundles that keep the generated
  route-preflight happy-path fixture review separate from the intentionally
  blocked baseline.
- Public-safe private-run handoff reports that declare the private evidence
  slots a live run would need without selecting endpoints or approving live
  work.
- Public-safe private evidence checklists that convert handoff slots into
  pending private-run evidence items without collecting evidence.
- Public-safe private evidence redaction reports that declare private-only and
  sanitized-derivative policy before any private evidence can move toward
  public artifacts.
- Public-safe fixture indexes that summarize the expected blocked baseline,
  ready clear fixture, and blocked private handoff/checklist/redaction lanes.
- Public-safe public package indexes that verify expected fixture states,
  required docs/tools/tests/schemas/examples, and declared validation evidence
  before public review without proving live readiness.
- Public-safe private import plans that describe which sanitized derivatives
  could later be imported after private evidence and redaction readiness exist,
  without reading private evidence.
- Public-safe private result placeholders that declare future public result
  slots while keeping private-only evidence private and sanitized derivatives
  blocked until import readiness exists.
- Public-safe private result acceptance reports that decide whether future
  sanitized derivative result slots could later accept public-safe artifacts
  after private review, without importing artifacts.

## Current Milestone

The first landscape-desktop milestone is complete: Termux:X11 can run a
1280x720 desktop, the localhost VNC/MJPEG bridge can stream it, and the Android
viewer can show the full frame in a wide Quest panel.

This is still a proof of concept. Direct interaction currently works through
the foreground Termux:X11 panel, while the larger viewer is observation-only
and slower because it receives an MJPEG stream rather than the native X11
surface.

The first headless-sidecar milestone is also positive: a Termux-owned
localhost JSON command service can continue answering allowlisted commands
while another headset app is foregrounded. This is the more relevant route for
XR apps that need Linux tools or scripts without showing a desktop.

The current native-wide surface lane is documented in
`docs/termux-x11-native-wide-surface.md`. It tests upstream Termux:X11
preferences before any fork and keeps X-root evidence, Android activity panel
evidence, and fallback viewer evidence separate.

The first preference-only native-wide pass is partial-positive: wide X roots up
to 2560x1440 can be created, and exact 1280x720 can render a visible XFCE
desktop through the native Termux:X11 surface. The remaining blocker is
ergonomics: activity/surface alignment and manual input still need their own
gate.

The first broker-feedback sidecar pass is also positive: a Termux-owned
Python/Linux process can poll a broker-owned status/stream registry, run small
bounded processing work, and publish a low-rate diagnostic feedback event while
an XR app remains foregrounded. This keeps Termux in the processor-sidecar
role; the broker remains the stream/module authority, and high-rate media or
sensor ownership stays out of this repository's recipe scope.

The first on-device APK loop milestone is positive for a baseline smoke app:
after an external workflow enabled or paired WiFi ADB, Termux connected back to
the headset over loopback, received shell authority through that approved ADB
session, built a small Android Activity APK with source-only inputs, signed it
locally, installed it, and launched it into a visible Quest panel. This does
not yet prove a Makepad build or OpenXR rendering. See
`docs/on-device-apk-build-install-launch.md`.

A new cross-package XR questionnaire panel handoff note is available at
`docs/xr-questionnaire-panel-handoff.md`, with a compact test checklist at
`examples/session-recipe.xr-questionnaire-panel-handoff.json`. It describes a
reusable app-to-app contract where any cooperating foreground XR app opens a
separate 2D questionnaire panel, supplies a caller-owned `content://` result
URI for answer JSON, and supplies a return route back to the same XR app. This
is currently a design/test recipe, not a published live-device pass.

A follow-up helper-app probe keeps the reboot boundary in place: a normal
installed helper can receive boot and write its own status after it has been
launched and pre-granted, but it did not restore classic WiFi ADB after reboot.
Termux-local ADB still needs an external or user-authorized ADB bootstrap
before it can connect and receive `uid=2000(shell)`.

The first outbound fleet-control-plane slice is simulator-only and public-safe:
it defines Termux agent manifests, heartbeats, command requests/results, ADB
lease-state records, a small central controller, and an outbound-only Python
agent. It does not touch ADB or a headset unless a later live run explicitly
enables local ADB in the agent config. See
`docs/outbound-fleet-control-plane.md`.

The fleet-agent lane now includes a public-safe shape for
`apk.update_verified`: a Termux agent can accept a signed update manifest,
verify package/version/hash/signing digest/rollout ring against local
allowlists, install through an already authorized loopback WiFi ADB lease, and
report idempotency, rollback state, and central direct-ADB recovery needs. This
is still not a WiFi ADB bootstrap, MDM replacement, root path, or generic
remote shell.

The repeatable off-LAN trigger model is documented in
`docs/internet-triggered-self-update-workflow.md`: publish an update to HTTPS,
queue a bounded command on an internet-reachable controller, and let each
headset's Termux agent poll outbound and install locally if its loopback ADB
gate passes. No same-WiFi operator device is required for the trigger.

Remote operation commands are now scoped by
`quest-termux-lab.remote-session-lease.v1`. Only passive `agent.status` and
`agent.capabilities` are lease-free; update, launch, logcat, UIAutomator, and
visual-preview commands require a current lease ID plus their normal local
allowlists and ADB shell gates. The controller remains a typed-command
simulator, not an ADB proxy or browser shell.

A later live Quest pass added two operational details for this lane. Termux
ADB subprocesses need a writable temporary directory such as `$PREFIX/tmp`,
because a non-interactive app context may not have `/tmp`. Also, APKs should be
downloaded or staged in Termux-private storage or another path the Termux
process can read; do not assume a host-pushed public shared-storage file is
readable from every Termux execution context.

A normal helper-app restart path is also now live-tested. A pre-granted helper
Activity can call Termux's `RunCommandService` with `startForegroundService()`
and restart the fixed fleet-agent command after `com.termux` was force-stopped.
Fresh controller heartbeats then showed loopback ADB available with
`uid=2000(shell)`. This is useful operator-visible recovery, not WiFi ADB
bootstrap, reboot-durable management, or helper-owned install authority.

The managed-device research note at `docs/managed-device-owner-options.md`
summarizes the current production direction: Android phones should use fully
managed / dedicated Android Enterprise device owner where possible. Quest
fleets should use only a vendor-confirmed management path: Meta's 2026 update
stops selling Horizon managed services and commercial Quest SKUs while support
continues through 2030, and third-party XR MDM enrollment through HMS must be
verified against the current Meta signup flow and vendor support terms. The
Termux fleet lane remains a lab and break-glass path.

The first peer-mesh slice is also simulator-only: it defines gossip envelopes,
peer summaries, a merge tool, and tests for stale-state and forbidden-message
handling. It does not open peer sockets, relay commands, or use cross-headset
ADB. See `docs/peer-mesh-preparation.md`.

The peer-mesh simulator can now derive a gossip envelope from a fleet
heartbeat, merge file-drop inbox directories, and prepare TTL-limited relay
envelopes while stripping or rejecting command-like, shell-like, credential,
and ADB-target fields.

The peer-mesh round simulator adds a dry-run harness for multiple synthetic
Termux agents. It creates per-peer inbox/outbox folders, delivers configured
status gossip links, performs bounded TTL relay passes, and writes per-peer
summaries plus a round report. It still does not open peer sockets, discover
devices, run shell commands, use ADB, or relay central commands.

The peer HTTP simulator adds the next transport-shaped dry run: a
loopback-only HTTP endpoint that accepts `peer-gossip-envelope.v1` messages and
returns an HTTP summary wrapper. It rejects heartbeats, command routes, shell
fields, ADB targets, pairing material, install/launch operations, and
non-loopback binding in the public fixture. It also returns explicit gossip
receipts, treats exact duplicate message IDs as idempotent, and rejects same-ID
content changes as replay conflicts inside a bounded replay window.

The peer delivery-state simulator adds the sender-side dry run: it tracks
pending gossip deliveries, applies HTTP receipts, records duplicate or rejected
outcomes, and expires undelivered entries. It stores message IDs and delivery
status only; it does not store gossip bodies, commands, shell text, ADB
targets, pairing material, install requests, or launch requests.

The peer dispatch-plan simulator adds the next sender-side step: it combines
delivery state with configured peer routes and produces a no-send plan. A
pending delivery can become ready for loopback HTTP or relative file-drop, or
be marked as expired, skipped terminal, route disabled, or missing route.

The peer file-drop staging planner adds the no-copy file-transport preparation
step: it consumes route config and delivery state, reuses the dispatch plan,
and produces a deterministic relative inbox filename only for ready
`file_drop_simulator` dispatches. It still does not copy files, read gossip
bodies, send gossip, open sockets, discover peers, use ADB, or launch apps.

The peer file-drop copy dry-run report adds synthetic outcome modeling for the
planned file-drop paths. It consumes the staging report plus explicit synthetic
copy outcomes and reports copied, duplicate, missing-source, write-blocked, or
missing-outcome states without copying files, creating inbox directories,
reading gossip bodies, sending gossip, opening sockets, discovering peers,
using ADB, or launching apps.

The peer file-drop inbox intake report adds the receiver-side synthetic check:
it consumes the copy dry-run report plus a declared inbox manifest, reads only
explicit public fixture envelopes under the artifact root, and reports accepted,
duplicate, missing-file, unreadable, invalid-envelope, or not-copied states. It
does not scan inbox directories, copy files, send gossip, discover peers, use
ADB, execute commands, or launch apps.

The peer send dry-run simulator adds a complete no-send sender loop: it
combines delivery state, route config, and synthetic outcomes, then writes a
report and updated delivery state for accepted, duplicate, rejected,
no-response, and not-sent cases. It still does not open sockets, copy files,
discover peers, send gossip, carry gossip bodies, use ADB, or launch apps.

The peer retry/backoff planner adds sender-side scheduling metadata: it
combines delivery state with a synthetic retry policy and reports due-now,
waiting-backoff, max-attempts, non-retryable, expired, and terminal outcomes.
It is a planner only, not a send loop or live route-health probe.

The peer route-health report adds the next operator-facing view: it combines
configured routes with synthetic send dry-run and retry-plan evidence, then
marks each configured route as healthy, degraded, unavailable, disabled, or
unknown. It is inference over simulator evidence only, not peer probing or LAN
transport validation.

The peer topology report adds route coverage analysis over an expected agent
set. The current public fixture is `topology_blocked` because one expected
route is configured but still `unknown`; it is a coverage report, not live
peer discovery.

The peer route-health history report adds the first trend layer: it aggregates
one or more synthetic route-health reports and records each route's latest
status, status counts, transitions, and trend. This is file-friendly evidence
aggregation only, not live monitoring.

The peer live-lab readiness report adds a preflight gate for future private
configured-peer gossip experiments. It evaluates synthetic route-health history
against a policy and reports `ready`, `manual_review`, or `not_ready`; it does
not approve live work or start transport.

The peer lab bundle report adds a packaging gate around the preflight evidence:
it checks route config, topology, route-health history, and readiness report
consistency against an experiment manifest and reports `blocked`,
`manual_review`, or `synthetic_ready`. This is still synthetic evidence only,
not live approval.

The peer trust report adds a configured-peer trust gate: it checks allowed
agent IDs, allowed simulator transport modes, required gossip-only schema,
sample envelope hop TTL, and lab bundle status before any private LAN endpoint
setup. The public fixture is deliberately `untrusted` while readiness and
bundle status remain blocked.

The peer rehearsal report adds the next dry-run planning layer: it combines
bundle and trust status with a phase list for future private evidence such as
operator review, endpoint selection records, gossip receipts, route health,
route history, and cleanup records. It is a rehearsal plan only.

The peer evidence intake report adds the post-run evidence shape for future
private experiments. It validates the schemas and identities of rehearsal,
trust, gossip receipt, route-health, route-history, and cleanup artifacts, then
reports `accepted`, `manual_review`, or `rejected`. It does not replay evidence
or perform live work.

The peer scorecard report adds a compact operator-facing summary over the
synthetic evidence stack. It highlights blocked, manual-review, and missing
pressure points across readiness, bundle, trust, rehearsal, evidence intake,
route health, route history, and cleanup without changing any underlying state.

The peer scorecard history report compares one or more scorecards in timestamp
order. It reports first-to-last status, trend, pressure-point deltas, and last
summary counters, but it does not monitor live peers or approve a live run.

The peer scorecard regression report applies a strict policy to scorecard
history. It can return `regression_clear`, `manual_review`, or
`regression_blocked`, but it remains a synthetic evidence gate and does not
approve live work.

The repeated scorecard fixture generator adds a public-safe happy path for the
scorecard stack: it writes two synthetic-clear scorecards, a stable clear
history, and a `regression_clear` report from sanitized templates. A
`fixture_ready` result means only that the public fixture path is internally
consistent under the declared policy; it is not live fleet readiness.

The preflight clear fixture generator adds a public-safe happy path for the
upstream route preflight stack: it writes two healthy route-health samples, a
stable clear route-health history, a no-manual-gate readiness policy, a
`ready` readiness report, a `topology_ready` topology report, and a
`synthetic_ready` lab bundle report. A `fixture_ready` result means only that
the public preflight gates compose under declared synthetic inputs; it is not
live fleet readiness.

The peer review bundle report packages the sanitized artifact stack for human
or agent review. It verifies expected schemas, file presence, and terminal
status gates without executing validation slots or approving live work.

The repeated-scorecard clear review bundle is a narrower review variant for
the generated happy-path fixture. It verifies the repeated-scorecard fixture
manifest/report, the two synthetic-clear scorecards, the clear history, the
clear regression report, and the related docs/tools/schemas. It can be
`review_ready` while the full baseline review bundle remains
`review_blocked`.

The preflight clear review bundle is the matching narrow review variant for
the generated route-preflight happy path. It verifies the preflight clear
fixture, the two healthy route-health samples, the stable route-health
history, the ready readiness report, the ready topology report, the synthetic
ready lab bundle, and the related docs/tools/schemas. It can be `review_ready`
without changing the blocked full baseline.

The peer cleanup plan adds a pre-run cleanup declaration surface. It verifies
that required cleanup categories are represented: operator review, peer
transport stopped, ephemeral inbox cleanup, ephemeral outbox cleanup, and a
cleanup record. The public fixture is `cleanup_plan_ready`; it does not
execute cleanup, inspect devices, or prove live cleanup happened.

The private-run handoff report consumes the review bundle and declares required
private evidence slots such as operator approval, endpoint selection record,
gossip receipts, route-health report, and cleanup record. It does not include
private endpoint values or any command authority.

The private evidence checklist consumes the handoff report and turns declared
private slots into pending required and optional evidence items. The public
fixture is `checklist_blocked` because the handoff is still blocked; it is a
checklist surface, not a live-run approval or evidence collector.

The private evidence redaction report consumes the checklist and declares
which private evidence kinds must remain private-only and which may produce a
sanitized public derivative. The public fixture is `redaction_blocked` while
the checklist is blocked; it is a policy surface, not a private evidence
reader or sanitizer.

The fixture index summarizes the current public fixture landscape. It can be
`fixture_index_ready` while two groups are blocked because those blocked states
are expected: the full baseline remains blocked and the private evidence lane
remains blocked, while the repeated-scorecard and preflight clear fixtures and
their narrow review bundles remain ready. The cleanup plan lane is also ready
as a public-safe pre-run declaration, the file-drop staging lane is ready as a
public-safe no-copy staging declaration, the file-drop copy dry-run lane is
ready as a public-safe synthetic copy outcome declaration, and the file-drop
inbox intake lane is ready as a public-safe receiver-side envelope validation
declaration.

The public package index summarizes whether the public peer-mesh preparation
stack is coherent enough for public review, including route-health,
route-history, live-lab readiness, topology, and topology-aware lab bundle
coverage. It can be `package_ready` while route-health, readiness, topology,
lab-bundle, and private evidence artifacts are blocked because the package
expectation is that those lanes remain blocked until stronger synthetic or
private evidence exists. It also expects both narrow clear review bundles to
remain `review_ready` and the cleanup plan to remain `cleanup_plan_ready`.
The package also expects the file-drop staging report to remain
`file_drop_staging_ready`, the file-drop copy dry-run report to remain
`file_drop_copy_dry_run_ready`, and the file-drop inbox intake report to remain
`file_drop_inbox_intake_ready`.

The private import plan consumes the package report plus redaction report and
describes which private-only items stay private and which sanitized
derivatives could later be imported. The public fixture is `import_blocked`
because redaction is still blocked; it is an import plan, not a private
evidence reader or live-run approval.

The private result placeholder report consumes the import plan and declares
future public result slots. The public fixture is
`result_placeholders_blocked` because the import plan is blocked; it is a
placeholder surface, not a private evidence reader, sanitizer, or live-run
approval.

The private result acceptance report consumes the result placeholder report and
decides whether future sanitized derivative slots could later accept
public-safe artifacts. The public fixture is `acceptance_blocked` because
result placeholders are still blocked; it is an acceptance gate, not an
artifact importer or private evidence reader.

## Workflow Pairing

Use this repository for Termux/Linux sidecar recipes and sanitized evidence
models. For live headset work, use the public `meta-quest-workflow` skill or
the equivalent team workflow before touching ADB, installing APKs, launching
apps, taking screenshots, collecting logcat, forwarding ports, or relying on
headset-visible state.

The split is intentional:

- `meta-quest-workflow`: device-operation discipline, provider choice,
  readiness checks, capture semantics, and cleanup gates.
- `quest-termux-lab`: Termux, Termux:X11, Proot, local dashboard, and VNC
  sidecar recipes that remain normal Android app workflows.
- `rusty-quest-sidecar-mesh`: Rusty Morphospace's Rusty Quest integration
  bridge for sanitized public-lab artifact intake, sidecar handoff fixtures,
  and future Manifold-facing proposals.

## Non-Goals

- No root, Magisk, bootloader unlock, SELinux changes, or device-owner policy.
- No ADB authorization bypasses or hidden pairing material.
- No APK vendoring.
- No default LAN VNC, SSHD, or persistent remote shell.
- No hidden boot daemon assumptions.
- No high-rate media or XR runtime payload routing through command/control JSON.

## Upstream Projects

Install Termux-family components from their upstream projects and follow their
licenses:

- Termux: https://github.com/termux/termux-app
- Termux:X11: https://github.com/termux/termux-x11
- Termux:Boot: https://github.com/termux/termux-boot
- Proot-Distro: https://github.com/termux/proot-distro

This repository's original code and documentation are MIT licensed. Upstream
Termux-family projects have their own licenses; do not copy their code into
this repository unless license obligations are reviewed.

## Recommended Test Order

0. Activate the Meta Quest workflow for live headset operations and reserve or
   coordinate any shared device, ADB, build, capture, or port resources through
   your team's normal process.
1. Baseline: record device model, Android version, focused surface, package
   state, and recovery route.
2. Termux CLI: verify app UID, package updates, bounded child processes, and
   cleanup.
3. Termux:X11: start a minimal X server and one small client.
4. Native-wide Termux:X11: apply the preference-only probe and capture X-root
   evidence separately from Android activity panel evidence.
5. Proot: run a CLI smoke test, then one small GUI client only after X11 is
   visible and stoppable.
6. Local dashboard: bind to device localhost and consume through an explicit
   host forward.
7. VNC: keep it localhost-only or ADB-forwarded, record direct screenshot or
   live stream endpoint evidence, then stop it.
8. Broker feedback sidecar: poll a broker-owned status/registry surface and
   publish bounded diagnostic feedback through an explicit broker route.
9. Outbound fleet agent: prove simulator heartbeats, command polling, bounded
   results, and no inbound listener before any live multi-headset run.
10. Peer gossip mesh: prove synthetic status merge and forbidden-command
    rejection before adding any peer network transport.
11. Peer HTTP simulator: prove a loopback-only gossip receive/summarize route
    before any configured LAN peer experiment.
12. Peer delivery state: prove pending, accepted, duplicate, rejected, and
    expired delivery outcomes before any live send loop.
13. Peer dispatch plan: prove configured route selection and no-send planning
    before any live send loop.
14. Peer file-drop staging: prove deterministic relative inbox filenames for
    ready file-drop dispatches before copying files or sending gossip.
15. Peer file-drop copy dry run: prove synthetic copy outcomes for planned
    file-drop staging paths before copying files or sending gossip.
16. Peer file-drop inbox intake: prove declared synthetic receiver-side
    envelope validation before scanning inboxes or treating copied files as
    received gossip.
17. Peer send dry run: prove synthetic send outcomes and updated delivery
    state before opening sockets, copying files, or sending gossip.
18. Peer retry/backoff plan: prove retry timing and max-attempt behavior for
    pending gossip deliveries before any live sender loop.
19. Peer route health: infer configured route status from synthetic send and
    retry evidence before adding live route probes.
20. Peer topology: compare expected agents, configured routes, and synthetic
    route-health evidence before treating the mesh as covered.
21. Peer route-health history: summarize repeated synthetic route-health
    reports into stability trends before live monitoring.
22. Peer live-lab readiness: evaluate synthetic history against an explicit
    policy before any private configured-peer LAN experiment.
23. Peer lab bundle: package route config, topology, route-health history, and
    readiness evidence into one preflight report before any private LAN
    endpoint setup.
24. Peer trust gate: verify configured peer IDs, simulator route modes, gossip
    schema, sample TTL, and bundle status before private LAN endpoint setup.
25. Peer rehearsal: package bundle/trust status and private evidence
    requirements into a no-transport live-run rehearsal report.
26. Peer evidence intake: validate post-run evidence artifacts without
    replaying, probing, selecting endpoints, or running transport.
27. Peer cleanup plan: declare cleanup categories and evidence slots before any
    private run, without executing cleanup.
28. Peer scorecard: summarize synthetic evidence status and pressure points
    before any private LAN endpoint setup.
29. Peer scorecard history: compare scorecards over time to see resolved, new,
    persistent, improving, and regressing pressure points before treating a
    private experiment as repeatable.
30. Peer scorecard regression: apply an explicit policy to scorecard history
    before calling repeated synthetic evidence stable.
31. Repeated scorecard fixture: generate a clearly synthetic two-scorecard
    clear path before using the scorecard stack as a stable public fixture.
32. Preflight clear fixture: generate a clearly synthetic route-health,
    readiness, topology, and lab-bundle clear path before using preflight gates
    as a stable public fixture.
33. Repeated scorecard review bundle: verify the generated clear fixture
    separately from the intentionally blocked public baseline.
34. Preflight clear review bundle: verify the generated route preflight clear
    fixture separately from the intentionally blocked public baseline.
35. Peer review bundle: verify the sanitized artifact stack, docs, tools,
    tests, schemas, and terminal status gates before handing off a private run.
36. Private-run handoff: declare required private evidence slots without
    selecting endpoints or approving live work.
37. Private evidence checklist: convert handoff slots into pending private-run
    evidence items without collecting evidence or endpoint values.
38. Private evidence redaction: declare private-only and sanitized-derivative
    policy before any private evidence moves toward public artifacts.
39. Fixture index: summarize expected blocked and ready public fixture lanes
    before packaging or handoff review.
40. Public package index: verify expected fixture states, required public
    files, and declared validation evidence before public review.
41. Private import plan: describe sanitized derivative import readiness after
    package and redaction gates, without reading private evidence.
42. Private result placeholders: declare future public result slots without
    reading private evidence or importing artifacts.
43. Private result acceptance: decide whether sanitized derivative result
    slots could later accept public-safe artifacts after private review,
    without importing artifacts.
44. On-device Codex engineering: prove the CLI, sandbox behavior, small public
    repo edits, validation, and patch review before any build or deploy lane.
45. On-device APK loop: use an operator-authorized WiFi ADB endpoint to build,
    sign, install, and launch a source-only smoke APK from Termux.
46. XR questionnaire panel handoff: test a foreground XR app launching a
    separate 2D questionnaire panel with a caller-provided return route, then
    returning to the same XR app without ADB, force-stop, package killing, or
    Meta menu navigation in the product path.
47. Reboot ADB recovery: treat Termux:Boot and pre-granted normal helpers as
    status probes only unless the target OS proves an official user-authorized
    wireless-debugging route.
48. Termux agent restart helper: use a visible, pre-granted helper Activity
    only to ask Termux to restart the fixed fleet-agent command; prove recovery
    with fresh heartbeats and the loopback ADB `uid=2000(shell)` gate.
49. Boot, wake-lock, desktop environments, audio, and graphics acceleration:
    treat each as a separate high-risk gate.

## Validation

```powershell
python tools/check_public_boundary.py --repo-root .
python -m py_compile tools/capture_vnc_screenshot.py tools/stream_vnc_mjpeg.py tools/check_public_boundary.py
python -m py_compile tools/fleet_control_plane.py scripts/termux_fleet_agent.py tools/test_fleet_control_plane.py
python -m unittest tools.test_fleet_control_plane
python -m py_compile tools/peer_mesh_gossip.py tools/test_peer_mesh_gossip.py
python -m unittest tools.test_peer_mesh_gossip
python -m py_compile tools/peer_mesh_round.py tools/test_peer_mesh_round.py
python -m unittest tools.test_peer_mesh_round
python -m py_compile tools/peer_mesh_http_sim.py tools/test_peer_mesh_http_sim.py
python -m unittest tools.test_peer_mesh_http_sim
python -m py_compile tools/peer_mesh_delivery.py tools/test_peer_mesh_delivery.py
python -m unittest tools.test_peer_mesh_delivery
python -m py_compile tools/peer_mesh_dispatch_plan.py tools/test_peer_mesh_dispatch_plan.py
python -m unittest tools.test_peer_mesh_dispatch_plan
python -m py_compile tools/peer_mesh_file_drop_staging.py tools/test_peer_mesh_file_drop_staging.py
python -m unittest tools.test_peer_mesh_file_drop_staging
python tools/peer_mesh_file_drop_staging.py --manifest examples/peer-file-drop-staging-manifest.synthetic.json --artifact-root . --output examples/peer-file-drop-staging-report.synthetic.json
python -m py_compile tools/peer_mesh_file_drop_copy_dry_run.py tools/test_peer_mesh_file_drop_copy_dry_run.py
python -m unittest tools.test_peer_mesh_file_drop_copy_dry_run
python tools/peer_mesh_file_drop_copy_dry_run.py --staging-report examples/peer-file-drop-staging-report.synthetic.json --outcomes examples/peer-file-drop-copy-outcomes.synthetic.json --output examples/peer-file-drop-copy-dry-run-report.synthetic.json
python -m py_compile tools/peer_mesh_file_drop_inbox_intake.py tools/test_peer_mesh_file_drop_inbox_intake.py
python -m unittest tools.test_peer_mesh_file_drop_inbox_intake
python tools/peer_mesh_file_drop_inbox_intake.py --copy-report examples/peer-file-drop-copy-dry-run-report.synthetic.json --manifest examples/peer-file-drop-inbox-intake-manifest.synthetic.json --artifact-root . --output examples/peer-file-drop-inbox-intake-report.synthetic.json
python -m py_compile tools/peer_mesh_send_dry_run.py tools/test_peer_mesh_send_dry_run.py
python -m unittest tools.test_peer_mesh_send_dry_run
python -m py_compile tools/peer_mesh_retry_plan.py tools/test_peer_mesh_retry_plan.py
python -m unittest tools.test_peer_mesh_retry_plan
python -m py_compile tools/peer_mesh_route_health.py tools/test_peer_mesh_route_health.py
python -m unittest tools.test_peer_mesh_route_health
python -m py_compile tools/peer_mesh_topology.py tools/test_peer_mesh_topology.py
python -m unittest tools.test_peer_mesh_topology
python -m py_compile tools/peer_mesh_route_history.py tools/test_peer_mesh_route_history.py
python -m unittest tools.test_peer_mesh_route_history
python -m py_compile tools/peer_mesh_live_lab_readiness.py tools/test_peer_mesh_live_lab_readiness.py
python -m unittest tools.test_peer_mesh_live_lab_readiness
python -m py_compile tools/peer_mesh_lab_bundle.py tools/test_peer_mesh_lab_bundle.py
python -m unittest tools.test_peer_mesh_lab_bundle
python -m py_compile tools/peer_mesh_trust_gate.py tools/test_peer_mesh_trust_gate.py
python -m unittest tools.test_peer_mesh_trust_gate
python -m py_compile tools/peer_mesh_rehearsal.py tools/test_peer_mesh_rehearsal.py
python -m unittest tools.test_peer_mesh_rehearsal
python -m py_compile tools/peer_mesh_evidence_intake.py tools/test_peer_mesh_evidence_intake.py
python -m unittest tools.test_peer_mesh_evidence_intake
python -m py_compile tools/peer_mesh_cleanup_plan.py tools/test_peer_mesh_cleanup_plan.py
python -m unittest tools.test_peer_mesh_cleanup_plan
python -m py_compile tools/peer_mesh_scorecard.py tools/test_peer_mesh_scorecard.py
python -m unittest tools.test_peer_mesh_scorecard
python -m py_compile tools/peer_mesh_scorecard_history.py tools/test_peer_mesh_scorecard_history.py
python -m unittest tools.test_peer_mesh_scorecard_history
python -m py_compile tools/peer_mesh_scorecard_regression.py tools/test_peer_mesh_scorecard_regression.py
python -m unittest tools.test_peer_mesh_scorecard_regression
python -m py_compile tools/peer_mesh_repeated_scorecard_fixture.py tools/test_peer_mesh_repeated_scorecard_fixture.py
python -m unittest tools.test_peer_mesh_repeated_scorecard_fixture
python -m py_compile tools/peer_mesh_review_bundle.py tools/test_peer_mesh_review_bundle.py
python -m unittest tools.test_peer_mesh_review_bundle
python tools/peer_mesh_review_bundle.py --manifest examples/peer-review-bundle-preflight-clear-manifest.synthetic.json --artifact-root . --output examples/peer-review-bundle-preflight-clear-report.synthetic.json
python -m py_compile tools/peer_mesh_private_run_handoff.py tools/test_peer_mesh_private_run_handoff.py
python -m unittest tools.test_peer_mesh_private_run_handoff
python -m py_compile tools/peer_mesh_private_evidence_checklist.py tools/test_peer_mesh_private_evidence_checklist.py
python -m unittest tools.test_peer_mesh_private_evidence_checklist
python -m py_compile tools/peer_mesh_private_evidence_redaction.py tools/test_peer_mesh_private_evidence_redaction.py
python -m unittest tools.test_peer_mesh_private_evidence_redaction
python -m py_compile tools/peer_mesh_fixture_index.py tools/test_peer_mesh_fixture_index.py
python -m unittest tools.test_peer_mesh_fixture_index
python -m py_compile tools/peer_mesh_public_package.py tools/test_peer_mesh_public_package.py
python -m unittest tools.test_peer_mesh_public_package
python -m py_compile tools/peer_mesh_private_import_plan.py tools/test_peer_mesh_private_import_plan.py
python -m unittest tools.test_peer_mesh_private_import_plan
python -m py_compile tools/peer_mesh_private_result_placeholder.py tools/test_peer_mesh_private_result_placeholder.py
python -m unittest tools.test_peer_mesh_private_result_placeholder
python -m py_compile tools/peer_mesh_private_result_acceptance.py tools/test_peer_mesh_private_result_acceptance.py
python -m unittest tools.test_peer_mesh_private_result_acceptance
powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw tools\capture_x11_surface_metrics.ps1)) | Out-Null"
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_android_vnc_panel_viewer.ps1 -Unsigned
bash -n scripts/build-minimal-android-apk-on-device.sh scripts/wifi-adb-keepawake-watchdog.sh scripts/quest-x11-wide-prefs.sh scripts/start-quest-x11-wide.sh
```
