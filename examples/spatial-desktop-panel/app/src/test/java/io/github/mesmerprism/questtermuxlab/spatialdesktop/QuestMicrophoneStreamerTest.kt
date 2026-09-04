package io.github.mesmerprism.questtermuxlab.spatialdesktop

import org.junit.Assert.assertEquals
import org.junit.Test

class QuestMicrophoneStreamerTest {
  @Test fun computesPcm16RmsWithoutRetainingAudio() {
    val samples = shortArrayOf(-6000, 6000, -6000, 6000)
    val bytes = ByteArray(samples.size * 2)
    samples.forEachIndexed { index, sample ->
      bytes[index * 2] = (sample.toInt() and 0xff).toByte()
      bytes[index * 2 + 1] = (sample.toInt() shr 8).toByte()
    }
    assertEquals(6000, Pcm16Meter.rmsLittleEndian(bytes, bytes.size))
  }

  @Test fun loopbackContractUsesVoiceFriendlyPcm() {
    assertEquals(5911, QuestMicrophoneStreamer.LOOPBACK_PORT)
    assertEquals("127.0.0.1", QuestMicrophoneStreamer.LOOPBACK_HOST)
    assertEquals(48_000, QuestMicrophoneStreamer.SAMPLE_RATE)
  }
}
