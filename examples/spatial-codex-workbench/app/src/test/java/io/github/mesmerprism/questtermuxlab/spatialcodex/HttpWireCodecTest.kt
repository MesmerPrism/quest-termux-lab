package io.github.mesmerprism.questtermuxlab.spatialcodex

import java.io.BufferedInputStream
import java.io.ByteArrayInputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HttpWireCodecTest {
  @Test fun requestIsLoopbackBearerAuthenticatedAndLengthBound() {
    val token = "abcdefghijklmnopqrstuvwxyz0123456789"
    val encoded = HttpWireCodec.encodeRequest("GET", "/v1/status", "{}", token).toString(Charsets.UTF_8)
    assertTrue(encoded.startsWith("GET /v1/status HTTP/1.1\r\n"))
    assertTrue(encoded.contains("Host: 127.0.0.1:47821"))
    assertTrue(encoded.contains("Authorization: Bearer $token"))
    assertTrue(encoded.endsWith("{}"))
  }

  @Test fun responseRequiresContentLengthAndReturnsOnlyBody() {
    val body = "{\"broker\":\"ready\"}"
    val wire = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.toByteArray().size}\r\n\r\n$body"
    assertEquals(body, HttpWireCodec.readResponse(BufferedInputStream(ByteArrayInputStream(wire.toByteArray()))))
  }
}
