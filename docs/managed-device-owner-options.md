# Managed Device Owner Options For APK Fleets

This note records the 2026-06-11 research pass on whether managed device-owner
paths can replace per-device manual APK updates for Quest headsets and Android
phones. It is an architecture note, not live-device evidence.

## Bottom Line

For Android phones and tablets, Android Enterprise fully managed or dedicated
device-owner mode is the strongest production path. A device-owner DPC or
Android Management API policy can manage installation, updates, permissions,
kiosk mode, network policy, and status reporting on supported devices.

For Quest, do not assume standard Android Enterprise device-owner support.
Quest runs Android-based Horizon OS, but public Meta documentation points to
Meta-managed device enrollment, Meta Device Manager, private apps, Shared Mode,
and third-party XR MDM paths rather than arbitrary customer DPC provisioning.
Treat full `DevicePolicyManager` and silent customer `PackageInstaller` control
on Quest as vendor-confirmation work.

Termux plus authorized WiFi ADB remains useful for lab devices and break-glass
fleet recovery. It is not durable enough to be the primary management plane for
100+ production devices because the ADB lease can disappear after reboot, adbd
restart, timeout, network change, or user revocation.

## Decision Matrix

| Path | Fit | Silent APK update | Provisioning | Main risk |
| --- | --- | --- | --- | --- |
| Consumer Quest developer mode | Lab only | Via ADB while authorized | Developer mode plus ADB authorization | Fragile, not a fleet MDM plane |
| Meta-managed Quest / XR MDM | Best Quest candidate | Vendor-dependent | Meta-managed enrollment / MDM | Public docs do not prove Android Enterprise device owner |
| Android phone device owner | Best phone path | Yes, documented for device owner / affiliated profile owner | Initial setup or factory reset | Requires managed provisioning discipline |
| Android phone profile owner | Partial | Work-profile scope only | Work-profile enrollment | Not whole-device kiosk/control |
| Termux plus WiFi ADB | Fallback | Yes through `adb install -r` while lease is live | External/user-authorized ADB, Termux agent | Lease loss and reboot recovery |

## Quest Implications

Use Meta-managed Quest enrollment and an XR-capable MDM for a serious Quest
fleet. Validate these facts with Meta or the MDM vendor before depending on
them:

- unattended APK install/update behavior;
- whether updates require headset, user, or admin confirmation;
- Shared Mode versus Individual Mode behavior;
- kiosk launch and app relaunch after reboot;
- runtime permission management;
- Wi-Fi and certificate policy;
- OS update policy;
- deployment status APIs and webhooks;
- app inventory and install failure reporting;
- log/status collection boundaries.

Do not design the Quest production path around a customer-controlled Android
Enterprise DPC unless Meta or the MDM vendor confirms support for the target
Quest SKUs and enrollment mode in writing.

Do not assume a managed Quest app is allowed to download and initiate
installation of APK files. The managed Quest path should be MDM/platform-owned
unless policy confirmation says otherwise.

## Android Phone Implications

For owned phones and tablets, use Android Enterprise fully managed or dedicated
device-owner mode. Provision during initial setup or after factory reset.

Recommended phone paths:

- Android Management API plus Android Device Policy and managed Google Play
  private apps, if private Play delivery is acceptable.
- A custom device-owner DPC using `PackageInstaller.Session`, if APK delivery
  must stay outside Play.

Release engineering requirements stay the same:

- stable package name;
- compatible signing certificate or signing lineage;
- monotonically increasing `versionCode`;
- rollback builds with higher version codes rather than ordinary downgrades;
- split APK sessions with one base APK and matching package/version/signing.

## Role Of `apk.update_verified`

The fleet command added in this repository remains valuable, but its role is
narrow:

- lab Quest devices with developer mode and an authorized local WiFi ADB lease;
- break-glass recovery when the managed plane misses a device;
- internal smoke tests against private APK artifacts;
- development of fleet manifest, idempotency, rollout-ring, and evidence
  semantics before committing to an MDM vendor.

