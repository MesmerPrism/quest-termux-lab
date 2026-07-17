package io.github.mesmerprism.questtermuxlab.spatialdesktop

import kotlin.math.sqrt

data class PlacementVector(val x: Float, val y: Float, val z: Float) {
  operator fun plus(other: PlacementVector) = PlacementVector(x + other.x, y + other.y, z + other.z)
  operator fun times(scale: Float) = PlacementVector(x * scale, y * scale, z * scale)

  fun normalizedOr(fallback: PlacementVector): PlacementVector {
    val length = sqrt((x * x + y * y + z * z).toDouble()).toFloat()
    return if (length > 0.000001f) PlacementVector(x / length, y / length, z / length) else fallback
  }
}

data class ViewerRelativePlacement(val center: PlacementVector, val forward: PlacementVector)

object SpatialPresentationContract {
  const val PANEL_CENTER_Y_METERS = 1.28f
  const val PANEL_DISTANCE_METERS = 1.85f
  const val PANEL_WIDTH_METERS = 1.6f
  const val PANEL_HEIGHT_METERS = 0.9f
  const val PANEL_LAYER_Z_INDEX = 99
  const val MARKER_VR_FEATURE = "SPATIAL_DESKTOP_VR_FEATURE_REGISTERED"
  const val MARKER_REGISTERED = "SPATIAL_DESKTOP_PANEL_REGISTERED"
  const val MARKER_LAYER = "SPATIAL_DESKTOP_PANEL_LAYER_READY"
  const val MARKER_ENTITY_CREATED = "SPATIAL_DESKTOP_ENTITY_CREATED"
  const val MARKER_SCENE_READY = "SPATIAL_DESKTOP_SCENE_READY"
  const val MARKER_FIRST_DRAW = "SPATIAL_DESKTOP_FIRST_ANDROID_PANEL_DRAW"

  val defaultForward = PlacementVector(0f, 0f, 1f)

  fun viewerRelative(viewerPosition: PlacementVector, viewerForward: PlacementVector): ViewerRelativePlacement {
    val flatForward =
      PlacementVector(viewerForward.x, 0f, viewerForward.z).normalizedOr(defaultForward)
    val projected = viewerPosition + flatForward * PANEL_DISTANCE_METERS
    return ViewerRelativePlacement(
      center = PlacementVector(projected.x, PANEL_CENTER_Y_METERS, projected.z),
      forward = flatForward,
    )
  }
}
