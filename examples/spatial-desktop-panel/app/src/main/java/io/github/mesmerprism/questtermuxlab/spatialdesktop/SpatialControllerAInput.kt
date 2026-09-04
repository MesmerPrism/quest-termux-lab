package io.github.mesmerprism.questtermuxlab.spatialdesktop

import com.meta.spatial.core.Query
import com.meta.spatial.core.SpatialFeature
import com.meta.spatial.core.SystemBase
import com.meta.spatial.runtime.ButtonBits
import com.meta.spatial.runtime.Scene
import com.meta.spatial.toolkit.AvatarAttachment
import com.meta.spatial.toolkit.Controller
import com.meta.spatial.toolkit.ControllerType

/** Polls before panel interaction systems so A/B can replace synthesized panel taps. */
internal class SpatialControllerButtonsFeature(private val poll: () -> Unit) : SpatialFeature {
  override fun earlySystemsToRegister(): List<SystemBase> = listOf(ControllerButtonsPollingSystem(poll))

  private class ControllerButtonsPollingSystem(private val poll: () -> Unit) : SystemBase() {
    override fun execute() = poll()
  }
}

internal data class SpatialControllerButtons(val aDown: Boolean, val bDown: Boolean)

internal object SpatialControllerButtonsState {
  fun read(scene: Scene): SpatialControllerButtons {
    var rightState: Int? = null
    var controllerState = 0
    Query.where { has(Controller.id) }
      .eval(scene.spatialInterface.dataModel)
      .forEach { entity ->
        val controller = entity.tryGetComponent<Controller>() ?: return@forEach
        if (controller.type != ControllerType.CONTROLLER) return@forEach
        controllerState = controllerState or controller.buttonState
        if (
          runCatching { entity.isLocal() }.getOrDefault(false) &&
            entity.tryGetComponent<AvatarAttachment>()?.type == "right_controller"
        ) {
          rightState = (rightState ?: 0) or controller.buttonState
        }
      }
    val state = rightState ?: controllerState
    return SpatialControllerButtons(
      aDown = state and ButtonBits.ButtonA != 0,
      bDown = state and ButtonBits.ButtonB != 0,
    )
  }
}
