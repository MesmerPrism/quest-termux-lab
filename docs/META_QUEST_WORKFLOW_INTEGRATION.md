# Meta Quest Workflow Integration

Quest Termux Lab should be used with a broader Meta Quest device workflow.
The Termux recipes in this repository assume that live device operation is
handled by a workflow that already covers:

- shared headset and ADB coordination;
- explicit serial selection;
- APK install and launch gates;
- screenshots and logcat windows;
- capture source labeling;
- port-forward setup and cleanup;
- headset readiness after sleep or reboot;
- operator-visible prompts and protected system UI.

If your agent environment supports local skills, use `meta-quest-workflow`
before running a live Quest test. If it does not, apply the same rule manually:
identify the operation class, prefer read-only probes first, preserve power and
proximity state unless the test explicitly changes it, and verify cleanup.

## Division Of Responsibility

| Area | Owner |
| --- | --- |
| Device coordination, ADB, installs, launches, screenshots, logcat | Meta Quest workflow |
| Termux CLI, X11, Proot, VNC, local dashboard recipes | Quest Termux Lab |
| Raw device evidence and private artifacts | Local/private workspace, not this repo |
| Public reusable findings | Sanitized docs, schemas, and synthetic fixtures in this repo |

## Capture Labeling

For Termux/X11 desktop work, label three evidence routes separately:

- X-root evidence: direct localhost/ADB-forwarded VNC screenshots or MJPEG
  frame/status endpoints.
- Headset display evidence: ADB or headset-provider screencaps of the Quest
  panel/compositor view.
- Human observer evidence: visible browser, cast, or desktop-window captures.

Prefer direct X-root frame/status pulls for automated VNC stream evidence.
Use headset display evidence only when the question is whether the Quest panel
itself is presenting the X content.

## Practical Start

1. Confirm the headset is authorized for ADB and in a meaningful ready state.
2. Capture a baseline with model, Android version, foreground surface, and
   recovery route.
3. Run the smallest Termux recipe that answers the question.
4. Stop the sidecar process or server.
5. Remove any ADB forward.
6. Record cleanup evidence before interpreting the result.
