package io.github.mesmerprism.questtermuxlab.spatialdesktop

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SpatialArchitectureStaticTest {
  private fun source(relative: String): String {
    val candidates = listOf(File(relative), File("app", relative))
    return candidates.firstOrNull { it.isFile }?.readText()
      ?: error("Missing source fixture: $relative from ${File(".").absolutePath}")
  }

  @Test fun activityRegistersVrFeatureViewerPoseLayerModeAndZIndex() {
    val activity = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/SpatialDesktopActivity.kt")
    assertTrue(activity.contains("VRFeature(this, LocomotionControls.Right, false, VrInputSystemType.INTERACTION_SDK)"))
    assertTrue(activity.contains("scene.getViewerPose()"))
    assertTrue(activity.contains("Quaternion.fromDirection"))
    assertTrue(activity.contains("UIPanelRenderOptions(PanelRenderMode.Layer())"))
    assertTrue(activity.contains("layer?.setZIndex(SpatialPresentationContract.PANEL_LAYER_Z_INDEX)"))
    assertTrue(activity.contains("Entity.createPanelEntity"))
    assertTrue(activity.contains("Grabbable(enabled = true, type = GrabbableType.PIVOT_Y, minHeight = 0.5f, maxHeight = 2.5f)"))
    assertTrue(!activity.contains("Isdk"))
    assertTrue(!activity.contains("setOnTouchListener"))
    assertTrue(!activity.contains("R.id.grab_label"))
    assertTrue(!activity.contains("movePanel"))
    assertTrue(!activity.contains("MotionEvent.ACTION_MOVE"))
    assertTrue(activity.contains("SPATIAL_DESKTOP_PANEL_RECENTERED"))
    assertTrue(activity.contains("require(BuildConfig.DEBUG) { \"panel recenter disabled in release build\" }"))
    assertTrue(activity.contains("scalePreserved=true"))
    assertTrue(activity.contains("check(scaleAfter == scaleBefore)"))
    assertEquals(2, Regex("setComponent\\(Transform\\(").findAll(activity).count() + Regex("Transform\\(pose\\)").findAll(activity).count())
  }

  @Test fun manifestHasHybridWindowedAndImmersiveScaffolding() {
    val manifest = source("src/main/AndroidManifest.xml")
    listOf(
      "uses-horizonos-sdk",
      "org.khronos.openxr.permission.OPENXR",
      "org.khronos.openxr.permission.OPENXR_SYSTEM",
      "android.permission.RECORD_AUDIO",
      "com.oculus.supportedDevices",
      "com.oculus.vr.focusaware",
      "libossdk.oculus.so",
      "android:screenOrientation=\"landscape\"",
      ".DesktopPanelActivity",
      "com.oculus.intent.category.2D",
      "com.oculus.intent.category.VR_HOME_LAUNCHER",
      "com.oculus.intent.category.OVERLAY_LAUNCHER",
      ".SpatialDesktopActivity",
      "com.oculus.intent.category.VR",
      "android:defaultWidth=\"1280dp\"",
      "android:defaultHeight=\"720dp\"",
    ).forEach { assertTrue("missing manifest marker $it", manifest.contains(it)) }
    assertEquals(1, Regex("android.intent.category.LAUNCHER").findAll(manifest).count())
    assertTrue(!manifest.contains("keyboardHidden|keyboard|navigation"))
  }

  @Test fun panelThemeIsExplicitlyOpaqueAndVrDependenciesArePinned() {
    val styles = source("src/main/res/values/styles.xml")
    val build = source("build.gradle.kts")
    assertTrue(styles.contains("android:windowIsTranslucent\">false</item>"))
    assertTrue(build.contains("meta-spatial-sdk-vr:0.13.2"))
    assertTrue(build.contains("meta-spatial-sdk-isdk:0.13.2"))
  }

  @Test fun buttonsAndDebugIntentShareTypedDispatcher() {
    val activity = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/SpatialDesktopActivity.kt")
    val windowedActivity = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/DesktopPanelActivity.kt")
    val session = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/DesktopPanelSession.kt")
    assertTrue(activity.contains("override fun onNewIntent(intent: Intent)"))
    assertTrue(session.contains("BuildConfig.DEBUG"))
    assertTrue(session.contains("dispatchHuman(if (client.isActive) PanelAction.Disconnect else PanelAction.Connect)"))
    assertTrue(session.contains("dispatchHuman(PanelAction.Camera50)"))
    assertTrue(session.contains("dispatchHuman(PanelAction.Camera51)"))
    assertTrue(session.contains("dispatchHuman(PanelAction.ToggleMicrophone)"))
    assertTrue(session.contains("dispatchHuman(PanelAction.ShowVirtualKeyboard)"))
    assertTrue(session.contains("R.id.recording_indicator"))
    assertTrue(session.contains("microphoneIndicator?.visibility = if (state.active) View.VISIBLE else View.GONE"))
    assertTrue(session.contains("SPATIAL_DESKTOP_MIC_INDICATOR"))
    assertTrue(session.contains("SPATIAL_DESKTOP_VIRTUAL_KEYBOARD_REQUESTED"))
    assertTrue(session.contains("stopMicrophone(\"activity-pause\")"))
    assertTrue(session.contains("dispatchPanelAction(request.action, request.requestId)"))
    assertTrue(session.contains("SPATIAL_DESKTOP_RFB_STATUS"))
    assertTrue(session.contains("SPATIAL_DESKTOP_RFB_FRAME"))
    assertTrue(session.contains("connectButton?.text = if (client.isActive) \"Disconnect\" else \"Connect\""))
    assertTrue(session.contains("postDelayed(deferredPauseDisconnect, PAUSE_DISCONNECT_DELAY_MS)"))
    assertTrue(session.contains("lifecycleHandler.removeCallbacks(deferredPauseDisconnect)"))
    assertTrue(activity.contains("session.handleControllerKey(event) || super.dispatchKeyEvent(event)"))
    assertTrue(windowedActivity.contains("session.handleControllerKey(event) || super.dispatchKeyEvent(event)"))
    assertTrue(activity.contains("session.handleControllerMotion(event) || super.dispatchGenericMotionEvent(event)"))
    assertTrue(windowedActivity.contains("session.handleControllerMotion(event) || super.dispatchGenericMotionEvent(event)"))
    assertTrue(windowedActivity.contains("override fun onBackPressed()"))
    assertTrue(windowedActivity.contains("session.handleWindowBackInvoked()"))
    assertTrue(session.contains("ControllerButtonMapper.isWindowVoiceClickToggle(event.keyCode)"))
    assertTrue(session.contains("horizon-window-back-key"))
    assertTrue(session.contains("horizon-window-back-callback"))
    assertTrue(session.contains("ControllerButtonMapper.isSecondaryClick(event.keyCode)"))
    assertTrue(session.contains("input.click(3)"))
    assertTrue(session.contains("SPATIAL_DESKTOP_CONTROLLER_RIGHT_CLICK"))
    assertTrue(session.contains("toggleSecondaryClickArm()"))
    assertTrue(session.contains("Cancel right-click"))
    val rfb = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/RfbProtocol.kt")
    assertTrue(rfb.indexOf("negotiate(input, out)") < rfb.indexOf("s.soTimeout = 0"))
    assertTrue(rfb.contains("newSingleThreadExecutor"))
    assertTrue(rfb.contains("loopback-rfb-writer"))
    assertTrue(rfb.contains("input.readFully(raw)"))
    assertTrue(rfb.contains("System.arraycopy"))
    assertTrue(rfb.contains("RfbPixelFormat.BGRA32"))
    assertTrue(rfb.contains("RfbPixelFormat.RGB565"))
    assertTrue(rfb.contains("copyRect"))
    val view = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/FramebufferView.kt")
    assertTrue(view.contains("ArrayBlockingQueue<DecodedFrame>"))
    assertTrue(view.contains("target.setPixels"))
    assertTrue(view.contains("backpressureBlocks"))
    assertTrue(!view.contains("framebuffer.snapshot()"))
    assertTrue(view.contains("PrimaryPointerGestureClassifier"))
    assertTrue(view.contains("OneShotSecondaryClickState"))
    assertTrue(view.contains("suppressPrimaryGestureForControllerAction"))
    assertTrue(view.contains("lifecycle.click(3"))
    assertTrue(view.contains("primaryGesture.down(id, point, e.eventTime)"))
    assertTrue(!view.contains("input?.press(1, point)"))
    assertTrue(view.contains("PrimaryPointerGestureEvent.Click -> lifecycle.click(1, event.point)"))
    val sidecar = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/TermuxSidecarLauncher.kt")
    assertTrue(sidecar.contains("termux-x11"))
    assertTrue(sidecar.contains("\"termux-x11-nightly\", \"xfce4\", \"xorg-xrandr\""))
    assertTrue(sidecar.contains("arrayOf(\"install\", \"-y\", \"x11-repo\")"))
    assertTrue(sidecar.contains("\"-localhost\""))
    assertTrue(!sidecar.contains("-lc"))
    val witness = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/TermuxWitnessLauncher.kt")
    assertTrue(witness.contains("xfce4-terminal"))
    assertTrue(witness.contains("^\$PREFIX/bin/xfce4-terminal .*--title=SpatialDesktopWitness$"))
    assertTrue(!witness.contains("-lc"))
  }

  @Test fun questMicrophoneRecordingIndicatorOverlaysWithoutResizingDesktop() {
    val layout = source("src/main/res/layout/spatial_desktop_panel.xml")
    assertTrue(layout.contains("android:id=\"@+id/recording_indicator\""))
    assertTrue(layout.contains("QUEST MICROPHONE LIVE"))
    assertTrue(layout.contains("android:visibility=\"gone\""))
    assertTrue(layout.indexOf("<FrameLayout") < layout.indexOf("@+id/framebuffer"))
    assertTrue(layout.indexOf("@+id/framebuffer") < layout.indexOf("@+id/recording_indicator"))
  }

  @Test fun explicitVirtualKeyboardControlTargetsTheImeBridge() {
    val layout = source("src/main/res/layout/spatial_desktop_panel.xml")
    val session = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/DesktopPanelSession.kt")
    assertTrue(layout.contains("android:id=\"@+id/virtual_keyboard\""))
    assertTrue(session.contains("ime.showSoftInputOnFocus = true"))
    assertTrue(session.contains("manager.showSoftInput(ime, InputMethodManager.SHOW_IMPLICIT)"))
    assertTrue(session.contains("ime.requestFocus()"))
  }

  @Test fun rawTransportStatusStripIsHiddenByDefault() {
    val layout = source("src/main/res/layout/spatial_desktop_panel.xml")
    val statusStart = layout.indexOf("android:id=\"@+id/status\"")
    assertTrue(statusStart >= 0)
    assertTrue(layout.substring(statusStart).substringBefore("/>").contains("android:visibility=\"gone\""))
  }

  @Test fun hybridActivitiesShareOneDesktopSessionAndUseExclusiveTransitions() {
    val windowed = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/DesktopPanelActivity.kt")
    val spatial = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/SpatialDesktopActivity.kt")
    val navigator = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/DesktopPresentation.kt")
    val session = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialdesktop/DesktopPanelSession.kt")
    assertTrue(windowed.contains("DesktopPanelSession(this, this)"))
    assertTrue(spatial.contains("DesktopPanelSession(this, this)"))
    assertTrue(windowed.contains("HybridDesktopNavigator.launchSpatial(this)"))
    assertTrue(spatial.contains("HybridDesktopNavigator.launchWindowedInHome(this)"))
    assertTrue(spatial.contains("SpatialControllerButtonsFeature(::pollControllerButtons)"))
    assertTrue(spatial.contains("SpatialControllerButtonsState.read(scene)"))
    assertTrue(spatial.contains("session.handleSpatialControllerB()"))
    assertTrue(spatial.contains("SPATIAL_DESKTOP_CONTROLLER_ROUTE_READY"))
    assertTrue(navigator.contains("extra_launch_in_home_pending_intent"))
    assertTrue(navigator.contains("finishAndRemoveTask()"))
    assertTrue(navigator.contains("EXTRA_AUTO_CONNECT"))
    assertTrue(session.contains("presentation.switchPresentation()"))
    assertTrue(session.contains("sizeDown.visibility = if (spatial) View.VISIBLE else View.GONE"))
  }
}
