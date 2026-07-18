package io.github.mesmerprism.questtermuxlab.spatialdesktop

import kotlin.math.floor
import kotlin.math.min

data class DesktopPoint(val x: Int, val y: Int)

object DesktopMapping {
  fun map(x: Float, y: Float, viewWidth: Int, viewHeight: Int, desktopWidth: Int, desktopHeight: Int): DesktopPoint? {
    if (viewWidth <= 0 || viewHeight <= 0 || desktopWidth <= 0 || desktopHeight <= 0) return null
    val scale = min(viewWidth.toDouble() / desktopWidth, viewHeight.toDouble() / desktopHeight)
    val contentWidth = desktopWidth * scale
    val contentHeight = desktopHeight * scale
    val offsetX = (viewWidth - contentWidth) / 2.0
    val offsetY = (viewHeight - contentHeight) / 2.0
    if (x < offsetX || y < offsetY || x >= offsetX + contentWidth || y >= offsetY + contentHeight) return null
    return DesktopPoint(
      floor((x - offsetX) / scale).toInt().coerceIn(0, desktopWidth - 1),
      floor((y - offsetY) / scale).toInt().coerceIn(0, desktopHeight - 1),
    )
  }
}
