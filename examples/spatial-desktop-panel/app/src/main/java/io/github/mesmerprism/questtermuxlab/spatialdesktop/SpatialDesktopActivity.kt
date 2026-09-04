package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.content.Intent
import android.os.Bundle
import android.util.Log
import com.meta.spatial.core.Entity
import com.meta.spatial.core.Pose
import com.meta.spatial.core.Quaternion
import com.meta.spatial.core.SpatialFeature
import com.meta.spatial.core.SpatialSDKExperimentalAPI
import com.meta.spatial.core.Vector2
import com.meta.spatial.core.Vector3
import com.meta.spatial.runtime.ReferenceSpace
import com.meta.spatial.toolkit.AppSystemActivity
import com.meta.spatial.toolkit.DpPerMeterDisplayOptions
import com.meta.spatial.toolkit.Grabbable
import com.meta.spatial.toolkit.GrabbableType
import com.meta.spatial.toolkit.LayoutXMLPanelRegistration
import com.meta.spatial.toolkit.PanelDimensions
import com.meta.spatial.toolkit.PanelRegistration
import com.meta.spatial.toolkit.PanelRenderMode
import com.meta.spatial.toolkit.PanelStyleOptions
import com.meta.spatial.toolkit.QuadShapeOptions
import com.meta.spatial.toolkit.Scale
import com.meta.spatial.toolkit.Transform
import com.meta.spatial.toolkit.UIPanelRenderOptions
import com.meta.spatial.toolkit.UIPanelSettings
import com.meta.spatial.toolkit.Visible
import com.meta.spatial.toolkit.createPanelEntity
import com.meta.spatial.vr.LocomotionControls
import com.meta.spatial.vr.VRFeature
import com.meta.spatial.vr.VrInputSystemType

class SpatialDesktopActivity : AppSystemActivity(), DesktopPresentationHost {
  private lateinit var session: DesktopPanelSession
  private var panelEntity: Entity? = null
  private var physicalScale = 1f

  override val presentationMode = DesktopPresentationMode.SPATIAL

  override fun registerFeatures(): List<SpatialFeature> {
    Log.i(TAG, "${SpatialPresentationContract.MARKER_VR_FEATURE} inputSystem=INTERACTION_SDK")
    return listOf(VRFeature(this, LocomotionControls.Right, false, VrInputSystemType.INTERACTION_SDK))
  }

  override fun registerPanels(): List<PanelRegistration> {
    Log.i(
      TAG,
      "${SpatialPresentationContract.MARKER_REGISTERED} panelId=desktop_panel " +
        "renderMode=layer size=${SpatialPresentationContract.PANEL_WIDTH_METERS}x${SpatialPresentationContract.PANEL_HEIGHT_METERS}",
    )
    return listOf(
      LayoutXMLPanelRegistration(
        R.id.desktop_panel,
        layoutIdCreator = { R.layout.spatial_desktop_panel },
        settingsCreator = {
          UIPanelSettings(
            shape =
              QuadShapeOptions(
                width = SpatialPresentationContract.PANEL_WIDTH_METERS,
                height = SpatialPresentationContract.PANEL_HEIGHT_METERS,
              ),
            style = PanelStyleOptions(themeResourceId = R.style.AppTheme),
            display = DpPerMeterDisplayOptions(dpPerMeter = 800f),
            rendering = UIPanelRenderOptions(PanelRenderMode.Layer()),
          )
        },
        panelSetupWithRootView = { root, panel, _ ->
          val layer = panel.layer
          layer?.setZIndex(SpatialPresentationContract.PANEL_LAYER_Z_INDEX)
          Log.i(
            TAG,
            "${SpatialPresentationContract.MARKER_LAYER} present=${layer != null} " +
              "zIndex=${SpatialPresentationContract.PANEL_LAYER_Z_INDEX} backing=${root.width}x${root.height}",
          )
          session.bindPanelViews(root)
          session.handleIntent(intent)
        },
      )
    )
  }

