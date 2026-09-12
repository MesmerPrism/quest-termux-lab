# Public Quest Findings

These findings are generalized from local lab work and intentionally omit
private paths, serials, screenshots, package identities, and project names.

## Current Findings

- Termux can act as a useful normal-app diagnostics sidecar.
- Termux app UID is distinct from Android `shell`; package queries may work
  while launch or privileged actions remain blocked.
- Termux:X11 can present a foreground 2D panel with small X11 clients.
- Pointer behavior can depend on Quest focus/click capture rather than hover.
- Proot can be useful for CLI tools and small GUI clients, but compatibility is
  package-specific.
- A full XFCE desktop can be launched as a lab sidecar through Termux:X11, and
  a Proot-hosted XFCE session can render through the same display path.
- A full desktop can render in the Quest 2D panel at the native phone-like X
  root size, but this is not yet an ergonomic desktop layout.
- A Proot-hosted terminal window can run ordinary Linux userland commands
  inside the desktop session.
- Host-visible VNC capture can work through localhost/ADB forwarding when the
  VNC server is configured to avoid shared-memory paths that Android blocks.
- Host-visible VNC can also be bridged into a local browser MJPEG stream for
  continuous observation instead of one-off screenshot capture.
- Automated VNC stream evidence should pull the stream frame/status endpoints
  directly. Browser-window or cast-window captures are optional human-visible
  witnesses, not the primary evidence path.
- VNC mirrors the X display; it does not fix headset-side panel geometry.
- Full-desktop evidence may be clearer through VNC than through the headset's
  Android panel screenshot path, which can show a black panel while the X root
  is alive.
- A resized landscape X root can be valid through VNC while the Quest 2D panel
  remains black or incomplete. Keep X-root evidence and headset-panel evidence
  labeled separately.
- Termux:X11 can expose a clean 1280x720 X root when its display resolution is
  set to an exact landscape value before the desktop starts. This can remove
  the left-slice desktop symptom in the X display and VNC stream.
- Termux:X11 preference-only native-wide probes can also create wider custom X
  roots such as 1600x900, 1920x1080, and 2560x1440.
- A full XFCE desktop can render visibly through the native Termux:X11 surface
  with an exact 1280x720 X root, without going through the VNC/MJPEG viewer.
  This is a partial success, not a finished interaction route: panel/layer
  alignment still needs manual input testing and may need activity manifest
  hints before it is ergonomic.
- Termux:X11's own Android activity may still present as a constrained
  phone-like Quest panel even when the X root is landscape. For headset-visible
  ergonomics, a separate landscape Android viewer panel can display the
  localhost MJPEG bridge without changing Termux's authority boundary.
- A minimal Android viewer panel with an explicit landscape 2D layout can show
  the full 1280x720 desktop from the localhost MJPEG bridge in headset. This is
  an observation surface only; Termux still owns the desktop session.
- A headset interaction check confirmed the small foreground Termux:X11 panel
  can receive Quest cursor input well enough to move the X cursor, click, and
  open desktop items. The larger Android viewer panel is not yet interactive
  and is visibly slower because it observes the MJPEG stream.
- A short headless-sidecar test confirmed that a Termux-owned localhost JSON
  command service can continue executing allowlisted commands while another
  headset app is foregrounded. This route does not require an X11 window or a
  visible Linux desktop.
- A broker-feedback sidecar test confirmed that Termux can run a small
  Python/Linux processing loop against a broker-owned status/stream registry
  and publish bounded diagnostic feedback while an XR app remains foregrounded.
- This broker-feedback route should treat Termux as an opt-in processor module
  only. The broker remains responsible for stream identity, module state,
  provider ownership, and acceptance of published feedback events.
- After an operator-approved WiFi ADB route is enabled, the Termux `adb` client
  can connect to the same headset over loopback and receive shell authority for
  install, launch, and bounded shell commands.
- A temporary Termux-side ADB keep-awake loop can hold the display awake during
  an attended lab run. It is a shell-lease helper, not a hidden boot service or
  Termux-native authority.
- Classic WiFi ADB on fixed port `5555` did not survive reboot in the tested
  route. Termux-local `adb` could not reconnect to that classic endpoint until
  an external authorized workflow re-enabled it. This result does not cover
  Android 11+ TLS Wireless Debugging, its dynamic mDNS port, or persistent
  pairing.
- A normal helper app that had been launched and pre-granted before reboot
  could receive boot and write app-owned status, but it did not restore classic
  WiFi ADB. Treat that helper shape as diagnostics, not shell recovery.
