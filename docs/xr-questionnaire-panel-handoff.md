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
5. The questionnaire writes its final JSON to a caller-owned `content://`
   result URI.
6. The questionnaire invokes the return route and closes only its panel
   activity.
7. The existing XR app instance returns to foreground/focus if the platform
   kept it alive.

The foreground switch and the questionnaire answer transport are separate
contracts. Do not depend on the activity foreground change as the answer
delivery path.

The recommended result channel is XR-owned: the foreground XR app creates a
per-session result file in private app storage, exposes only that file through a
narrow `FileProvider` or custom `ContentProvider`, grants the questionnaire
write access to the resulting `content://` URI, and later reads/validates the
JSON itself. This is normal Android app-to-app IPC. It does not require Termux,
WiFi ADB, shared public storage, or a file-drop sidecar.

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
- a per-request id and random nonce;
- an optional schema or questionnaire id;
- small request metadata or JSON inline, or a request URI for larger payloads;
- a caller-owned result `content://` URI, usually backed by an XR-owned
  `FileProvider` or custom provider;
- a return route created by the XR app.

A return `PendingIntent` is the preferred return route. It preserves the exact
initiating activity and avoids the questionnaire app needing to guess which XR
package to foreground later.

For the simple path, grant only write access to the result URI and keep the
request payload in launch extras. Be careful when using several URIs in one
Intent: Android grant flags apply to Intent data and `ClipData`, so broad
read/write flags can give the panel app more access than intended. Use manual
per-URI grants or a custom provider when request and result streams need
different modes.

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

val resultUri = FileProvider.getUriForFile(
    this,
    "${packageName}.questionnaire.results",
    resultFile
)

val questionnaireIntent =
    Intent("org.example.quest.action.START_QUESTIONNAIRE").apply {
        setPackage("org.example.quest.questionnaire")
        addCategory(Intent.CATEGORY_DEFAULT)
        setDataAndType(
            resultUri,
            "application/vnd.example.questionnaire-result+json"
        )
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        putExtra("request_id", requestId)
        putExtra("request_nonce", nonce)
        putExtra("session_id", sessionId)
        putExtra("request_json", requestJson)
        putExtra("result_uri", resultUri)
        putExtra("return_to_xr", returnToXr)
    }

startActivity(questionnaireIntent)
```

The XR activity should use a launch mode or flags that resume the existing XR
task instead of creating a second immersive instance.

Persist the request id, nonce, expected result URI, and resume state before
launch. The callback may arrive after the XR process was paused, stopped, or
cold-started.

## Result URI Contract

Default product route:

```text
XR app private storage
  -> opaque per-request result file
  -> XR-owned FileProvider/custom provider exposes one content:// URI
  -> questionnaire receives a write grant
  -> questionnaire writes result JSON before return
  -> XR app reads and validates result after callback or resume
```

Use a narrow provider path whitelist, `exported=false`, and
`grantUriPermissions=true` for a `FileProvider`. Avoid public `/sdcard`
directories, MediaStore, broad provider roots, `file://` URIs, and participant
answers in PendingIntent extras.

Recommended result envelope:

```json
{
  "schema": "org.example.quest.questionnaire.result.v1",
  "request_id": "opaque-request-id",
  "nonce": "random-per-request-nonce",
  "status": "completed",
  "questionnaire": {
    "id": "presence-v2",
    "version": 2
  },
  "answers": {},
  "started_at": "2026-06-10T12:00:00Z",
  "submitted_at": "2026-06-10T12:03:00Z"
}
```

The XR app should verify schema, request id, nonce, status, questionnaire
id/version, and answer shape before ingesting the result. Keep answer payloads
out of public logs and public fixtures.

## Return To XR

The questionnaire panel should write the final result first, close the stream,
invoke the supplied return route, then close only its visible activity:

```kotlin
fun returnToXrAndClose(activity: Activity) {
    activity.contentResolver.openOutputStream(resultUri, "wt").use { out ->
        out!!.write(resultJson.toByteArray(Charsets.UTF_8))
    }
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
foreground XR app
  -> start questionnaire panel
  -> questionnaire writes caller-owned content:// result
  -> questionnaire return route
```

Termux and WiFi ADB are lab fallback tools only. Use them when testing,
installing, launching, or recovering apps before the app-to-app contract is
implemented. Do not use Termux file drops, Termux-local ADB, public shared
storage, or shell-controlled relaunches as the product result channel.

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
7. Submit the questionnaire and confirm it writes result JSON to the
   caller-owned `content://` URI.
8. Press the questionnaire app's return control.
9. Confirm the panel closes and the same XR app instance returns to foreground.
10. Confirm no `force-stop`, package kill, Meta menu navigation, shared public
    storage, Termux file drop, or ADB launch
   was used in the product-path pass.

Record evidence privately first:

- headset model and OS version;
- caller package/activity and questionnaire package/activity;
- foreground surface before launch, during questionnaire, and after return;
- OpenXR session state changes for the XR app;
- process liveness for both packages;
- result URI ownership, grant mode, and validation status without answer
  payloads;
- whether any protected prompt or controller requirement appeared;
- whether screenshots, cast, direct stream, or human witness supplied the
  visual evidence.

Publish only sanitized derivatives. Do not publish device serials, private
package IDs, screenshots, raw logs, pairing data, local paths, or generated
APKs.

## Related Docs

- Quest Questionnaire Panel:
  https://github.com/MesmerPrism/quest-questionnaire-panel/blob/main/docs/remote-operations-relationship.md
- `docs/META_QUEST_WORKFLOW_INTEGRATION.md`
- `docs/SAFETY_AND_AUTHORITY_BOUNDARY.md`
- `docs/on-device-apk-build-install-launch.md`
- `examples/session-recipe.xr-questionnaire-panel-handoff.json`