  override fun onCreate(savedInstanceState: Bundle?) {
    session = DesktopPanelSession(this, this)
    super.onCreate(savedInstanceState)
  }

  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    setIntent(intent)
    session.handleIntent(intent)
  }

  @OptIn(SpatialSDKExperimentalAPI::class)
  override fun onSceneReady() {
    super.onSceneReady()
    scene.setReferenceSpace(ReferenceSpace.LOCAL_FLOOR)
    val placement = currentViewerRelativePlacement()
    val pose = placement.pose
    Log.i(
      TAG,
      "${SpatialPresentationContract.MARKER_SCENE_READY} referenceSpace=LOCAL_FLOOR " +
        "finalPose=$pose source=${placement.source}",
    )
    panelEntity =
      Entity.createPanelEntity(
        R.id.desktop_panel,
        Transform(pose),
        PanelDimensions(Vector2(SpatialPresentationContract.PANEL_WIDTH_METERS, SpatialPresentationContract.PANEL_HEIGHT_METERS)),
        Scale(Vector3(1f, 1f, 1f)),
        Grabbable(enabled = true, type = GrabbableType.PIVOT_Y, minHeight = 0.5f, maxHeight = 2.5f),
        Visible(true),
      )
    Log.i(
      TAG,
      "${SpatialPresentationContract.MARKER_ENTITY_CREATED} visible=${panelEntity?.getComponent<Visible>()?.isVisible} " +
        "transform=${panelEntity?.getComponent<Transform>()} ${presentationState()}",
    )
    session.onPresentationReady()
  }

  override fun isPresentationReady(action: PanelAction): Boolean =
    action !is PanelAction.RecenterPanel || panelEntity != null

  override fun resizeBy(factor: Float) {
    physicalScale = (physicalScale * factor).coerceIn(0.65f, 1.75f)
    panelEntity?.setComponent(Scale(Vector3(physicalScale, physicalScale, 1f)))
  }

  @OptIn(SpatialSDKExperimentalAPI::class)
  override fun recenterPanel(source: String) {
    require(BuildConfig.DEBUG) { "panel recenter disabled in release build" }
    val entity = requireNotNull(panelEntity) { "panel entity not ready" }
    val placement = currentViewerRelativePlacement()
    val scaleBefore = entity.getComponent<Scale>()
    entity.setComponent(Transform(placement.pose))
    val scaleAfter = entity.getComponent<Scale>()
    check(scaleAfter == scaleBefore) { "recenter unexpectedly changed panel scale" }
    Log.i(
      TAG,
      "SPATIAL_DESKTOP_PANEL_RECENTERED finalPose=${placement.pose} source=${placement.source}:$source " +
        "scalePreserved=true ${presentationState()}",
    )
  }

  override fun presentationState(): String {
    val entity = panelEntity ?: return "scale=${"%.3f".format(physicalScale)} grabbable=missing transform=missing"
    val grabbable = entity.getComponent<Grabbable>()
    return "scale=${"%.3f".format(physicalScale)} grabbable=present enabled=${grabbable.enabled} " +
      "type=${grabbable.type} isGrabbed=${grabbable.isGrabbed} " +
      "transform=${entity.getComponent<Transform>()} scaleComponent=${entity.getComponent<Scale>()}"
  }

  override fun switchPresentation() {
    HybridDesktopNavigator.launchWindowedInHome(this)
  }

  @OptIn(SpatialSDKExperimentalAPI::class)
  private fun currentViewerRelativePlacement(): ResolvedPanelPlacement {
    val viewerPose = runCatching { scene.getViewerPose() }.getOrNull()
    val placement =
      if (viewerPose != null) {
        SpatialPresentationContract.viewerRelative(
          PlacementVector(viewerPose.t.x, viewerPose.t.y, viewerPose.t.z),
          viewerPose.forward().let { PlacementVector(it.x, it.y, it.z) },
        )
      } else {
        SpatialPresentationContract.viewerRelative(PlacementVector(0f, 0f, 0f), SpatialPresentationContract.defaultForward)
      }
    val forward = Vector3(placement.forward.x, placement.forward.y, placement.forward.z)
    return ResolvedPanelPlacement(
      Pose(
        Vector3(placement.center.x, placement.center.y, placement.center.z),
        Quaternion.fromDirection(forward, Vector3(0f, 1f, 0f)),
      ),
      if (viewerPose != null) "viewer" else "fallback",
    )
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

private data class ResolvedPanelPlacement(val pose: Pose, val source: String)
