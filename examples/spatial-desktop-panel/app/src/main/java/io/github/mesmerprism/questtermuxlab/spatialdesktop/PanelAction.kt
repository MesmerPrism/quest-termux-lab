package io.github.mesmerprism.questtermuxlab.spatialdesktop

private val REQUEST_ID_PATTERN = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

sealed interface PanelAction {
  data object Connect : PanelAction
  data object Disconnect : PanelAction
  data object SizeUp : PanelAction
  data object SizeDown : PanelAction
  data object RecenterPanel : PanelAction
  data object SwitchPresentation : PanelAction
  data object RightClick : PanelAction
  data object ScrollUp : PanelAction
  data object ScrollDown : PanelAction
  data object Camera50 : PanelAction
  data object Camera51 : PanelAction
  data class PointerMove(val point: DesktopPoint) : PanelAction
  data class PointerDown(val point: DesktopPoint) : PanelAction
  data class PointerUp(val point: DesktopPoint) : PanelAction
  data class Tap(val point: DesktopPoint) : PanelAction
  data class Drag(val start: DesktopPoint, val end: DesktopPoint) : PanelAction
  data class TypeText(val text: String) : PanelAction
  data object Enter : PanelAction
  data object StartSidecar : PanelAction
  data object StartWitness : PanelAction
  data object StopWitness : PanelAction
}

data class PanelActionRequest(val requestId: String, val action: PanelAction)

object DebugPanelActionContract {
  const val INTENT_ACTION = "io.github.mesmerprism.questtermuxlab.spatialdesktop.DEBUG_PANEL_ACTION"
  const val EXTRA_REQUEST_ID = "request_id"
  const val EXTRA_ACTION = "panel_action"
  const val EXTRA_X = "x"
  const val EXTRA_Y = "y"
  const val EXTRA_X2 = "x2"
  const val EXTRA_Y2 = "y2"
  const val EXTRA_TEXT = "text"
  const val MAX_COORDINATE = 4095
  const val MAX_TEXT_LENGTH = 128
  const val MARKER_ACCEPTED = "SPATIAL_DESKTOP_DEBUG_ACTION_ACCEPTED"
  const val MARKER_REJECTED = "SPATIAL_DESKTOP_DEBUG_ACTION_REJECTED"
  const val MARKER_COMPLETED = "SPATIAL_DESKTOP_DEBUG_ACTION_COMPLETED"

  val actionNames = setOf("connect", "disconnect", "size-up", "size-down", "recenter-panel", "switch-presentation", "right-click", "scroll-up", "scroll-down", "camera-50", "camera-51", "pointer-move", "pointer-down", "pointer-up", "tap", "drag", "type-text", "enter", "start-sidecar", "start-witness", "stop-witness")

  fun parse(isDebug: Boolean, intentAction: String?, requestId: String?, actionName: String?, x: Int?, y: Int?, text: String?, x2: Int? = null, y2: Int? = null): Result<PanelActionRequest> =
    runCatching {
      require(isDebug) { "debug control disabled in release build" }
      require(intentAction == INTENT_ACTION) { "unexpected intent action" }
      val id = requireNotNull(requestId) { "missing request id" }
      require(REQUEST_ID_PATTERN.matches(id)) { "invalid request id" }
      val name = requireNotNull(actionName) { "missing action" }
      require(name in actionNames) { "action not allowlisted" }
      fun point(): DesktopPoint {
        val px = requireNotNull(x) { "missing x" }
        val py = requireNotNull(y) { "missing y" }
        require(px in 0..MAX_COORDINATE && py in 0..MAX_COORDINATE) { "coordinates out of bounds" }
        return DesktopPoint(px, py)
      }
      fun endPoint(): DesktopPoint {
        val px = requireNotNull(x2) { "missing x2" }
        val py = requireNotNull(y2) { "missing y2" }
        require(px in 0..MAX_COORDINATE && py in 0..MAX_COORDINATE) { "end coordinates out of bounds" }
        return DesktopPoint(px, py)
      }
      val action = when (name) {
        "connect" -> PanelAction.Connect
        "disconnect" -> PanelAction.Disconnect
        "size-up" -> PanelAction.SizeUp
        "size-down" -> PanelAction.SizeDown
        "recenter-panel" -> PanelAction.RecenterPanel
        "switch-presentation" -> PanelAction.SwitchPresentation
        "right-click" -> PanelAction.RightClick
        "scroll-up" -> PanelAction.ScrollUp
        "scroll-down" -> PanelAction.ScrollDown
        "camera-50" -> PanelAction.Camera50
        "camera-51" -> PanelAction.Camera51
        "pointer-move" -> PanelAction.PointerMove(point())
        "pointer-down" -> PanelAction.PointerDown(point())
        "pointer-up" -> PanelAction.PointerUp(point())
        "tap" -> PanelAction.Tap(point())
        "drag" -> PanelAction.Drag(point(), endPoint())
        "type-text" -> {
          val value = requireNotNull(text) { "missing text" }
          require(value.length in 1..MAX_TEXT_LENGTH) { "text length out of bounds" }
          require(value.all { it.code in 0x20..0x7e }) { "text must be printable ASCII" }
          PanelAction.TypeText(value)
        }
        "enter" -> PanelAction.Enter
        "start-sidecar" -> PanelAction.StartSidecar
        "start-witness" -> PanelAction.StartWitness
        "stop-witness" -> PanelAction.StopWitness
        else -> error("unreachable allowlist action")
      }
      PanelActionRequest(id, action)
    }
}
