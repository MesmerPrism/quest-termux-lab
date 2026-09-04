package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import android.view.MotionEvent

/** Horizon OS-managed 2D presentation of the same interactive Linux desktop. */
class DesktopPanelActivity : Activity(), DesktopPresentationHost {
  private lateinit var session: DesktopPanelSession

  override val presentationMode = DesktopPresentationMode.WINDOWED

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    session = DesktopPanelSession(this, this)
    setContentView(R.layout.spatial_desktop_panel)
    session.bindPanelViews(findViewById(R.id.root))
    session.handleIntent(intent)
    session.onPresentationReady()
    Log.i(TAG, "SPATIAL_DESKTOP_WINDOWED_READY presentation=os-managed-2d")
  }

  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    setIntent(intent)
    session.handleIntent(intent)
  }

  override fun dispatchKeyEvent(event: KeyEvent): Boolean =
    session.handleControllerKey(event) || super.dispatchKeyEvent(event)

  override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean =
    session.handleControllerMotion(event) || super.dispatchGenericMotionEvent(event)

  override fun isPresentationReady(action: PanelAction): Boolean = true

  override fun resizeBy(factor: Float) {
    error("window size is managed by Horizon OS")
  }

  override fun recenterPanel(source: String) {
    error("window placement is managed by Horizon OS")
  }

  override fun presentationState(): String = "window=os-managed"

  override fun switchPresentation() {
    HybridDesktopNavigator.launchSpatial(this)
  }

  override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
    super.onRequestPermissionsResult(requestCode, permissions, grantResults)
    session.onRequestPermissionsResult(requestCode)
  }

  override fun onPause() {
    session.onPause()
    super.onPause()
  }

  override fun onResume() {
    session.onResume()
    super.onResume()
  }

  override fun onWindowFocusChanged(hasFocus: Boolean) {
    super.onWindowFocusChanged(hasFocus)
    session.onWindowFocusChanged(hasFocus)
  }

  override fun onDestroy() {
    session.onDestroy()
    super.onDestroy()
  }

  companion object {
    private const val TAG = "SpatialDesktop"
  }
}