It is not a replacement for Meta-managed Quest enrollment, Android Enterprise
device owner, or a supported MDM.

When local ADB is missing, `apk.update_verified` should fail closed and report
`central_direct_adb_recovery`. The central recovery path remains owned by the
live Quest operations workflow, not the Termux agent itself.

## Recommended Architecture

Use two production management planes:

- Quest: Meta-managed Quest enrollment plus Meta Device Manager or a vetted
  third-party XR MDM, with app-level heartbeat and smoke-test telemetry inside
  the Quest APKs.
- Android phones: Android Enterprise fully managed / dedicated device owner,
  using AMAPI/private managed Play or a custom DPC depending on distribution
  constraints.

Use a shared app-level agent contract for routine status:

- app version and build hash;
- content/schema version;
- battery and network summary;
- bounded structured logs;
- privacy-safe smoke-test results;
- permissions and backend reachability self-checks.

Use ADB and Termux only for lab automation and break-glass recovery.

## Minimal POC Plan

Android phones:

1. Factory reset 3-5 devices.
2. Enroll as fully managed or dedicated device owner.
3. Test AMAPI/private managed Play install and, if needed, a custom DPC
   `PackageInstaller.Session` install.
4. Verify silent install, silent update, wrong-signature failure, downgrade
   behavior, permission grant, kiosk, Wi-Fi config, reboot recovery, and app
   telemetry.

Quest:

1. Enroll 5 devices through the Meta-managed path.
2. Test Shared Mode and Individual Mode if both are relevant.
3. Deploy the questionnaire panel APK and Unity APK through private app,
   self-hosted APK URL, and at least one third-party MDM path.
4. Verify update confirmation behavior, retries after offline/reboot, kiosk
   relaunch, permission handling, Wi-Fi/cert handling, deployment status APIs,
   and logging boundaries.

Termux/ADB fallback:

1. Use 3 lab Quest devices with developer mode and authorized ADB.
2. Run the outbound Termux fleet agent with local ADB disabled, then enabled.
3. Exercise `adb.self_check`, `apk.update_verified`, allowlisted launch,
   foreground snapshot, and logcat slice.
4. Explicitly test reboot, Wi-Fi change, ADB key revocation, and sleep/wake.

## Vendor Questions

Ask Meta and MDM vendors:

- Can the target Quest SKU/enrollment mode be a standard Android Enterprise
  device owner with a customer DPC?
- Can APK updates be silent with no headset confirmation and no per-update admin
  acceptance?
- Are install/update APIs available for CI/CD rings and retries?
- Can runtime permissions be granted centrally?
- Can apps be launched or relaunched after reboot in kiosk/shared mode?
- What status, inventory, failure reason, and log APIs are available?
- What are the rules for apps downloading or installing APK files on managed
  Quest devices?

## Sources

Research source URLs from the 2026-06-11 intake:

- Meta private apps for managed devices:
  https://developers.meta.com/horizon/resources/qfb-private-apps-dist/
- Meta Quest Android device setup:
  https://developers.meta.com/horizon/documentation/native/android/mobile-device-setup/
- Android device administration:
  https://source.android.com/docs/devices/admin
- Android Debug Bridge:
  https://developer.android.com/tools/adb
- Android `PackageInstaller`:
  https://developer.android.com/reference/kotlin/android/content/pm/PackageInstaller
- Android `DevicePolicyManager`:
  https://developer.android.com/reference/android/app/admin/DevicePolicyManager
- Android Management API provisioning:
  https://developers.google.com/android/management/provision-device
- Google Play EMM private apps:
  https://developers.google.com/android/work/play/emm-api/private-apps
- Android dedicated devices / lock task:
  https://developer.android.com/work/dpc/dedicated-devices/lock-task-mode
- Android Management API policies:
  https://developers.google.com/android/management/reference/rest/v1/enterprises.policies
- Termux:Boot:
  https://github.com/termux/termux-boot
