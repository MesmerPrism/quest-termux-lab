package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import java.io.Closeable
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.max
import kotlin.math.sqrt

data class MicrophoneStreamState(
  val active: Boolean,
  val detail: String,
  val bytesSent: Long = 0,
  val rms: Int = 0,
)

internal object Pcm16Meter {
  fun rmsLittleEndian(bytes: ByteArray, length: Int): Int {
    require(length in 0..bytes.size)
    val sampleBytes = length and -2
    if (sampleBytes == 0) return 0
    var sumSquares = 0.0
    var offset = 0
    while (offset < sampleBytes) {
      val sample = ((bytes[offset].toInt() and 0xff) or (bytes[offset + 1].toInt() shl 8)).toShort().toInt()
      sumSquares += sample.toDouble() * sample.toDouble()
      offset += 2
    }
    return sqrt(sumSquares / (sampleBytes / 2)).toInt()
  }
}

/** Streams Quest microphone PCM to the fixed Termux loopback bridge without retaining audio. */
class QuestMicrophoneStreamer(private val onState: (MicrophoneStreamState) -> Unit) : Closeable {
  private val running = AtomicBoolean(false)
  @Volatile private var recorder: AudioRecord? = null
  @Volatile private var socket: Socket? = null

  val isActive: Boolean get() = running.get()

  @SuppressLint("MissingPermission")
  fun start() {
    if (!running.compareAndSet(false, true)) return
    Thread(
      {
        var bytesSent = 0L
        try {
          val minBuffer = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
          check(minBuffer > 0) { "unsupported capture format ($minBuffer)" }
          val localSocket = Socket()
          socket = localSocket
          localSocket.tcpNoDelay = true
          localSocket.connect(InetSocketAddress(InetAddress.getByName(LOOPBACK_HOST), LOOPBACK_PORT), CONNECT_TIMEOUT_MS)
          val localRecorder =
            AudioRecord.Builder()
              .setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
              .setAudioFormat(
                AudioFormat.Builder()
                  .setEncoding(AUDIO_FORMAT)
                  .setSampleRate(SAMPLE_RATE)
                  .setChannelMask(CHANNEL_CONFIG)
                  .build(),
              )
              .setBufferSizeInBytes(max(minBuffer * 2, STREAM_BUFFER_BYTES))
              .build()
          recorder = localRecorder
          check(localRecorder.state == AudioRecord.STATE_INITIALIZED) { "AudioRecord initialization failed" }
          localRecorder.startRecording()
          check(localRecorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) { "microphone did not enter recording state" }
          onState(MicrophoneStreamState(true, "streaming"))
          val buffer = ByteArray(STREAM_BUFFER_BYTES)
          var lastReportAt = System.nanoTime()
          while (running.get()) {
            val count = localRecorder.read(buffer, 0, buffer.size, AudioRecord.READ_BLOCKING)
            if (count < 0) error("AudioRecord read failed ($count)")
            if (count == 0) continue
            localSocket.getOutputStream().write(buffer, 0, count)
            bytesSent += count
            val now = System.nanoTime()
            if (now - lastReportAt >= REPORT_INTERVAL_NANOS) {
              val rms = Pcm16Meter.rmsLittleEndian(buffer, count)
              Log.i(TAG, "SPATIAL_DESKTOP_MIC_FRAME bytes=$bytesSent rms=$rms route=android-loopback-pcm")
              onState(MicrophoneStreamState(true, "streaming", bytesSent, rms))
              lastReportAt = now
            }
          }
        } catch (error: Exception) {
          if (running.get()) {
            Log.w(TAG, "SPATIAL_DESKTOP_MIC_FAILED type=${error.javaClass.simpleName} reason=${error.message}")
            onState(MicrophoneStreamState(false, "failed:${error.javaClass.simpleName}", bytesSent))
          }
        } finally {
          running.set(false)
          closeResources()
          Log.i(TAG, "SPATIAL_DESKTOP_MIC_STOPPED bytes=$bytesSent")
        }
      },
      "quest-mic-capture",
    ).apply { isDaemon = true }.start()
  }

  fun stop() {
    if (!running.getAndSet(false)) return
    closeResources()
    onState(MicrophoneStreamState(false, "stopped"))
  }

  private fun closeResources() {
    val localRecorder = recorder
    recorder = null
    runCatching { localRecorder?.stop() }
    runCatching { localRecorder?.release() }
    val localSocket = socket
    socket = null
    runCatching { localSocket?.close() }
  }

  override fun close() = stop()

  companion object {
    const val LOOPBACK_PORT = 5911
    const val LOOPBACK_HOST = "127.0.0.1"
    const val SAMPLE_RATE = 48_000
    private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
    private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    private const val STREAM_BUFFER_BYTES = 9_600
    private const val CONNECT_TIMEOUT_MS = 2_000
    private const val REPORT_INTERVAL_NANOS = 1_000_000_000L
    private const val TAG = "SpatialDesktop"
  }
}
