package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.util.Log
import java.io.Closeable

/** Starts only the fixed, installed Termux virtual-microphone helper. */
class QuestMicrophoneBridgeLauncher(
  private val context: Context,
  private val onResult: (Boolean) -> Unit,
) : Closeable {
  private val receiver =
    object : BroadcastReceiver() {
      override fun onReceive(receiverContext: Context?, intent: Intent?) {
        val result = intent?.getBundleExtra(EXTRA_RESULT)
        val exitCode = result?.getInt("exitCode", Int.MIN_VALUE) ?: Int.MIN_VALUE
        val stderr = result?.getString("stderr").orEmpty().replace('\n', ' ').take(MAX_RESULT_CHARS)
        Log.i(TAG, "SPATIAL_DESKTOP_MIC_SIDECAR_RESULT exit=$exitCode stderr=$stderr")
        onResult(exitCode == 0)
      }
    }
  private var registered = true

  init {
    context.registerReceiver(receiver, IntentFilter(RESULT_ACTION), Context.RECEIVER_NOT_EXPORTED)
  }

  fun start() {
    val resultIntent = Intent(RESULT_ACTION).setPackage(context.packageName)
    val resultPendingIntent =
      PendingIntent.getBroadcast(
        context,
        REQUEST_CODE,
        resultIntent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
      )
    val command =
      Intent(RUN_COMMAND_ACTION)
        .setComponent(ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE))
        .putExtra(EXTRA_PATH, HELPER_PATH)
        .putExtra(EXTRA_ARGUMENTS, arrayOf("start"))
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
    private const val RESULT_ACTION = "io.github.mesmerprism.questtermuxlab.spatialdesktop.MIC_SIDECAR_RESULT"
    private const val HELPER_PATH = "/data/data/com.termux/files/usr/local/bin/quest-mic-pulse-bridge"
    private const val HOME = "/data/data/com.termux/files/home"
    private const val REQUEST_CODE = 5911
    private const val MAX_RESULT_CHARS = 256
  }
}
