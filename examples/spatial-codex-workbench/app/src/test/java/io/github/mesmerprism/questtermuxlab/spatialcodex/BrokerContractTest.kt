package io.github.mesmerprism.questtermuxlab.spatialcodex

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BrokerContractTest {
  @Test fun allowlistAcceptsTypedRoutesAndRejectsRawSurfaces() {
    assertTrue(BrokerContract.isAllowed("GET", "/v1/status"))
    assertTrue(BrokerContract.isAllowed("GET", "/v1/events?after=42"))
    assertTrue(BrokerContract.isAllowed("GET", "/v1/codex/runs/codex-safe"))
    assertTrue(BrokerContract.isAllowed("POST", "/v1/codex/runs/codex-safe/cancel"))
    assertFalse(BrokerContract.isAllowed("POST", "/v1/shell"))
    assertFalse(BrokerContract.isAllowed("POST", "/v1/builds/../../escape"))
    assertFalse(BrokerContract.isAllowed("DELETE", "/v1/workspaces/demo"))
  }

  @Test fun riskyOperationsRequireNativeConfirmation() {
    assertNotNull(BrokerContract.confirmationFor("POST", "/v1/repository/commit"))
    assertNotNull(BrokerContract.confirmationFor("POST", "/v1/deploy/install"))
    assertNull(BrokerContract.confirmationFor("GET", "/v1/repository/diff"))
  }
}
