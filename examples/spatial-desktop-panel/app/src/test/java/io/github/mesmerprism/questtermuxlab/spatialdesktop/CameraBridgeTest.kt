package io.github.mesmerprism.questtermuxlab.spatialdesktop

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CameraBridgeTest {
  @Test fun packsStridedYuv420AsNv21() {
    val y = PackedYuvPlane(byteArrayOf(1, 2, 99, 3, 4, 99), rowStride = 3, pixelStride = 1)
    val u = PackedYuvPlane(byteArrayOf(5, 99), rowStride = 2, pixelStride = 2)
    val v = PackedYuvPlane(byteArrayOf(6, 99), rowStride = 2, pixelStride = 2)
    assertArrayEquals(byteArrayOf(1, 2, 3, 4, 6, 5), Yuv420ToNv21.pack(2, 2, y, u, v))
  }

  @Test fun snapshotRequestRequiresExactPathAndBearerToken() {
    val token = "a".repeat(64)
    assertTrue(
      SnapshotRequestPolicy.accepts(
        "GET /snapshot.jpg HTTP/1.1",
        mapOf("authorization" to "Bearer $token"),
        token,
      )
    )
    assertFalse(SnapshotRequestPolicy.accepts("GET / HTTP/1.1", mapOf("authorization" to "Bearer $token"), token))
    assertFalse(SnapshotRequestPolicy.accepts("GET /snapshot.jpg HTTP/1.1", mapOf("authorization" to "Bearer wrong"), token))
  }
}
