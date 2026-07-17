package io.github.mesmerprism.questtermuxlab.spatialdesktop

/**
 * Pure desktop-coordinate primary-pointer classifier. It deliberately does not
 * depend on MotionEvent, ViewConfiguration, or RFB so its timing and movement
 * rules remain deterministic in unit tests.
 */
class PrimaryPointerGestureClassifier(private val emit: (PrimaryPointerGestureEvent) -> Unit) {
  private data class CompletedTap(val point: DesktopPoint, val eventTimeMs: Long)

  private var activePointerId: Int? = null
  private var downPoint: DesktopPoint? = null
  private var lastPoint: DesktopPoint? = null
  private var tapAnchor: DesktopPoint? = null
  private var dragging = false
  private var lastTap: CompletedTap? = null

  var lastClassification: String = "idle"; private set
  var doubleTapSnapCount: Long = 0; private set
  val isDragging: Boolean get() = dragging
  val ownsPointer: Boolean get() = activePointerId != null
  val pointerId: Int? get() = activePointerId

  fun down(pointerId: Int, point: DesktopPoint, eventTimeMs: Long): Boolean {
    if (activePointerId != null) return false
    val snap = lastTap?.takeIf {
      eventTimeMs - it.eventTimeMs in 0..DOUBLE_TAP_TIMEOUT_MS && distanceSquared(it.point, point) <= DOUBLE_TAP_SLOP_PX * DOUBLE_TAP_SLOP_PX
    }?.point
    activePointerId = pointerId
    downPoint = point
    lastPoint = point
    tapAnchor = snap ?: point
    dragging = false
    if (snap != null) doubleTapSnapCount++
    lastClassification = if (snap != null) "tap-candidate-double-snap" else "tap-candidate"
    emit(PrimaryPointerGestureEvent.CursorMove(point))
    return true
  }

  fun move(pointerId: Int, point: DesktopPoint): Boolean {
    if (pointerId != activePointerId) return false
    val origin = downPoint ?: return false
    lastPoint = point
    if (!dragging && distanceSquared(origin, point) > DRAG_SLOP_PX * DRAG_SLOP_PX) {
      dragging = true
      lastClassification = "drag"
      emit(PrimaryPointerGestureEvent.Press(origin))
    }
    if (dragging) emit(PrimaryPointerGestureEvent.HeldMove(point))
    return true
  }

  fun up(pointerId: Int, point: DesktopPoint?, eventTimeMs: Long): Boolean {
    if (pointerId != activePointerId) return false
    val origin = downPoint ?: return false
    val finalPoint = point ?: lastPoint ?: origin
    if (dragging) {
      emit(PrimaryPointerGestureEvent.Release(finalPoint))
      lastClassification = "drag-release"
    } else {
      val anchor = tapAnchor ?: origin
      emit(PrimaryPointerGestureEvent.Click(anchor))
      lastTap = CompletedTap(anchor, eventTimeMs)
      lastClassification = "tap"
    }
    clearActive()
    return true
  }

  /** Cancels only an actual held left button; a tap candidate never becomes a click. */
  fun cancel(): Boolean {
    if (activePointerId == null) return false
    if (dragging) emit(PrimaryPointerGestureEvent.Release(lastPoint ?: downPoint ?: DesktopPoint(0, 0)))
    lastClassification = if (dragging) "cancelled-drag" else "cancelled-tap"
    clearActive()
    return true
  }

  /** Use for focus loss, pause, and disconnect: discard both active and double-tap history. */
  fun reset() {
    cancel()
    lastTap = null
  }

  private fun clearActive() {
    activePointerId = null
    downPoint = null
    lastPoint = null
    tapAnchor = null
    dragging = false
  }

  private fun distanceSquared(a: DesktopPoint, b: DesktopPoint): Int {
    val dx = a.x - b.x
    val dy = a.y - b.y
    return dx * dx + dy * dy
  }

  companion object {
    /** Desktop pixels: absorbs small spatial-ray jitter without delaying a real drag. */
    const val DRAG_SLOP_PX = 18
    /** Desktop pixels: nearby second taps are snapped to the first click coordinate. */
    const val DOUBLE_TAP_SLOP_PX = 32
    /** Milliseconds: independent of Android ViewConfiguration for deterministic behavior. */
    const val DOUBLE_TAP_TIMEOUT_MS = 350L
  }
}

sealed interface PrimaryPointerGestureEvent {
  data class CursorMove(val point: DesktopPoint) : PrimaryPointerGestureEvent
  data class Press(val point: DesktopPoint) : PrimaryPointerGestureEvent
  data class HeldMove(val point: DesktopPoint) : PrimaryPointerGestureEvent
  data class Release(val point: DesktopPoint) : PrimaryPointerGestureEvent
  data class Click(val point: DesktopPoint) : PrimaryPointerGestureEvent
}
