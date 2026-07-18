package io.github.mesmerprism.questtermuxlab.spatialcodex

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpatialArchitectureStaticTest {
  private fun source(relative: String): String {
    val candidates = listOf(File(relative), File("app", relative))
    return candidates.firstOrNull { it.isFile }?.readText() ?: error("Missing source fixture: $relative")
  }

  @Test fun activityKeepsSpatialAndWebSecurityBoundaries() {
    val activity = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialcodex/SpatialCodexWorkbenchActivity.kt")
    assertTrue(activity.contains("PanelRenderMode.Layer()"))
    assertTrue(activity.contains("Grabbable(enabled = true, type = GrabbableType.PIVOT_Y"))
    assertTrue(activity.contains("allowFileAccess = false"))
    assertTrue(activity.contains("allowContentAccess = false"))
    assertTrue(activity.contains("MIXED_CONTENT_NEVER_ALLOW"))
    assertTrue(activity.contains("loadDataWithBaseURL(APP_ASSET_ORIGIN"))
    assertTrue(activity.contains("BrokerContract.confirmationFor"))
    assertFalse(activity.contains("Runtime.getRuntime().exec"))
    assertFalse(activity.contains("ProcessBuilder"))
  }

  @Test fun sidecarLauncherIsFixedAndDoesNotAcceptShellText() {
    val launcher = source("src/main/java/io/github/mesmerprism/questtermuxlab/spatialcodex/WorkbenchSidecarLauncher.kt")
    assertTrue(launcher.contains("sidecar/src/server.mjs"))
    assertTrue(launcher.contains("WORKBENCH_TOKEN=\$token"))
    assertTrue(launcher.contains("TERMUX_PREFIX/bin/env"))
    assertTrue(launcher.contains("com.termux.RUN_COMMAND_STDIN"))
    assertTrue(launcher.contains("!relative.contains(\"..\")"))
    assertFalse(launcher.contains("-lc"))
    assertFalse(launcher.contains("commandText"))
  }
}
