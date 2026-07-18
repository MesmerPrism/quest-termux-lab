package io.github.mesmerprism.questtermuxlab.spatialdesktop

import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.EOFException
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import kotlin.math.max

data class RfbLimits(
  val maxWidth: Int = 4096,
  val maxHeight: Int = 4096,
  val maxPixels: Int = 8_388_608,
  val maxRectBytes: Int = 33_554_432,
  val maxNameBytes: Int = 4096,
)

enum class RfbPixelFormat(val bytesPerPixel: Int) {
  BGRA32(4),
  RGB565(2),
}

data class RfbStats(
  var generation: Long = 0,
  var updates: Long = 0,
  var frames: Long = 0,
  var changedPixels: Long = 0,
  var wireBytes: Long = 0,
  var socketReadNanos: Long = 0,
  var decodeNanos: Long = 0,
  var retainedCopyNanos: Long = 0,
  var patchAllocations: Long = 0,
  var copyRects: Long = 0,
  var reconnects: Long = 0,
  var errors: Long = 0,
  var inputEnqueued: Long = 0,
  var inputWritten: Long = 0,
  var inputQueueNanos: Long = 0,
  var inputWriteNanos: Long = 0,
)

data class DecodedPatch(
  val x: Int,
  val y: Int,
  val width: Int,
  val height: Int,
  val pixels: IntArray,
  val wireBytes: Int,
  val socketReadNanos: Long,
  val decodeNanos: Long,
  val retainedCopyNanos: Long,
)

data class DecodedFrame(
  val width: Int,
  val height: Int,
  val generation: Long,
  val sequence: Long,
  val patches: List<DecodedPatch>,
  val changedPixels: Long,
  val wireBytes: Long,
  val decodedAtNanos: Long,
)

class RetainedFramebuffer(private val limits: RfbLimits = RfbLimits()) {
  var width = 0
    private set
  var height = 0
    private set
  var pixels = IntArray(0)
    private set
  var generation = 0L
    private set

  @Synchronized
  fun resize(w: Int, h: Int) {
    validateDimensions(w, h, limits)
    width = w
    height = h
    pixels = IntArray(w * h)
    generation++
  }

  @Synchronized
  fun rawRect(
    x: Int,
    y: Int,
    w: Int,
    h: Int,
    input: DataInputStream,
    pixelFormat: RfbPixelFormat = RfbPixelFormat.BGRA32,
  ): DecodedPatch {
    validateRect(x, y, w, h, width, height, limits)
    val byteCount = Math.multiplyExact(Math.multiplyExact(w, h), pixelFormat.bytesPerPixel)
    val raw = ByteArray(byteCount)
    val readStarted = System.nanoTime()
    input.readFully(raw)
    val readNanos = System.nanoTime() - readStarted

    val decoded = IntArray(w * h)
    val decodeStarted = System.nanoTime()
    var source = 0
    var destination = 0
    when (pixelFormat) {
      RfbPixelFormat.BGRA32 ->
        while (source < raw.size) {
          val b = raw[source].toInt() and 0xff
          val g = raw[source + 1].toInt() and 0xff
          val r = raw[source + 2].toInt() and 0xff
          decoded[destination++] = (0xff shl 24) or (r shl 16) or (g shl 8) or b
          source += 4
        }
      RfbPixelFormat.RGB565 ->
        while (source < raw.size) {
          val value = (raw[source].toInt() and 0xff) or ((raw[source + 1].toInt() and 0xff) shl 8)
          val r = (((value ushr 11) and 0x1f) * 255 + 15) / 31
          val g = (((value ushr 5) and 0x3f) * 255 + 31) / 63
          val b = ((value and 0x1f) * 255 + 15) / 31
          decoded[destination++] = (0xff shl 24) or (r shl 16) or (g shl 8) or b
          source += 2
        }
    }
    val decodeNanos = System.nanoTime() - decodeStarted

    val copyStarted = System.nanoTime()
    for (row in 0 until h) {
      System.arraycopy(decoded, row * w, pixels, (y + row) * width + x, w)
    }
    val copyNanos = System.nanoTime() - copyStarted
    generation++
    return DecodedPatch(x, y, w, h, decoded, byteCount, readNanos, decodeNanos, copyNanos)
  }

  @Synchronized
  fun copyRect(x: Int, y: Int, w: Int, h: Int, sourceX: Int, sourceY: Int): DecodedPatch {
    validateRect(x, y, w, h, width, height, limits)
    validateRect(sourceX, sourceY, w, h, width, height, limits)
    val copied = IntArray(w * h)
    val copyStarted = System.nanoTime()
    for (row in 0 until h) {
      System.arraycopy(pixels, (sourceY + row) * width + sourceX, copied, row * w, w)
    }
    for (row in 0 until h) {
      System.arraycopy(copied, row * w, pixels, (y + row) * width + x, w)
    }
    val copyNanos = System.nanoTime() - copyStarted
    generation++
    return DecodedPatch(x, y, w, h, copied, 4, 0, 0, copyNanos)
  }

