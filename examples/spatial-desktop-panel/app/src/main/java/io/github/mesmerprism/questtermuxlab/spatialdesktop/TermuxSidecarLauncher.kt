package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Handler
import android.os.Looper
import android.util.Log

class TermuxSidecarLauncher(private val context: Context) {
  fun start() {
    registerResultReceiver()
    dispatch(
      label = "repository",
      path = "$PREFIX/bin/pkg",
      arguments = arrayOf("install", "-y", "x11-repo"),
      workdir = HOME,
    )
  }

  private fun registerResultReceiver() {
    context.registerReceiver(
      object : BroadcastReceiver() {
        override fun onReceive(receiverContext: Context?, intent: Intent?) {
          val result = intent?.getBundleExtra(EXTRA_RESULT)
          val label = intent?.getStringExtra(EXTRA_RESULT_LABEL) ?: "unknown"
          val exitCode = result?.getInt("exitCode", Int.MIN_VALUE)
          val stdout = result?.getString("stdout").orEmpty().replace('\n', ' ').take(MAX_RESULT_CHARS)
          val stderr = result?.getString("stderr").orEmpty().replace('\n', ' ').take(MAX_RESULT_CHARS)
          val error = result?.getString("errmsg").orEmpty().replace('\n', ' ').take(MAX_RESULT_CHARS)
          Log.i(TAG, "SPATIAL_DESKTOP_SIDECAR_RESULT label=$label exit=$exitCode stdout=$stdout stderr=$stderr error=$error")
          if (label == "repository" && exitCode == 0) installVnc()
          if (label == "dependency" && exitCode == 0) startX11()
        }
      },
      IntentFilter(RESULT_ACTION),
      Context.RECEIVER_NOT_EXPORTED,
    )
  }

  private fun installVnc() {
    dispatch(
      label = "dependency",
      path = "$PREFIX/bin/pkg",
      arguments = arrayOf("install", "-y", "x11vnc", "termux-x11-nightly", "xfce4", "xorg-xrandr"),
      workdir = HOME,
    )
  }

  private fun startX11() {
    dispatch(
      label = "x11",
      path = "$PREFIX/bin/env",
      arguments =
        arrayOf(
          "DISPLAY=:1",
          "$PREFIX/bin/termux-x11",
          ":1",
          "-ac",
          "-dpi",
          "120",
          "-xstartup",
          "dbus-launch --exit-with-session xfce4-session",
        ),
      workdir = HOME,
    )
    Handler(Looper.getMainLooper()).postDelayed(
      {
        dispatch(
          label = "geometry",
          path = "$PREFIX/bin/env",
          arguments = arrayOf("DISPLAY=:1", "$PREFIX/bin/xrandr", "--display", ":1", "--fb", "1280x720"),
          workdir = HOME,
        )
      },
      GEOMETRY_DELAY_MS,
    )
    Handler(Looper.getMainLooper()).postDelayed(
      {
        dispatch(
          label = "vnc",
          path = "$PREFIX/bin/env",
          arguments =
            arrayOf("DISPLAY=:1", "$PREFIX/bin/x11vnc", "-display", ":1", "-localhost", "-rfbport", "5900", "-nopw", "-forever", "-shared"),
          workdir = HOME,
        )
        Log.i(TAG, "SPATIAL_DESKTOP_SIDECAR_START_DISPATCHED display=:1 requestedGeometry=1280x720 rfb=127.0.0.1:5900")
      },
      VNC_DELAY_MS,
    )
  }

  private fun dispatch(label: String, path: String, arguments: Array<String>, workdir: String) {
    val resultIntent = Intent(RESULT_ACTION).setPackage(context.packageName).putExtra(EXTRA_RESULT_LABEL, label)
    val resultPendingIntent =
      PendingIntent.getBroadcast(
        context,
        label.hashCode(),
        resultIntent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
      )
    val command =
      Intent(RUN_COMMAND_ACTION)
        .setComponent(ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE))
        .putExtra(EXTRA_PATH, path)
        .putExtra(EXTRA_ARGUMENTS, arguments)
        .putExtra(EXTRA_WORKDIR, workdir)
        .putExtra(EXTRA_BACKGROUND, true)
        .putExtra(EXTRA_PENDING_INTENT, resultPendingIntent)
    context.startForegroundService(command)
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
    private const val RESULT_ACTION = "io.github.mesmerprism.questtermuxlab.spatialdesktop.SIDECAR_RESULT"
    private const val EXTRA_RESULT_LABEL = "result_label"
    private const val PREFIX = "/data/data/com.termux/files/usr"
    private const val HOME = "/data/data/com.termux/files/home"
    private const val VNC_DELAY_MS = 8_000L
    private const val GEOMETRY_DELAY_MS = 5_000L
    private const val MAX_RESULT_CHARS = 512
  }
}
