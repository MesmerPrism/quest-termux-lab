package io.github.mesmerprism.questtermuxlab.spatialdesktop

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PrimaryPointerGestureClassifierTest {
  private fun classifier(events: MutableList<PrimaryPointerGestureEvent>) = PrimaryPointerGestureClassifier(events::add)
  private fun points(events: List<PrimaryPointerGestureEvent>) = events.map {
    when (it) {
      is PrimaryPointerGestureEvent.CursorMove -> "move:${it.point.x},${it.point.y}"
      is PrimaryPointerGestureEvent.Press -> "press:${it.point.x},${it.point.y}"
      is PrimaryPointerGestureEvent.HeldMove -> "held:${it.point.x},${it.point.y}"
      is PrimaryPointerGestureEvent.Release -> "release:${it.point.x},${it.point.y}"
      is PrimaryPointerGestureEvent.Click -> "click:${it.point.x},${it.point.y}"
    }
  }

  @Test fun cleanTapMovesThenEmitsAtomicClickOnlyOnUp() {
    val events = mutableListOf<PrimaryPointerGestureEvent>(); val c = classifier(events)
    c.down(7, DesktopPoint(10, 20), 100)
    assertEquals(listOf("move:10,20"), points(events))
    c.up(7, DesktopPoint(10, 20), 120)
    assertEquals(listOf("move:10,20", "click:10,20"), points(events))
  }

  @Test fun microJitterRemainsTapAndUsesStableDownCoordinate() {
    val events = mutableListOf<PrimaryPointerGestureEvent>(); val c = classifier(events)
    c.down(1, DesktopPoint(100, 100), 0); c.move(1, DesktopPoint(112, 112)); c.up(1, DesktopPoint(113, 113), 20)
    assertEquals(listOf("move:100,100", "click:100,100"), points(events))
  }

  @Test fun nearbyDoubleTapSnapsSecondClickToFirstCoordinate() {
    val events = mutableListOf<PrimaryPointerGestureEvent>(); val c = classifier(events)
    c.down(1, DesktopPoint(200, 200), 0); c.up(1, DesktopPoint(200, 200), 20)
    c.down(2, DesktopPoint(220, 210), 200); c.up(2, DesktopPoint(221, 211), 220)
    assertEquals(listOf("move:200,200", "click:200,200", "move:220,210", "click:200,200"), points(events)); assertEquals(1, c.doubleTapSnapCount)
  }

  @Test fun distantOrLateSecondTapUsesOwnCoordinate() {
    val events = mutableListOf<PrimaryPointerGestureEvent>(); val c = classifier(events)
    c.down(1, DesktopPoint(20, 20), 0); c.up(1, DesktopPoint(20, 20), 10)
    c.down(2, DesktopPoint(70, 20), 100); c.up(2, DesktopPoint(70, 20), 110)
    c.down(3, DesktopPoint(75, 20), 500); c.up(3, DesktopPoint(75, 20), 510)
    assertEquals(listOf("move:20,20", "click:20,20", "move:70,20", "click:70,20", "move:75,20", "click:75,20"), points(events))
  }

  @Test fun deliberateDragPressesAtOriginThenHoldsAndReleasesAtLastPoint() {
    val events = mutableListOf<PrimaryPointerGestureEvent>(); val c = classifier(events)
    c.down(4, DesktopPoint(10, 10), 0); c.move(4, DesktopPoint(29, 10)); c.move(4, DesktopPoint(40, 10)); c.up(4, null, 30)
    assertEquals(listOf("move:10,10", "press:10,10", "held:29,10", "held:40,10", "release:40,10"), points(events))
  }

  @Test fun cancelTapIsSilentAndCancelDragReleasesOnce() {
    val events = mutableListOf<PrimaryPointerGestureEvent>(); val c = classifier(events)
    c.down(1, DesktopPoint(1, 1), 0); assertTrue(c.cancel()); assertFalse(c.cancel())
    c.down(2, DesktopPoint(5, 5), 20); c.move(2, DesktopPoint(30, 5)); assertTrue(c.cancel()); assertFalse(c.cancel())
    assertEquals(listOf("move:1,1", "move:5,5", "press:5,5", "held:30,5", "release:30,5"), points(events))
  }

  @Test fun classifierOwnsPrimaryPointerAndIgnoresExtraContacts() {
    val events = mutableListOf<PrimaryPointerGestureEvent>(); val c = classifier(events)
    assertTrue(c.down(11, DesktopPoint(1, 1), 0)); assertFalse(c.down(12, DesktopPoint(2, 2), 1))
    assertFalse(c.move(12, DesktopPoint(50, 50))); assertFalse(c.up(12, DesktopPoint(50, 50), 2)); assertTrue(c.up(11, DesktopPoint(1, 1), 3))
    assertEquals(listOf("move:1,1", "click:1,1"), points(events))
  }
}