- A separate opt-in helper can discover the modern TLS connect service through
  Android NSD, hand its dynamic port to a previously paired Termux ADB client,
  and prove `uid=2000(shell)`. A fresh outbound heartbeat independently
  confirmed the same pre-reboot state. On the tested Horizon OS build, a fresh
  post-reboot heartbeat appeared only after the operator accepted Meta's
  protected Wi-Fi debugging alert. A read-only boot attempt avoided the alert
  but had no TLS service because Android had reset the Wi-Fi ADB transport
  before Wi-Fi joined.
- Peerless Wi-Fi Direct group-owner mode and Quest-owned `LocalOnlyHotspot`
  both kept local network interfaces active after the ordinary infrastructure
  Wi-Fi connection was disconnected. Neither topology satisfied the tested
  Horizon OS Wireless Debugging network gate: the setting remained disabled,
  no live TLS listener appeared, and Termux did not obtain shell UID `2000`.
- A later post-reboot test on the inspected Android 14 headset exercised the
  reported Android 16 timing-race shape more directly. With station Wi-Fi
  disabled and an app-owned local-only hotspot ready, one attempt started the
  hotspot before a roughly 15-second `adb_wifi_enabled` pulse and a second
  overlapped hotspot startup with the pulse. The setting briefly read `1` but
  the framework reset it to `0`; repeated socket observations found no TLS
  listener and the authorized Termux client remained unavailable. Both attempts
  restored the setting. This bounds the two tested orderings and does not prove
  that every timing race is impossible on other Android or Horizon OS builds.
- The same session established the missing client-authentication control. An
  attended USB-backed classic-ADB handoff caused Meta's visible approval for
  Termux's distinct RSA key. After wearer approval, the existing Termux ADB
  server reached exact shell UID `2000` first through classic loopback and then
  through a fresh dynamic TLS endpoint discovered by Android NSD. Classic TCP
  was still enabled during the TLS check; later cleanup removed both transports.
  This proves an exact-target TLS connection, not an exclusive TLS-only runtime.
  It also proves that the packaged Termux client supports direct TLS and that
  ordinary wearer-approved ADB key authorization is sufficient on this headset;
  it is not an authorization bypass or an unattended post-reboot bootstrap.
- Android NSD can report a cached TLS connect service from the previous
  infrastructure-network epoch. Treat discovery alone as advisory. Recovery
  requires a current enabled setting, a live listener, and an independent
  `adb shell id` result containing `uid=2000(shell)`.
- `service.adb.tls.port` was blank during a confirmed live TLS listener and
  successful loopback shell session on the inspected headset. Do not use that
  property as a required positive or negative witness there. Android NSD, a
  current socket observation, and the exact shell-UID result provide the useful
  independent checks.
- The validated on-device TLS route therefore still requires an eligible
  external station network on the tested headsets. A later attended test passed
  on an offline Windows Wi-Fi Direct autonomous group owner with legacy access-
  point support. The Quest obtained a local address, Android NSD supplied a
  fresh TLS endpoint after the wearer accepted Meta's network prompt, and the
  retained Termux key reached exact shell UID `2000` without another RSA-key
  prompt. Windows Internet sharing and forwarding were disabled, and external
  IPv4/IPv6 controls failed on the temporary network. The Windows host remained
  the group owner, so this was not AP-free or unattended recovery. Classic TCP
  remained enabled during the TLS check, so the run also does not establish an
  exclusive TLS-only runtime.
- The accepted TLS endpoint later stopped after Android's ADB debugging manager
  observed a network disconnect and disabled Wi-Fi ADB. The `adbd` process did
  not restart, the hosted network remained live, and the Quest was later again
  associated with it; no user or helper disable action was observed. Preserve
  the successful bootstrap result and classify this as a separate durability
  failure. One accepted endpoint does not prove an always-on TLS lease across
  transient network events.
- With ADB configuration finalized before arming, a separate automatic guardian
  restored the original station network without operator recovery. Saved-
  network inventory remained exact and the `adbd` process identity was
  unchanged. This qualifies automatic restoration for that stable-daemon run;
  it does not override the separate result that ADB daemon or transport
  reconfiguration can terminate a detached shell guardian.
- A later read-only inspection on a separate Quest Android 14/API 34 build
  explains that topology result. Secure Wireless Debugging required current
  station Wi-Fi information with a valid network ID, SSID or Passpoint-name
  resolution, and nonempty BSSID; a failed check reset `adb_wifi_enabled`
  before TLS startup. The
  shipped property policy also prevented an ordinary app or UID-2000 shell from
  directly setting the persistent TCP/TLS ADB properties.
