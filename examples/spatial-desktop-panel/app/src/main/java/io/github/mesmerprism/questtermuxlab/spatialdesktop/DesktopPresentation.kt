package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.app.Activity
import android.app.PendingIntent
import android.content.Intent

enum class DesktopPresentationMode {
  WINDOWED,
  SPATIAL,
}

interface DesktopPresentationHost {
  val presentationMode: DesktopPresentationMode
  fun isPresentationReady(action: PanelAction): Boolean
  fun resizeBy(factor: Float)
  fun recenterPanel(source: String)
  fun presentationState(): String
  fun switchPresentation()
}

object HybridDesktopNavigator {
  const val EXTRA_AUTO_CONNECT = "auto_connect"
  const val MARKER_SWITCH = "SPATIAL_DESKTOP_PRESENTATION_SWITCH"
  private const val HOME_PENDING_INTENT_EXTRA = "extra_launch_in_home_pending_intent"

  fun launchSpatial(activity: Activity) {
    val immersiveIntent =
      Intent(activity, SpatialDesktopActivity::class.java).apply {
        action = Intent.ACTION_MAIN
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        putExtra(EXTRA_AUTO_CONNECT, true)
      }
    activity.startActivity(immersiveIntent)
    activity.finishAndRemoveTask()
  }

  fun launchWindowedInHome(activity: Activity) {
    val panelIntent =
      Intent(activity.applicationContext, DesktopPanelActivity::class.java).apply {
        action = Intent.ACTION_MAIN
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        putExtra(EXTRA_AUTO_CONNECT, true)
      }
    val pendingPanelIntent =
      PendingIntent.getActivity(
        activity.applicationContext,
        0,
        panelIntent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
      )
    val homeIntent =
      Intent(Intent.ACTION_MAIN)
        .addCategory(Intent.CATEGORY_HOME)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        .putExtra(HOME_PENDING_INTENT_EXTRA, pendingPanelIntent)
    activity.startActivity(homeIntent)
    activity.finishAndRemoveTask()
  }
}
