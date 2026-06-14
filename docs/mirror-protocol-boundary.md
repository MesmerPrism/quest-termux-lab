# Mirror Protocol Boundary

The mirror protocol is a typed command-request lane for two Quest Termux
agents. It is not peer gossip, raw ADB, raw input replay, or arbitrary shell
control.

Non-negotiable boundaries:

1. Mirror commands are typed commands, not arbitrary shell text.
2. Quest A is not granted raw control of Quest B.
3. Quest B only executes commands that pass its own local policy.
4. Commands that require ADB only run if Quest B's Termux agent verifies
   `adb shell id == uid=2000(shell)`.
5. Existing peer gossip remains status-only.
6. All commands require TTL, idempotency, source identity, target identity, and
   a result.
7. Every live session is revocable.

## Authority

The controller owns mirror lease state, intent state, idempotency mapping, and
result-to-intent correlation. The source headset may submit a typed intent.
The target headset remains the final execution authority through its local
fleet-agent config and mirror binding policy.

The execution path is deliberately unchanged:

```text
mirror-command-intent
  -> controller validation
  -> fleet-command-request
  -> target agent local validation
  -> bounded executor
  -> fleet-command-result
  -> mirror-command-event
```

## Non-Scope

The mirror protocol does not provide:

- generic shell execution;
- raw `adb` command forwarding;
- raw tap, swipe, controller, or coordinate mirroring;
- package install requests outside the existing verified update command;
- raw logcat mirroring;
- VNC control;
- headset listeners exposed to the internet.

For off-Wi-Fi use, both headsets initiate outbound HTTPS or polling to the
controller. Do not expose headset ADB, VNC, HTTP listeners, Termux listeners,
or direct device-to-device command sockets to the internet.

## Peer Gossip Boundary

Peer gossip remains useful for presence and compact status:

- last-seen peer;
- central reachability;
- local ADB availability summary;
- last command status.

It must continue rejecting command-like, shell-like, credential-like, ADB
target, pairing, install, and launch fields. Mirror commands belong in the
controller-mediated fleet command lane.

## First Command Set

Start with these command kinds:

```text
agent.status
agent.capabilities
adb.lease_check
android.foreground_snapshot
app.launch_allowlisted
uiautomator.run_allowlisted_scenario
adb.lease_disconnect
```

Target rejection is normal. Common rejection reasons include missing or expired
lease, revoked lease, source not allowed, wrong target, command kind not
allowed, payload not allowed, local ADB unavailable, operator-visible session
missing, duplicate idempotency, and timeout.