- The installed Meta companion service contained separate ADB-mode and wireless
  pairing paths. ADB mode wrote only `adb_enabled`, the USB debugging gate.
  Wireless pairing wrote `adb_wifi_enabled` and invoked the framework pairing
  service, which still uses the network admission above. This confirms a real
  companion-mediated Bluetooth control surface without establishing ADB over
  Bluetooth or an AP-free fresh shell. Historical Quest companion-protocol
  research and newer reports of on-device Shizuku pairing remain useful leads,
  but no post-reboot no-access-point route was exercised in this inspection.
- Keep the earlier lab-headset behavioral tests and the current-headset static
  inspection distinct. An Android 16 Pixel report describes a timing race using
  a hosted hotspot and repeated Wireless Debugging UI actions; it still pairs
  ADB. The two orderings tested on the inspected Quest Android 14 build were
  negative, without settling other versions or race timings.
- A separate guarded saved-source probe reached `uid=2000(shell)` over a live
  WiFi ADB transport and could inspect the active source. It stopped while
  reflecting `NETWORK_SELECTION_ENABLE` as a selection-reason field. Source
  review corrected that diagnosis: in AOSP Android 14,
  `NETWORK_SELECTION_ENABLED` is the enabled-status field, `DISABLED_NONE` is
  the no-disable-reason field, and `NETWORK_SELECTION_ENABLE` is a diagnostic
  label rather than a field. The stopped probe therefore does not establish a
  privilege limitation or an absent target member. A later read-only probe on
  an API 34 Quest build resolved both corrected fields to `0`, resolved the
  disable-reason accessor, and confirmed `NoSuchFieldException` for the old
  label lookup; connectivity remained unchanged. This verifies the target API
  names, not that Termux, an ordinary app, or BLE can autonomously switch the
  headset between WiFi sources. Transition behavior remains pending.
- The first corrected existing-interface integration attempt ended before BLE
  advertising or HOLD. The app reported `exact_shell_probe_failed`; the host
  consequently found no authenticated candidate and recorded
  `device_executed=false`. The app log identifies the first failure: enforcing
  SELinux denied `{ connectto }` from the `untrusted_app` domain to the shell
  domain's intended abstract Unix stream socket. A separate `run-as`
  reproduction also received `Permission denied` while reading the shell
  owner's `/proc/<pid>/stat`, but its distinct `runas_app` context makes that an
  additional incompatible assumption rather than the app's first failure.
  Wi-Fi remained enabled and connected, and typed private cleanup succeeded.
  This is a pre-HOLD IPC integration failure, not evidence that Wi-Fi API
  authority was denied or that a radio cycle succeeded. Further radio-cycle
  work requires an allowed inert app-to-shell IPC proof first.
- A later inert APK-to-shell capability probe established allowed alternatives
  without changing Wi-Fi or Bluetooth state. IPv4 loopback TCP passed in both
  directions with 50 echo samples and an exact 4 MiB integrity transfer. Direct
  abstract Unix stream sockets failed in both directions: focused logs recorded
  enforcing SELinux `{ connectto }` denials for `untrusted_app` to `shell` and
  for `shell` to `untrusted_app`. These are direction- and socket-type-specific
  results; they do not establish pathname-socket, datagram, or other-build
  behavior.
- On the same API 34 test shape, UID-2000 shell successfully acquired an
  exported app provider through Android's exact external-provider Binder
  interface, called it with explicit `com.android.shell` attribution, received
  an app Binder callback, matched an inert token echo, released the provider
  lease, and exited. The provider observed caller UID 2000 and the shell
  callback observed the app UID. A wrong expected-app-UID case returned
  `SecurityException`, produced no callback, and still released the provider
  lease. This qualifies synchronous Binder handoff and the tested UID negative;
  it does not yet qualify wrong-token/replay handling, FD transfer, BLE
  integration, a persistent service, a radio transition, capture, or streaming.
- The first detached transport helper survived its initiating ADB command and
  reached its intended deadline, but a blocked Unix-socket accept worker kept
  the process alive until exact-owner cleanup. This was a cancellation defect
  in the diagnostic implementation, not evidence that Horizon OS prevented
  expiry or that detached shell lifetime was proven. Corrected STOP and
  watchdog results follow below.
- The corrected retained Binder helper then passed bounded pipe and lifecycle
  checks. Binder-carried pipes transferred 4096 bytes and 4 MiB in both
  directions with exact fixed-pattern hashes and EOF, and provider leases were
  released. Status remained available after the initiating ADB command returned
  and while the activity reported `resumed=false`. A wrong callback token was
  rejected with `SecurityException: callback_identity`, and the next valid
  status request still worked.
