package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.util.Log
import java.io.Closeable

class CameraToInkscapeLauncher(
  private val context: Context,
  private val onState: (String) -> Unit,
) : Closeable {
  private val receiver =
    object : BroadcastReceiver() {
      override fun onReceive(receiverContext: Context?, intent: Intent?) {
        val result = intent?.getBundleExtra(EXTRA_RESULT)
        val exitCode = result?.getInt("exitCode", Int.MIN_VALUE) ?: Int.MIN_VALUE
        Log.i(TAG, "SPATIAL_DESKTOP_CAMERA_IMPORT_RESULT exit=$exitCode")
        onState(if (exitCode == 0) "camera-import=launched" else "camera-import=failed exit=$exitCode")
      }
    }
  private var registered = true

  init {
    context.registerReceiver(receiver, IntentFilter(RESULT_ACTION), Context.RECEIVER_NOT_EXPORTED)
  }

  fun launch(cameraId: String, url: String, token: String) {
    require(cameraId == "50" || cameraId == "51") { "camera ID must be 50 or 51" }
    require(url.startsWith("http://127.0.0.1:") && url.endsWith("/snapshot.jpg")) { "snapshot URL must be loopback" }
    require(token.matches(Regex("[0-9a-f]{64}"))) { "invalid snapshot token" }
    val resultIntent = Intent(RESULT_ACTION).setPackage(context.packageName)
    val resultPendingIntent =
      PendingIntent.getBroadcast(
        context,
        url.hashCode(),
        resultIntent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
      )
    val command =
      Intent(RUN_COMMAND_ACTION)
        .setComponent(ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE))
        .putExtra(EXTRA_PATH, HELPER_PATH)
        .putExtra(EXTRA_ARGUMENTS, arrayOf("--url", url, "--token", token, "--camera-id", cameraId))
        .putExtra(EXTRA_WORKDIR, HOME)
        .putExtra(EXTRA_BACKGROUND, true)
        .putExtra(EXTRA_PENDING_INTENT, resultPendingIntent)
    context.startForegroundService(command)
  }

  override fun close() {
    if (registered) {
      registered = false
      runCatching { context.unregisterReceiver(receiver) }
    }
  }

  companion object {
    private const val TAG = "SpatialDesktop"
    private const val TERMUX_PACKAGE = "com.termux"
    private const val RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService"
    private const val RUN_COMMAND_ACTION = "com.termux.RUN_COMMAND"
    private const val EXTRA_PATH = "com.termux.RUN_COMMAND_PATH"
    private const val EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS"
    private const val EXTRA_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR"
    private const val EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND"
    private const val EXTRA_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT"
    private const val EXTRA_RESULT = "result"
    private const val RESULT_ACTION = "io.github.mesmerprism.questtermuxlab.spatialdesktop.CAMERA_IMPORT_RESULT"
    private const val HELPER_PATH = "/data/data/com.termux/files/usr/local/bin/quest-camera2-to-inkscape"
    private const val HOME = "/data/data/com.termux/files/home"
  }
}
