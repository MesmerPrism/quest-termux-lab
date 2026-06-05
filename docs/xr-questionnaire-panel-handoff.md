# XR Questionnaire Panel Handoff

This note describes a public-safe Quest test pattern for launching a reusable
2D questionnaire app from any cooperating foreground XR app, then returning to
the same XR app without using the Meta menu and without force-stopping either
package.

Status: design and test recipe. This repository has not yet recorded a public
live-device pass for the cross-package handoff.

## General Approach

Same-package hybrid apps are not required. They are only a useful reference
baseline because Meta documents the behavior of a 2D panel activity and an
immersive activity inside one APK.

The reusable feature should be cross-package:

1. The questionnaire APK exposes an exported Quest 2D panel activity.
2. A foreground XR app calls a small launch command or SDK wrapper.
3. The launch includes a questionnaire session id and a return route supplied
   by the XR app.
4. Horizon brings the questionnaire panel to the foreground and routes normal
   Quest pointer, hand, controller, keyboard, or gamepad input to the focused
   panel.
5. The questionnaire saves or publishes its answers through a separate result
   channel.
6. The questionnaire invokes the return route and closes only its panel
   activity.
7. The existing XR app instance returns to foreground/focus if the platform
   kept it alive.

The foreground switch and the questionnaire answer transport are separate
contracts. Do not depend on the activity foreground change as the answer
delivery path.

## Questionnaire Activity

The questionnaire app should expose a normal exported 2D panel activity. A
minimal manifest shape is:

```xml
<activity
    android:name=".QuestionnaireActivity"
    android:exported="true"
    android:resizeableActivity="true"
    android:configChanges="keyboard|keyboardHidden|orientation|screenLayout|screenSize|smallestScreenSize">
    <intent-filter>
        <action android:name="org.example.quest.action.START_QUESTIONNAIRE" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="com.oculus.intent.category.2D" />
    </intent-filter>
    <layout
        android:defaultHeight="720dp"
        android:defaultWidth="1080dp"
        android:minHeight="540dp"
        android:minWidth="720dp" />
</activity>
```

Add `android.intent.action.MAIN` plus `android.intent.category.LAUNCHER` if
the questionnaire should also be user-launchable from the normal app library.
Add `com.oculus.intent.category.OVERLAY_LAUNCHER` only after a headset pass
proves that it gives the desired overlay behavior for the target OS version.

## XR Caller Contract

The XR app should call the questionnaire only while the XR app is already
foregrounded. The caller should pass:

- a stable questionnaire session id;
- an optional schema or questionnaire id;
- a result destination, such as a content provider, app-owned shared file,
  broker endpoint, local service endpoint, or backend session id;
- a return route created by the XR app.

A return `PendingIntent` is the preferred return route. It preserves the exact
initiating activity and avoids the questionnaire app needing to guess which XR
package to foreground later.

```kotlin
val returnIntent = Intent().apply {
    setComponent(ComponentName(packageName, VrActivity::class.java.name))
    action = Intent.ACTION_MAIN
    addCategory("com.oculus.intent.category.VR")
    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
    addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
}

val returnToXr = PendingIntent.getActivity(
    this,
    sessionId.hashCode(),
    returnIntent,
    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
)

val questionnaireIntent =
    Intent("org.example.quest.action.START_QUESTIONNAIRE").apply {
        setPackage("org.example.quest.questionnaire")
        addCategory(Intent.CATEGORY_DEFAULT)
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        putExtra("session_id", sessionId)
        putExtra("return_to_xr", returnToXr)
    }

startActivity(questionnaireIntent)
```

The XR activity should use a launch mode or flags that resume the existing XR
task instead of creating a second immersive instance.

## Return To XR

The questionnaire panel should return to XR by invoking the supplied return
route, then closing only its visible activity:

```kotlin
fun returnToXrAndClose(activity: Activity) {
    val returnToXr =
        activity.intent.getParcelableExtra<PendingIntent>("return_to_xr")
    returnToXr?.send()
    activity.finish()
}
```

Do not use `am force-stop`, process killing, or package restarts as the normal
return path. If the questionnaire app needs background work after the panel
closes, put that work in an explicit service or sidecar layer; do not treat the
closed activity as durable runtime state.

If a return `PendingIntent` is not available, a configured package/activity
name can be a fallback. That fallback needs package visibility handling,
clear user/operator configuration, and error reporting for missing packages,
duplicate tasks, or protected launch prompts.

## Expected Focus Behavior

While the questionnaire is focused, the XR app may remain alive but should not
expect XR input focus. In OpenXR terms, the expected transition is:

```text
XR foreground focused -> questionnaire panel focused -> XR focused again
```

The middle state may leave the XR app `VISIBLE` rather than `FOCUSED`. The XR
app must tolerate pause, visible, and focus transitions without tearing down
the session unless the platform requires it.

## Termux And ADB Boundary

The product UX should not require ADB. The normal product route is:

```text
foreground XR app -> start questionnaire panel -> questionnaire return route
```

Termux and WiFi ADB are lab fallback tools only. Use them when testing,
installing, launching, or recovering apps before the app-to-app contract is
implemented.

Termux is a normal Android app. It becomes useful as an ADB launcher only after
an external or user-visible workflow enables or pairs WiFi ADB, and the local
ADB client proves Android shell identity:

```sh
adb connect 127.0.0.1:5555
adb -s 127.0.0.1:5555 shell id
```

The pass condition is:

```text
uid=2000(shell)
```

Without that shell identity, do not treat Termux `am start` as launch
authority.

## Test Checklist

Use `examples/session-recipe.xr-questionnaire-panel-handoff.json` as the
compact run checklist.

Minimum public-safe test:

1. Install a test XR app that can log OpenXR session state and expose a visible
   command to open the questionnaire.
2. Install a separate questionnaire APK with an exported Quest 2D panel
   activity.
3. Start the XR app and confirm it is foregrounded and focused.
4. Trigger the questionnaire launch from inside the XR app.
5. Confirm the questionnaire appears as a focused 2D panel and receives Quest
   input.
6. Confirm the XR app process remains alive while the panel is focused.
7. Press the questionnaire app's return control.
8. Confirm the panel closes and the same XR app instance returns to foreground.
9. Confirm no `force-stop`, package kill, Meta menu navigation, or ADB launch
   was used in the product-path pass.

Record evidence privately first:

- headset model and OS version;
- caller package/activity and questionnaire package/activity;
- foreground surface before launch, during questionnaire, and after return;
- OpenXR session state changes for the XR app;
- process liveness for both packages;
- whether any protected prompt or controller requirement appeared;
- whether screenshots, cast, direct stream, or human witness supplied the
  visual evidence.

Publish only sanitized derivatives. Do not publish device serials, private
package IDs, screenshots, raw logs, pairing data, local paths, or generated
APKs.

## Related Docs

- `docs/META_QUEST_WORKFLOW_INTEGRATION.md`
- `docs/SAFETY_AND_AUTHORITY_BOUNDARY.md`
- `docs/on-device-apk-build-install-launch.md`
- `examples/session-recipe.xr-questionnaire-panel-handoff.json`