- On a second Android 14 Quest, an attended headset-local Termux key reached a
  dynamic TLS endpoint supplied by Android NSD after classic port `5555` had
  been disabled. The recovery helper's normal `RunCommandService` execution had
  created the ordinary Termux `untrusted_app` ADB server. With the USB cable
  still connected, the host used `run-as com.termux` to dispatch an ADB client
  request to that existing server; the exact TLS target, rather than the USB
  serial shell, created the detached UID-2000 helper. The app's post-drop probe
  had been scheduled through TLS before Wi-Fi loss, then ran from its local
  timer while Wi-Fi and `adb_wifi_enabled` were off and the TLS listener was
  absent. The same helper PID/start time remained live and Binder-carried pipes
  again transferred 4096 bytes and 4 MiB in both directions with exact hashes.
  A sample after completion still showed the listener absent, the TLS target was
  unreachable, and the `adbd` PID was unchanged. The automatic guardian restored
  the original association without USB radio recovery; typed STOP exited the
  helper and the app observed Binder death. This proves one bounded retained
  Binder/FD lifetime after loss of the launch route. It does not prove a fully
  headset-UI-driven run, long-duration or production streaming, in-flight
  peer-death behavior, daemon-restart survival, sleep, reboot, or unattended
  bootstrap.
- The first host-harness attempt completed the app-local Binder/pipe work but
  its last listener sample preceded completion by 42 ms. It was retained as a
  failed/recovered attempt and used USB Wi-Fi recovery. The corrected rerun
  waited for a post-completion listener sample before accepting the result.
- A separate run removed physical USB from the live BLE radio sequence. With
  Android reporting USB disconnected and unconfigured, classic Wi-Fi ADB
  launched the detached UID-2000 helper and started the ordinary APK's GATT
  service. Signed BLE replies authenticated READY, rejected a bad MAC and a
  replay, accepted a no-op, confirmed Wi-Fi OFF, and later confirmed resume.
  During a measured 10.016-second interval between OFF and resume, five attempts
  to reach the classic Wi-Fi ADB TCP endpoint failed while the BLE connection
  remained live. After the original association and Wi-Fi ADB returned, USB was
  still disconnected, the helper PID/start time and boot ID were unchanged,
  the `adbd` PID/start time was unchanged, and the saved-network inventory was
  byte-identical. Shell events recorded the UID-2000 disable/enable effects and
  guardian shutdown before `RESTORED`; typed STOP exited the helper and the app
  reported stopped. The aggregate harness retained a failed status because it
  compared CRLF-decoded command output with LF-normalized text after the radio
  cycle; the preserved raw inventory bytes and hashes were equal. This proves
  one bounded no-USB BLE control cycle after classic Wi-Fi ADB bootstrap. It
  proves discrete shell-confirmed OFF/RESTORED states and five failed TCP
  observations, not continuous radio telemetry, absence of every network route,
  autonomous bootstrap, reboot survival, long-duration behavior, or a product
  control plane.
- Explicit STOP terminated the corrected shell helper, after which the APK
  observed Binder death and `DeadObjectException`. Force-stopping only the test
  APK caused a separate shell helper to observe app death and exit. A real
  three-second watchdog expired and terminated another helper, and the APK
  observed its Binder death. These are short bounded results; they do not prove
  in-flight peer-death FD closure, long-background or sleep/power behavior,
  reboot/package-replacement survival, ADB daemon or transport-loss survival,
  or product streaming performance.
- The test APK ran in `untrusted_app` with seccomp mode 2 and zero permitted and
  effective capabilities. It could read the boot ID, but its read of
  `/proc/<live-shell-pid>/stat` returned `ENOENT` while the shell process was
  independently confirmed alive. Treat this as an app-side process-visibility
  boundary, not proof that the shell process is absent. One initial host receipt
  also contained malformed JSON because raw tab characters in UID/GID values
  were not escaped; raw evidence was preserved, the private parsed copy alone
  was normalized, and the source was fixed for future builds.
- A separate bounded ADB-shell display-acquisition check captured one valid
  3664×1920 PNG whose inspected content contained the physical stereo
  passthrough view and 2D panels. A two-second raw H.264 `screenrecord` at
  1832×960 and 8 Mbit/s produced 945002 bytes; 132 decoded frames had 132
  unique hashes, both recorder and decoder exited successfully, and no recorder
  remained. The raw stream's reported `1200000/1` frame rate is invalid timing
  evidence. This proves a bounded shell acquisition route only, separate from
  the APK/Binder pipe: it does not prove capture-to-APK integration, audio,
  protected-content or complete-XR-layer coverage, Camera API access, frame
  rate, latency, or streaming performance.
