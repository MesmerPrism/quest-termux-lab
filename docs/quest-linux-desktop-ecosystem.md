# Quest Linux desktop ecosystem and development references

Research reference date: 2026-09-12  
Status: engineering reference, not a priority or patent search  
Primary target: Spatial Linux Desktop for Meta Quest

## Why this document exists

Linux on Quest predates this project. This document places the Spatial Linux
Desktop in that wider ecosystem, gives adopters useful alternatives, and turns
the comparison into a development agenda. It should prevent two mistakes:

- presenting established local-Linux or XR-desktop techniques as new; and
- copying an attractive technique without first checking its execution model,
  evidence, license, and whole-device cost.

The external ecosystem scan behind this synthesis examined 53 target,
candidate, upstream, adjacent, and lead records and logged 74 source or access
attempts. Those counts are an audit trail, not counts of verified products. The
scan did not independently build the projects, reproduce their headset tests,
or measure their performance.

The scan inspected this project's hybrid implementation at commit
[`1ed3a45`](https://github.com/MesmerPrism/quest-termux-lab/tree/1ed3a4544ac3883e4c4928c4f114b22466c7c783).
Later code and operator acceptance must be read from the current branch and
current validation records. In particular, a finding that a feature was
pending in the research snapshot does not override a later, recorded hardware
test.

## Executive position

The defensible contribution is a particular integration, not “the first Linux
desktop on Quest.” The integration is:

- a native ARM64 Termux/XFCE session rendered by Termux:X11 on the headset;
- optional PRoot distributions for software needing a conventional Linux
  userspace;
- `x11vnc` mirroring the active X display over Android loopback;
- a bounded, repository-owned RFB client;
- mutually exclusive Horizon window and Meta Spatial SDK panel presentations;
- Quest-specific pointer, keyboard, microphone, camera, and workflow bridges;
  and
- public fixtures, runbooks, tests, and claim boundaries.

No other public implementation of that exact Termux:X11 + loopback x11vnc +
Meta Spatial SDK arrangement was identified in the sources inspected on the
research date. That is a bounded search result, not proof of nonexistence and
not a basis for a “first,” “only,” or “unique” headline.

## Architecture taxonomy

The first question for an adopter is where the workload should execute. The
second is who owns its presentation and input.

| Route | Representative work | Workload location | Presentation | Main trade-off |
| --- | --- | --- | --- | --- |
| Direct local Linux | [legokichi](https://qiita.com/legokichi/items/66975c203aebb5a4121c), [matmon3](https://github.com/matmon3/TERMUX-linux-X11-on-android-Proot-KDE-XFCE-compatibility-with-quest-3-and-3s-), [DroidDesk](https://github.com/orailnoor/DroidDesk) | Quest | Standard Android/Termux:X11 window | Shorter display path and simpler architecture; no application-owned XR panel |
| Local PRoot plus VNC | [Andronix](https://docs.andronix.app/get-started/how-does-andronix-work), UserLAnd recipes | Quest | Generic Android VNC client or browser | Familiar distribution and mature client options; usually a separate virtual X session and generic Quest interaction |
| Local compatibility runtime with native XR | [WinlatorXR](https://github.com/WinlatorXR/WinlatorXR/tree/cmod_bionic) | Quest | Purpose-built XR frontend | Strong precedent for local execution plus XR-owned input, but aimed at Windows applications and translation layers rather than native ARM Linux/XFCE |
| Local Linux plus Quest-specific Spatial SDK frontend | This project | Quest | Horizon window or application-controlled Spatial SDK panel | More integration and maintenance work in exchange for local execution and Quest-specific interaction experiments |
| Native Quest remote desktop | [remote-desktop-for-ubuntu](https://github.com/yveshughes/remote-desktop-for-ubuntu), [Moonlight-SpatialSDK](https://github.com/XXJones21/Moonlight-SpatialSDK), [Nightfall](https://github.com/tB0nE/nightfall) | External computer | Native XR/Spatial SDK surface | Hardware video decode and desktop-class host resources, but an external host and network remain part of the system |
| Remote Linux spatial workspace | [WayVR](https://github.com/wayvr-org/wayvr) with [WiVRn](https://github.com/WiVRn/WiVRn), Immersed | External Linux computer | Streamed spatial workspace | Best fit when compatibility, GPU resources, or several displays matter more than standalone execution |
| Cloud desktop | [AWS Quest virtual-desktop prototype](https://aws.amazon.com/blogs/physical-ai/vr-virtual-desktop-prototype-on-the-meta-quest/), Guacamole deployments | Cloud | Native or browser client | Avoids a user-owned host but adds identity, network, cost, and data-governance dependencies |

PRoot is not privileged `chroot`, and a local compatibility runtime is not a
full virtual machine. A generic Android window is not an application-controlled
spatial panel. These distinctions should remain explicit in documentation.

## Established chronology

The dates below are the earliest public dates established by the 2026-09-12
scan, not a complete priority history.

| Date | Reference | What it establishes | Important limit |
| --- | --- | --- | --- |
| 2018-11-27 | [Tokoro: Oculus Go standalone work environment](https://blog.tokor.org/2018/11/27/Oculus-Go%E3%81%A7%E3%82%B9%E3%82%BF%E3%83%B3%E3%83%89%E3%82%A2%E3%83%AD%E3%83%B3VR%E4%BD%9C%E6%A5%AD%E7%92%B0%E5%A2%83%E3%82%92%E4%BD%9C%E3%81%A3%E3%81%9F/) and [OVRVNC](https://github.com/y-fujii/ovrvnc) | Local UserLAnd Linux, a native VR VNC viewer, and a Bluetooth keyboard on standalone Oculus hardware | Oculus Go, not Quest or Meta Spatial SDK |
| 2019-05-24 | [RangerMauve: Linux on the Oculus Quest](https://medium.com/@RangerMauve/linux-on-the-oculus-quest-406ba5d0c982) | Local Ubuntu/UserLAnd workflow on the original Quest | The inspected account supports a userland/SSH workflow, not a complete GUI claim |
| 2020 | [Quest 2 XFCE + noVNC demonstration](https://www.reddit.com/r/OculusQuest/comments/ji9k7z/xfce_desktop_environment_on_my_quest_2_running_in/) | Credible local graphical-desktop evidence using Termux, XFCE, noVNC, and Firefox Reality | Exact day, full architecture, and sustained usability were not recovered |
| 2022-10-26 | [catid: Quest Pro Termux and code-server](https://catid.io/posts/quest_pro_termux/) | Local development workflow on Quest Pro | Browser IDE, not a full desktop or spatial panel |
| 2025 | [Ben Kaiser](https://benkaiser.dev/web-development-in-vr/), [legokichi](https://qiita.com/legokichi/items/66975c203aebb5a4121c), [matmon3](https://github.com/matmon3/TERMUX-linux-X11-on-android-Proot-KDE-XFCE-compatibility-with-quest-3-and-3s-), [Andronix/bVNC video](https://www.youtube.com/watch?v=Xshj_xjwVjc) | Several reproducible-looking local Quest desktop routes across UserLAnd, Termux:X11, and PRoot/VNC | The research did not independently reproduce them; video access was incomplete |
| 2026 | [remote-desktop-for-ubuntu](https://github.com/yveshughes/remote-desktop-for-ubuntu) | Meta Spatial SDK panel, controller mouse input, scrolling, right-click, Bluetooth keyboard, and direct hardware video surface | Linux executes on an external Ubuntu computer |

There is also a 2023 direct-Termux:X11 lead associated with
[Kazuho Oku](https://gist.github.com/kazuho/2432b0dce057b34488de4e5e7b356cad),
but its publication history was not established well enough to use as a firm
priority date.

## Closest engineering comparisons

### Direct Termux:X11 on Quest

[legokichi's guide](https://qiita.com/legokichi/items/66975c203aebb5a4121c)
is the most useful baseline for the same native Termux/XFCE family without the
extra x11vnc/RFB/Spatial SDK path. It also documents Japanese input work and an
OS-version-specific microphone failure.

Use it to answer whether our additional layer earns its cost. Run the same
resolution and visible tasks in direct Termux:X11 and in both presentations of
our app. Compare input correctness, click-to-visible response, text clarity,
process load, thermal state, and battery use.

### DroidDesk

[DroidDesk](https://github.com/orailnoor/DroidDesk) is the closest packaging and
local Android desktop ecosystem comparison. Its current repository describes
both setup workflows and a standalone Android application with an embedded
Termux:X11 server. No Quest-specific spatial renderer was established in the
scan.

The useful lesson is onboarding: dependency detection, application discovery,
desktop selection, start/stop flows, and recovery. Its
[compliance record](https://github.com/orailnoor/DroidDesk/blob/main/COMPLIANCE.md)
also demonstrates why a repository license alone does not settle bundled
bootstrap, native library, artwork, notice, and corresponding-source duties.
Study the workflow; review every file and dependency before reusing code.

### WinlatorXR

[WinlatorXR](https://github.com/WinlatorXR/WinlatorXR/tree/cmod_bionic) is the
strongest counterexample to broad claims about local execution plus native XR.
Its [XR controller code](https://github.com/WinlatorXR/WinlatorXR/blob/d4c830526eb5562067d21685a975845ab705da60/app/src/main/java/com/winlator/xr/XrController.java)
routes XR state into a local X-server-backed environment. The project is aimed
at Windows applications through Wine and CPU translation rather than a native
ARM Linux desktop, and it does not use Meta Spatial SDK.

Study its cursor stability, focus ownership, keyboard activation, application
switching, and local rendering boundary. The project's license describes fork
modifications as LGPLv3 while retaining upstream terms; do not describe the
whole fork as MIT or import code without a file-level review.

### remote-desktop-for-ubuntu

[Yves Hughes' client](https://github.com/yveshughes/remote-desktop-for-ubuntu)
is the closest inspected Meta Spatial SDK comparison. Its source maps panel UVs
to host coordinates and implements trigger left-click, A/X right-click,
thumbstick scrolling, keyboard translation, panel manipulation, and bounded
reconnection. Its documented spike sends HEVC through Android hardware decode
to a Spatial SDK video surface. The decisive difference is that Sunshine and
the Linux desktop run on an external Ubuntu machine.

This is the best reference for:

- keeping desktop input from consuming the events required for panel grabs;
- activity-level physical-keyboard capture and modifier handling;
- direct decoder-to-panel surfaces;
- separating input from the media stream; and
- bounded reconnect behavior.

The repository reports its own Quest Pro tests and latency observations. They
are not measurements of our local path. It also states that distribution is
GPL-3.0 because of `moonlight-common-c`.

### Tokoro and OVRVNC

The 2018 [Tokoro workflow](https://blog.tokor.org/2018/11/27/Oculus-Go%E3%81%A7%E3%82%B9%E3%82%BF%E3%83%B3%E3%83%89%E3%82%A2%E3%83%AD%E3%83%B3VR%E4%BD%9C%E6%A5%AD%E7%92%B0%E5%A2%83%E3%82%92%E4%BD%9C%E3%81%A3%E3%81%9F/)
paired local Linux with [OVRVNC](https://github.com/y-fujii/ovrvnc). It is the
most important historical standalone analogue, despite targeting Oculus Go.
OVRVNC's separation of frame handling, rendering, and input is worth studying.
Its MIT repository code does not change the licenses of TigerVNC or other
dependencies.

### Andronix and generic VNC clients

The [Quest 3 Andronix video](https://www.youtube.com/watch?v=Xshj_xjwVjc) is a
clear adopter-facing example of local Ubuntu presented through a generic VNC
client. Andronix's own architecture documentation identifies PRoot rather than
privileged chroot. The scan could verify indexed metadata and upstream
architecture, but not reliably inspect the full video, timestamps, comments, or
transcript.

This route is not inferior by definition. A mature generic client may offer
more RFB encodings, clipboard behavior, text input, authentication, and recovery
with much less Quest-specific code. It should be compared in user tasks rather
than dismissed because Horizon owns the window.

## Adopter decision guide

| Need | Start with | Why |
| --- | --- | --- |
| A conventional local Linux desktop with the shortest rendering path | Direct Termux:X11 or DroidDesk | Avoids the additional local capture and RFB stages |
| Familiar Ubuntu onboarding in an ordinary window | Andronix/UserLAnd plus a mature VNC client | Distribution-oriented setup and established client behavior |
| Locally execute Windows applications in an XR-owned surface | WinlatorXR | Purpose-built local XR integration for that workload family |
| A powerful external Linux workstation in a native Quest panel | remote-desktop-for-ubuntu, Moonlight-SpatialSDK, or WayVR/WiVRn | External compute and hardware video encoding are appropriate trade-offs |
| Experiment with a local Linux desktop plus Quest-specific panel and device bridges | Spatial Linux Desktop | The local execution, hybrid presentation, input classifier, microphone, camera, and workflow boundaries are the point |

Remote execution is not a failure mode. For GPU-heavy applications, large
builds, several monitors, or mature multimedia transport, it may be the better
architecture. Likewise, a normal Termux:X11 window may be better when spatial
panel control adds no value.

## Development priorities derived from the comparison

The priorities below are experiments, not promised improvements.

### P0: correctness, evidence, and local security

1. **Current-release input acceptance.** On exact release builds, test hover,
   single click, jitter-tolerant double-click, deliberate drag, right-click,
   scrolling, focus-loss release, controller mappings, and panel grabbing in
   both presentations. Preserve actual hardware tests separately from semantic
   intent/CLI tests.
2. **Unicode, IME, and clipboard.** Separate physical key state from committed
   text. Test German AltGr/dead keys, Japanese composition, deletion,
   selection, copy, and paste. Study legokichi, noVNC, and bVNC, but respect
   MPL/GPL licensing.
3. **Loopback threat model.** Verify IPv4 and IPv6 listeners. Test an
   unauthorized same-device client, stale camera tokens, microphone shutdown,
   and reconnect/session replacement. Loopback plus RFB `None` security limits
   network exposure; it does not authenticate the intended two applications.
4. **Evidence alignment.** Keep source capability, automated tests,
   operator-observed hardware results, and sustained measurements in distinct
   fields. Refresh the public validation record when a later release closes an
   older failure.

### P1: performance and lifecycle

1. **Measure before changing transport.** Compare direct Termux:X11, current
   retained RFB, and any compressed-video candidate with the same desktop,
   resolution, and task trace.
2. **Extend RFB selectively.** Measure CopyRect, changed rectangles, cursor
   pseudo-encoding, and one reviewed compressed encoding before replacing the
   protocol. A static desktop should not be redrawn continuously.
3. **Investigate direct surfaces.** Use WinlatorXR and the Spatial SDK Ubuntu
   client as references for direct local rendering and decoder surfaces. Do not
   claim a zero-copy Termux:X11 handoff until a compatible buffer contract is
   demonstrated.
4. **Test hardware video end to end.** Hardware decode alone does not prove a
   local win because the same headset may also perform readback, encoding,
   copies, and queueing. Include sharp text and chroma edges in the quality
   criterion.
5. **Make lifecycle explicit.** Release held keys/buttons, stop microphone
   capture on pause or permission loss, request a fresh frame after reconnect,
   cap retries, and avoid transform writes while a panel is grabbed.
6. **Validate audio channels independently.** Playback and microphone uplink
   have different clocks and failure modes. Measure drift, underruns, sample
   format, mute indication, permission denial, and stop semantics.

### P2: usability and distribution

1. **Panel DPI and resolution presets.** Keep desktop pixels, physical panel
   dimensions, and angular text size independent. Avoid changing desktop
   resolution in the middle of a gesture.
2. **Accessible interaction presets.** Make snap distance, movement slop,
   click-after-release behavior, and alternative right-click routes tunable.
   Test seated, one-controller, and low-mobility use rather than inferring
   accessibility from configuration alone.
3. **Onboarding.** Add an idempotent dependency checker and one visible
   start/stop/recovery flow before considering bundled distributions. Pin
   versions and maintain notices and source records.
4. **Sustained operation.** Run 30- and 60-minute mixed workloads with thermal,
   battery, memory, process-survival, and readability observations.

## Comparative benchmark contract

Use one deterministic visible task trace across every presentation and
transport:

1. Connect and open a known application.
2. Click large and small targets.
3. Make and cancel a drag.
4. Double-click with recorded spatial jitter.
5. Right-click through every supported route.
6. Scroll static text, a dense canvas, and a high-damage surface.
7. Enter ASCII, German AltGr/dead-key text, and Japanese composed text.
8. Hold and release modifiers, then force focus loss.
9. Resize, grab, recenter, and switch presentation modes.
10. Sleep/wake and disconnect/reconnect.
11. Exercise denied microphone/camera permissions and successful recovery.
12. Run the known small camera-import and print fixtures separately.

For every run, record:

- app commit and APK hash;
- headset model and Horizon build, without a serial;
- Linux, Termux:X11, x11vnc, and application versions;
- X display and framebuffer resolution;
- panel size or angular-size reference;
- pixel format and transport/encoding;
- physical input device and actual event path;
- expected desktop response and observed response;
- CPU, memory, Android thermal state, and battery change;
- RFB updates, rectangles, changed pixels, bytes, decode time, and render time;
- click-to-visible-response median and tail only after defining both endpoints;
  and
- reconnects, process deaths, stuck keys/buttons, audio underruns, and dropped
  input.

Do not collapse device render refresh, server update rate, decoder frame rate,
first decoded frame, and click-to-visible response into one “FPS” number.

## Public claim rules

### Supported framing

- “This project provides a Quest-specific interface to a locally executing
  Termux:X11 desktop.”
- “The client mirrors the active local X display through an Android-loopback
  RFB connection when the documented `x11vnc -localhost` runbook is followed.”
- “The project focuses on the combination of local native-ARM Linux, hybrid
  Horizon/Spatial SDK presentation, bounded desktop input, and selected
  Quest-to-Linux bridges.”
- “Earlier local Linux desktops, native VR desktop viewers, and Meta Spatial
  SDK remote desktops are acknowledged as related work.”
- “The public sources inspected on 2026-09-12 did not reveal another project
  with this exact Termux:X11 + loopback x11vnc + Meta Spatial SDK arrangement.”
  Use this only beside the search limitations and never as a synonym for
  “first” or “only.”

### Claims requiring release-specific validation

- controller right-click in both presentations;
- international virtual-keyboard input and IME composition;
- synchronized controller click plus microphone capture;
- a complete current source-to-running-APK and Codex/mobile round trip;
- release-visible recenter behavior; and
- sustained performance across Quest 3 and 3S.

Some of these may already have later operator evidence than the research
snapshot. Update the validation record before promoting the claim.

### Claims to avoid

- “The first Linux desktop on Quest.”
- “The first locally executing desktop environment in standalone VR.”
- “The first Quest ray-to-Linux mapping or Spatial SDK Linux desktop client.”
- “Secure because it uses localhost.”
- “All components are MIT.”
- “Fully offline” for cloud AI, downloads, or network printing.
- “A PC replacement” or “arbitrary Linux application compatibility.”

## Follow-up research queue

1. Watch and timestamp the complete Andronix/bVNC and older Quest Linux videos;
   preserve what is shown separately from what descriptions claim.
2. Recover the original publication trail for the Kazuho Termux:X11 gist and
   any associated posts.
3. Build OVRVNC against a currently supported Quest target if licensing and
   dependencies permit, then test it against the same local x11vnc session.
4. Audit WinlatorXR rendering and keyboard code at file level before proposing
   reuse or architectural convergence.
5. Run the same-SDK Ubuntu client and our app on the same headset/input devices;
   compare panel ownership, keyboard capture, grab conflicts, reconnect, and
   click-to-visible response without treating remote-host latency as a local
   transport measurement.
6. Inspect Nightfall and the Quest-adapted aRDP/bVNC/aSPICE fork more deeply.
7. Search SideQuest, Meta developer forums, XDA, Bilibili, Gitee, 4PDA, and
   deleted/archived repositories with native platform search rather than only
   web indexing.
8. Revisit commercial Linux-host support against named application versions;
   do not generalize old Immersed, Steam Link, Virtual Desktop, or Meta Remote
   Desktop matrices.

## Reference directory

### Local Quest Linux and development

- [RangerMauve — Linux on the Oculus Quest](https://medium.com/@RangerMauve/linux-on-the-oculus-quest-406ba5d0c982)
- [Quest 2 XFCE/noVNC community demonstration](https://www.reddit.com/r/OculusQuest/comments/ji9k7z/xfce_desktop_environment_on_my_quest_2_running_in/)
- [legokichi — standalone Linux with Termux on Quest 3](https://qiita.com/legokichi/items/66975c203aebb5a4121c)
- [matmon3 — Quest 3/3S Termux:X11 recipe](https://github.com/matmon3/TERMUX-linux-X11-on-android-Proot-KDE-XFCE-compatibility-with-quest-3-and-3s-)
- [Ben Kaiser — Web development in VR](https://benkaiser.dev/web-development-in-vr/)
- [Andronix/bVNC Quest 3 video](https://www.youtube.com/watch?v=Xshj_xjwVjc)
- [catid — Quest Pro Termux/code-server](https://catid.io/posts/quest_pro_termux/)
- [Ramin Assadollahi — Developing for Quest on Quest](https://assadollahi.de/developing-for-the-oculus-quest-on-the-oculus-quest/)

### Local XR and native desktop clients

- [Tokoro — Oculus Go standalone work environment](https://blog.tokor.org/2018/11/27/Oculus-Go%E3%81%A7%E3%82%B9%E3%82%BF%E3%83%B3%E3%83%89%E3%82%A2%E3%83%AD%E3%83%B3VR%E4%BD%9C%E6%A5%AD%E7%92%B0%E5%A2%83%E3%82%92%E4%BD%9C%E3%81%A3%E3%81%9F/)
- [OVRVNC](https://github.com/y-fujii/ovrvnc)
- [WinlatorXR](https://github.com/WinlatorXR/WinlatorXR/tree/cmod_bionic)
- [remote-desktop-for-ubuntu](https://github.com/yveshughes/remote-desktop-for-ubuntu)
- [Moonlight-SpatialSDK](https://github.com/XXJones21/Moonlight-SpatialSDK)
- [Quest-adapted remote desktop clients](https://github.com/wasdwasd0105/remote-desktop-clients-quest)
- [Nightfall](https://github.com/tB0nE/nightfall)
- [binzume WebRTC/WebXR RDP](https://github.com/binzume/webrtc-rdp)

### Linux-host spatial and remote alternatives

- [WayVR](https://github.com/wayvr-org/wayvr)
- [WiVRn](https://github.com/WiVRn/WiVRn)
- [ALVR](https://github.com/alvr-org/ALVR)
- [Immersed](https://immersed.com/faq)
- [AWS Quest virtual-desktop prototype](https://aws.amazon.com/blogs/physical-ai/vr-virtual-desktop-prototype-on-the-meta-quest/)
- [Apache Guacamole](https://guacamole.apache.org/)

### Upstream components and licensing references

- [Termux](https://github.com/termux/termux-app)
- [Termux:X11](https://github.com/termux/termux-x11)
- [x11vnc](https://github.com/LibVNC/x11vnc)
- [noVNC](https://github.com/novnc/noVNC)
- [Andronix architecture](https://docs.andronix.app/get-started/how-does-andronix-work)
- [Andronix source-availability statement](https://docs.andronix.app/miscellaneous/open-source)
- [bVNC/aRDP/aSPICE upstream](https://github.com/iiordanov/remote-desktop-clients)
- [Meta Spatial SDK samples](https://github.com/meta-quest/Meta-Spatial-SDK-Samples)

## Evidence boundary

This document is an engineering map based on public sources and an external
research synthesis. It is not an independent reproduction, security audit,
license opinion, exhaustive multilingual search, or legal prior-art search.
“Not verified” means the scan did not establish a fact; it does not mean the
feature is absent. Recheck living projects and product support matrices before
making current-status claims.