  @Synchronized
  fun snapshot(): IntArray = pixels.copyOf()
}

fun validateDimensions(w: Int, h: Int, limits: RfbLimits = RfbLimits()) {
  if (w <= 0 || h <= 0 || w > limits.maxWidth || h > limits.maxHeight || w.toLong() * h > limits.maxPixels) {
    throw IOException("framebuffer dimensions rejected: ${w}x$h")
  }
}

fun validateRect(x: Int, y: Int, w: Int, h: Int, fw: Int, fh: Int, limits: RfbLimits = RfbLimits()) {
  val bytes = w.toLong() * h * 4
  if (x < 0 || y < 0 || w <= 0 || h <= 0 || x.toLong() + w > fw || y.toLong() + h > fh || bytes > limits.maxRectBytes) {
    throw IOException("rectangle rejected")
  }
}

interface RfbListener {
  fun onFramebuffer(frame: DecodedFrame, stats: RfbStats)
  fun onStatus(status: String, stats: RfbStats)
}

class RfbClient(
  private val listener: RfbListener,
  private val limits: RfbLimits = RfbLimits(),
  val pixelFormat: RfbPixelFormat = RfbPixelFormat.BGRA32,
) {
  private val running = AtomicBoolean(false)
  private val lock = Any()
  private var socket: Socket? = null
  private var output: DataOutputStream? = null
  private val writer =
    Executors.newSingleThreadExecutor { runnable -> Thread(runnable, "loopback-rfb-writer").apply { isDaemon = true } }
  val framebuffer = RetainedFramebuffer(limits)
  val stats = RfbStats()
  val isActive: Boolean
    get() = running.get()

  fun connect(host: String = "127.0.0.1", port: Int = 5900) {
    require(InetAddress.getByName(host).isLoopbackAddress) { "interactive RFB endpoint must be loopback" }
    disconnect("reconnect")
    stats.reconnects++
    running.set(true)
    thread(name = "loopback-rfb", isDaemon = true) { runSession(host, port) }
  }

  fun disconnect(reason: String = "operator") {
    if (running.getAndSet(false)) listener.onStatus("disconnecting: $reason", stats)
    synchronized(lock) {
      runCatching { socket?.close() }
      socket = null
      output = null
    }
  }

  private fun runSession(host: String, port: Int) {
    try {
      val s = Socket()
      s.tcpNoDelay = true
      s.connect(InetSocketAddress(host, port), 3000)
      s.soTimeout = 15000
      val input = DataInputStream(s.getInputStream())
      val out = DataOutputStream(s.getOutputStream())
      synchronized(lock) {
        socket = s
        output = out
      }
      negotiate(input, out)
      s.soTimeout = 0
      listener.onStatus("connected loopback-only", stats)
      requestUpdate(false)
      while (running.get()) readServerMessage(input)
    } catch (e: Exception) {
      if (running.get()) {
        stats.errors++
        listener.onStatus("RFB error: ${e.message ?: e.javaClass.simpleName}", stats)
      }
    } finally {
      running.set(false)
      synchronized(lock) {
        runCatching { socket?.close() }
        socket = null
        output = null
      }
      listener.onStatus("disconnected", stats)
    }
  }

  private fun negotiate(input: DataInputStream, out: DataOutputStream) {
    val version = ByteArray(12)
    input.readFully(version)
    if (!String(version, StandardCharsets.US_ASCII).startsWith("RFB 003.")) throw IOException("invalid RFB banner")
    out.write("RFB 003.008\n".toByteArray(StandardCharsets.US_ASCII))
    out.flush()
    val count = input.readUnsignedByte()
    if (count == 0) throw IOException(readReason(input))
    val types = ByteArray(count)
    input.readFully(types)
    if (!types.contains(1.toByte())) throw IOException("server does not offer None security")
    out.writeByte(1)
    out.flush()
    if (input.readInt() != 0) throw IOException(readReason(input))
    out.writeByte(1)
    out.flush()
    val w = input.readUnsignedShort()
    val h = input.readUnsignedShort()
    validateDimensions(w, h, limits)
    val serverFormat = ByteArray(16)
    input.readFully(serverFormat)
    val nameLength = input.readInt()
    if (nameLength !in 0..limits.maxNameBytes) throw IOException("desktop name too long")
    input.skipFully(nameLength)
    framebuffer.resize(w, h)
    setPixelFormat(out)
    setEncodings(out)
  }

  private fun setPixelFormat(out: DataOutputStream) {
    synchronized(lock) {
      out.writeByte(0)
      out.write(byteArrayOf(0, 0, 0))
      out.writeByte(if (pixelFormat == RfbPixelFormat.RGB565) 16 else 32)
      out.writeByte(if (pixelFormat == RfbPixelFormat.RGB565) 16 else 24)
      out.writeByte(0)
      out.writeByte(1)
      out.writeShort(if (pixelFormat == RfbPixelFormat.RGB565) 31 else 255)
      out.writeShort(if (pixelFormat == RfbPixelFormat.RGB565) 63 else 255)
      out.writeShort(if (pixelFormat == RfbPixelFormat.RGB565) 31 else 255)
      out.writeByte(if (pixelFormat == RfbPixelFormat.RGB565) 11 else 16)
      out.writeByte(if (pixelFormat == RfbPixelFormat.RGB565) 5 else 8)
      out.writeByte(0)
      out.write(byteArrayOf(0, 0, 0))
      out.flush()
    }
  }

  private fun setEncodings(out: DataOutputStream) {
    synchronized(lock) {
      out.writeByte(2)
      out.writeByte(0)
      out.writeShort(3)
      out.writeInt(0)
      out.writeInt(1)
      out.writeInt(-223)
      out.flush()
    }
  }

  private fun readServerMessage(input: DataInputStream) {
    when (input.readUnsignedByte()) {
      0 -> {
        input.readUnsignedByte()
        val count = input.readUnsignedShort()
        if (count > 4096) throw IOException("too many rectangles")
        var changed = 0L
        var frameBytes = 0L
        var resize = false
        val patches = ArrayList<DecodedPatch>(count)
        repeat(count) {
          val x = input.readUnsignedShort()
          val y = input.readUnsignedShort()
          val w = input.readUnsignedShort()
          val h = input.readUnsignedShort()
          when (val encoding = input.readInt()) {
            0 -> {
              val patch = framebuffer.rawRect(x, y, w, h, input, pixelFormat)
              patches += patch
              changed += w.toLong() * h
              frameBytes += patch.wireBytes
              stats.socketReadNanos += patch.socketReadNanos
              stats.decodeNanos += patch.decodeNanos
              stats.retainedCopyNanos += patch.retainedCopyNanos
              stats.patchAllocations += 2
            }
            1 -> {
              val sourceX = input.readUnsignedShort()
              val sourceY = input.readUnsignedShort()
              val patch = framebuffer.copyRect(x, y, w, h, sourceX, sourceY)
              patches += patch
              changed += w.toLong() * h
              frameBytes += patch.wireBytes
              stats.retainedCopyNanos += patch.retainedCopyNanos
              stats.patchAllocations++
              stats.copyRects++
            }
            -223 -> {
              framebuffer.resize(w, h)
              resize = true
            }
            else -> throw IOException("unsupported rectangle encoding $encoding")
          }
        }
        stats.updates++
        stats.frames++
        stats.changedPixels += changed
        stats.wireBytes += frameBytes
        stats.generation = framebuffer.generation
        listener.onFramebuffer(
          DecodedFrame(
            framebuffer.width,
            framebuffer.height,
            framebuffer.generation,
            stats.frames,
            patches,
            changed,
            frameBytes,
            System.nanoTime(),
          ),
          stats,
        )
        requestUpdate(!resize)
      }
      2 -> Unit
      3 -> {
        input.readFully(ByteArray(3))
        val n = input.readInt()
        if (n !in 0..limits.maxNameBytes) throw IOException("cut text too long")
        input.skipFully(n)
      }
      else -> throw IOException("unsupported server message")
    }
  }

  fun requestUpdate(incremental: Boolean = true) =
    write { out ->
      out.writeByte(3)
      out.writeByte(if (incremental) 1 else 0)
      out.writeShort(0)
      out.writeShort(0)
      out.writeShort(framebuffer.width)
      out.writeShort(framebuffer.height)
    }

  fun pointer(mask: Int, x: Int, y: Int) =
    write { out ->
      out.writeByte(5)
      out.writeByte(mask)
      out.writeShort(x.coerceIn(0, max(0, framebuffer.width - 1)))
      out.writeShort(y.coerceIn(0, max(0, framebuffer.height - 1)))
    }

  fun key(down: Boolean, keysym: Int) =
    write { out ->
      out.writeByte(4)
      out.writeByte(if (down) 1 else 0)
      out.writeShort(0)
      out.writeInt(keysym)
    }

  private fun write(block: (DataOutputStream) -> Unit) {
    val enqueuedAt = System.nanoTime()
    stats.inputEnqueued++
    writer.execute {
      val writeStarted = System.nanoTime()
      stats.inputQueueNanos += writeStarted - enqueuedAt
      synchronized(lock) {
        val out = output ?: return@synchronized
        try {
          block(out)
          out.flush()
          stats.inputWritten++
          stats.inputWriteNanos += System.nanoTime() - writeStarted
        } catch (_: IOException) {
          disconnect("write failure")
        }
      }
    }
  }

  private fun readReason(input: DataInputStream): String {
    val n = input.readInt()
    if (n !in 0..limits.maxNameBytes) return "invalid server reason"
    val b = ByteArray(n)
    input.readFully(b)
    return String(b, StandardCharsets.UTF_8)
  }
}

private fun DataInputStream.skipFully(count: Int) {
  var left = count
  while (left > 0) {
    val skipped = skipBytes(left)
    if (skipped <= 0) throw EOFException()
    left -= skipped
  }
}