- A final bounded BLE-to-Binder behavior check authenticated a signed READY for
  the exact run, rejected a bad MAC and a replay, and delivered a valid no-op
  through the ordinary APK to the UID-2000 shell helper. Only Bluetooth connect
  and advertise runtime permissions were granted to the new APK. This qualifies
  the tested app/helper path, not a general BLE command channel.
- A signed BLE request then disabled Wi-Fi. USB readback confirmed the effective
  disabled state while the BLE connection remained active. A later signed
  request re-enabled Wi-Fi; USB readback confirmed enabled state, the original
  association rejoined, saved-network inventory was byte-equal, the Wi-Fi ADB
  TCP port remained `0`, and typed STOP terminated the helper. Bluetooth was ON
  before and after. This is one reversible Wi-Fi enable-state cycle, not saved-
  profile switching, autonomous Wi-Fi ADB recovery, or blanket Wi-Fi authority.
- The restore guardian was positively identified while Wi-Fi was off as an
  exact UID-2000 child of the shell server, then stopped and reaped after normal
  resume. Java process-PID reflection returned `-1`; independent USB process
  evidence identified the child, so the reflective value was a metadata limit,
  not a permission denial. Automatic guardian expiry/restoration was not
  exercised.
- The first attempt with the same APK reached Wi-Fi-off, but its host logger
  could not serialize a non-primitive BLE connection-state object and therefore
  never sent resume. Typed STOP and an eager USB recovery restored Wi-Fi. After
  fixing only host Boolean conversion and STOP settlement, the same APK was
  rerun without rebuilding and completed the cycle above. Classify the first
  attempt as failed/recovered, not a partial successful cycle.
- Final cleanup matched the original package inventory and original APK hash,
  Wi-Fi association and saved-network inventory, Wi-Fi and Bluetooth enabled
  state, Wi-Fi ADB properties, stay-awake state, and ADB forward/reverse sets.
  All diagnostic processes, the recorder, staged files, and the new APK were
  absent, and the coordination lease was released.
- A baseline on-device Android APK toolchain can build, sign, install, and
  launch a simple source-only Activity APK from Quest Termux.
- A Rust native library can be compiled on the headset and packaged into a
  native APK experiment, but this currently proves native packaging only. It
  does not prove OpenXR session creation or XR rendering.
- Quest launch-check and controller prompts can block an otherwise valid
  launch. Treat the protected prompt as operator-gated readiness evidence, not
  as a build failure.
- Shell-level Android task resizing is not a reliable product route for this
  case. It can create mismatched task and root bounds that reintroduce cropped
  or sliced desktop output.

## Still Open

- Robust landscape desktop-size geometry directly inside the Termux:X11
  Android activity, including clean activity/surface alignment.
- Manual Quest cursor input and keyboard behavior against the native-wide
  Termux:X11 surface.
- Longer validation of the landscape viewer panel, including sustained MJPEG
  frame rate, input expectations, and cleanup behavior.
- Low-latency large-panel rendering and input forwarding from the viewer panel
  back into the Linux desktop.
- Background desktop execution while another Quest app is foregrounded, with a
  controlled message route for commands or launch requests.
- Longer broker-feedback sidecar survival tests across app focus changes,
  broker restarts, battery restrictions, network interruptions, and explicit
  sidecar stop/restart cycles.
- Longer background-service survival tests across sleep, focus changes,
  battery policy, and foreground-service constraints.
- Text-heavy terminal or editor ergonomics.
- Full desktop performance and long-session stability.
- Live stream frame rate, latency, and CPU cost across longer sessions.
- Wake-lock behavior without external guard conditions.
- An OS-supported way for a normal pre-granted helper to re-enable the Wi-Fi
  ADB transport after reboot without Meta's protected alert. The tested build
  requires the attended **Restore Now** fallback.
- A Horizon OS-supported Wireless Debugging path over a Quest-owned Wi-Fi
  Direct group or local-only hotspot. Both tested self-hosted topologies provide
  local networking but fail the platform's infrastructure-network gate.
- WiFi ADB survival across debugging timeout, adbd restart, and user
  revocation after an active lease is already established.
- A framework-supported, fully observable saved-source transition with
  effective-state readback from a WiFi-ADB `uid=2000(shell)` lease using the
  target-verified selection fields.
- Makepad APK builds directly inside Quest Linux.
- OpenXR session creation and real headset-rendered XR frames from an
  on-device-built APK.
- Signed release artifact provenance for Git-backed APK download/install flows.
- Graphics acceleration and renderer classification.
- Audio and remote shell services.
