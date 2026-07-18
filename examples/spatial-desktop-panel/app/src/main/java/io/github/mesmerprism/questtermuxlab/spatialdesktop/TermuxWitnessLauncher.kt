package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.util.Log

class TermuxWitnessLauncher(private val context: Context) {
  fun start() {
    val command =
      Intent(RUN_COMMAND_ACTION)
        .setComponent(ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE))
        .putExtra(EXTRA_PATH, "$PREFIX/bin/env")
        .putExtra(
          EXTRA_ARGUMENTS,
          arrayOf(
            "DISPLAY=:1",
            "$PREFIX/bin/xfce4-terminal",
            "--display=:1",
            "--geometry=70x20+100+100",
            "--title=SpatialDesktopWitness",
          ),
        )
        .putExtra(EXTRA_WORKDIR, HOME)
        .putExtra(EXTRA_BACKGROUND, true)
    context.startForegroundService(command)
    Log.i(TAG, "SPATIAL_DESKTOP_WITNESS_DISPATCHED kind=xfce4-terminal display=:1")
  }

  fun stop() {
    val command =
      Intent(RUN_COMMAND_ACTION)
        .setComponent(ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE))
        .putExtra(EXTRA_PATH, "$PREFIX/bin/pkill")
        .putExtra(
          EXTRA_ARGUMENTS,
          arrayOf("-f", "^$PREFIX/bin/xfce4-terminal .*--title=SpatialDesktopWitness$"),
        )
        .putExtra(EXTRA_WORKDIR, HOME)
        .putExtra(EXTRA_BACKGROUND, true)
    context.startForegroundService(command)
    Log.i(TAG, "SPATIAL_DESKTOP_WITNESS_STOP_DISPATCHED kind=xfce4-terminal")
  }

  private fun dispatch(arguments: Array<String>) {
    val command =
      Intent(RUN_COMMAND_ACTION)
        .setComponent(ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE))
        .putExtra(EXTRA_PATH, "$PREFIX/bin/env")
        .putExtra(EXTRA_ARGUMENTS, arguments)
        .putExtra(EXTRA_WORKDIR, HOME)
        .putExtra(EXTRA_BACKGROUND, true)
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
    private const val PREFIX = "/data/data/com.termux/files/usr"
    private const val HOME = "/data/data/com.termux/files/home"
  }
}
