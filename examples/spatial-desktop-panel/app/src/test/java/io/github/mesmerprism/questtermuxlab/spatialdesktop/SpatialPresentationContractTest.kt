package io.github.mesmerprism.questtermuxlab.spatialdesktop

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SpatialPresentationContractTest {
  @Test fun placementUsesFlattenedViewerForwardAtFixedFloorHeight() {
    val placement =
      SpatialPresentationContract.viewerRelative(
        viewerPosition = PlacementVector(2f, 1.7f, -3f),
        viewerForward = PlacementVector(3f, 4f, 0f),
      )
    assertEquals(2f + SpatialPresentationContract.PANEL_DISTANCE_METERS, placement.center.x, 0.0001f)
    assertEquals(SpatialPresentationContract.PANEL_CENTER_Y_METERS, placement.center.y, 0f)
    assertEquals(-3f, placement.center.z, 0.0001f)
    assertEquals(PlacementVector(1f, 0f, 0f), placement.forward)
  }

  @Test fun degenerateViewerForwardUsesDocumentedFallbackDirection() {
    val placement = SpatialPresentationContract.viewerRelative(PlacementVector(0f, 0f, 0f), PlacementVector(0f, 1f, 0f))
    assertEquals(SpatialPresentationContract.defaultForward, placement.forward)
    assertEquals(SpatialPresentationContract.PANEL_DISTANCE_METERS, placement.center.z, 0.0001f)
  }

  @Test fun readinessMarkersCoverVrRegistrationLayerEntitySceneAndDraw() {
    val markers =
      setOf(
        SpatialPresentationContract.MARKER_VR_FEATURE,
        SpatialPresentationContract.MARKER_REGISTERED,
        SpatialPresentationContract.MARKER_LAYER,
        SpatialPresentationContract.MARKER_ENTITY_CREATED,
        SpatialPresentationContract.MARKER_SCENE_READY,
        SpatialPresentationContract.MARKER_FIRST_DRAW,
      )
    assertEquals(6, markers.size)
    assertTrue(markers.all { it.startsWith("SPATIAL_DESKTOP_") })
  }
}
