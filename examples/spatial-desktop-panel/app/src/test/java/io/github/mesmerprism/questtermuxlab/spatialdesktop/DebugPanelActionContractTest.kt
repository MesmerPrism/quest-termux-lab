package io.github.mesmerprism.questtermuxlab.spatialdesktop

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DebugPanelActionContractTest {
  @Test fun allowlistParsesEverySimpleAction() {
    val simple = DebugPanelActionContract.actionNames - setOf("pointer-move", "pointer-down", "pointer-up", "tap", "type-text")
    simple.forEach { name ->
      assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "test-$name", name, null, null, null).isSuccess)
    }
  }

  @Test fun releaseBuildAndUnknownActionsAreRejected() {
    assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "recenter", "recenter-panel", null, null, null).isSuccess)
    assertTrue(DebugPanelActionContract.parse(false, DebugPanelActionContract.INTENT_ACTION, "release-recenter", "recenter-panel", null, null, null).isFailure)
    assertTrue(DebugPanelActionContract.parse(false, DebugPanelActionContract.INTENT_ACTION, "release", "connect", null, null, null).isFailure)
    assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "unknown", "raw-shell", null, null, null).isFailure)
  }

  @Test fun coordinatesTextAndRequestIdsAreBounded() {
    assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "tap-ok", "tap", 1279, 719, null).isSuccess)
    assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "tap-bad", "tap", 4096, 0, null).isFailure)
    assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "text-ok", "type-text", null, null, "hello 123").isSuccess)
    assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "text-bad", "type-text", null, null, "line\nbreak").isFailure)
    assertTrue(DebugPanelActionContract.parse(true, DebugPanelActionContract.INTENT_ACTION, "bad id", "connect", null, null, null).isFailure)
  }

  @Test fun cliRequiresSerialAndContainsNoRawShellParameter() {
    val candidates = listOf(File("tools/Invoke-SpatialDesktopPanelAction.ps1"), File("../tools/Invoke-SpatialDesktopPanelAction.ps1"))
    val cli = candidates.firstOrNull { it.isFile }?.readText() ?: error("missing module CLI")
    assertTrue(cli.contains("[Parameter(Mandatory = \$true)]\n  [ValidatePattern"))
    assertTrue(cli.contains("[string]\$Serial"))
    assertTrue(!cli.contains("[string]\$Command"))
    assertTrue(!cli.contains("Invoke-Expression"))
    assertEquals(1, Regex("'shell', 'am', 'start'").findAll(cli).count())
    assertTrue(cli.contains("'recenter-panel'"))
  }
}
