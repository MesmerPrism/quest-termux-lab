package io.github.mesmerprism.questtermuxlab.spatialdesktop

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.Closeable
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

internal object SnapshotRequestPolicy {
  fun accepts(requestLine: String, headers: Map<String, String>, expectedToken: String): Boolean {
    if (requestLine != "GET /snapshot.jpg HTTP/1.1") return false
    val supplied = headers["authorization"] ?: return false
    val prefix = "Bearer "
    if (!supplied.startsWith(prefix)) return false
    return MessageDigest.isEqual(
      supplied.removePrefix(prefix).toByteArray(StandardCharsets.UTF_8),
      expectedToken.toByteArray(StandardCharsets.UTF_8),
    )
  }
}

class OneShotJpegServer private constructor(
  private val socket: ServerSocket,
  private val jpegBytes: ByteArray,
  val token: String,
  private val onState: (String) -> Unit,
) : Closeable {
  private val closed = AtomicBoolean(false)
  val url: String = "http://127.0.0.1:${socket.localPort}/snapshot.jpg"

  private val thread =
    Thread({ serve() }, "camera-jpeg-loopback").apply {
      isDaemon = true
      start()
    }

  private fun serve() {
    val deadline = System.nanoTime() + SERVER_LIFETIME_SECONDS * 1_000_000_000L
    var attempts = 0
    var served = false
    try {
      while (!closed.get() && System.nanoTime() < deadline && attempts < MAX_ATTEMPTS && !served) {
        val client = try {
          socket.accept()
        } catch (_: SocketTimeoutException) {
          continue
        }
        attempts++
        client.use { served = handle(it) }
      }
      if (!closed.get()) onState(if (served) "served" else "expired")
    } catch (_: Exception) {
      if (!closed.get()) onState("failed")
    } finally {
      close()
    }
  }

  private fun handle(client: Socket): Boolean {
    client.soTimeout = CLIENT_TIMEOUT_MS
    val input = BufferedInputStream(client.getInputStream())
    val output = BufferedOutputStream(client.getOutputStream())
    val requestLine = readAsciiLine(input) ?: return false
    val headers = linkedMapOf<String, String>()
    var headerBytes = requestLine.length
    while (true) {
      val line = readAsciiLine(input) ?: return false
      headerBytes += line.length
      if (headerBytes > MAX_HEADER_BYTES) {
        respond(output, "431 Request Header Fields Too Large", "text/plain", "headers too large".toByteArray())
        return false
      }
      if (line.isEmpty()) break
      val split = line.indexOf(':')
      if (split > 0) headers[line.substring(0, split).trim().lowercase(Locale.ROOT)] = line.substring(split + 1).trim()
    }
    if (!SnapshotRequestPolicy.accepts(requestLine, headers, token)) {
      respond(output, "403 Forbidden", "text/plain", "forbidden".toByteArray())
      return false
    }
    respond(output, "200 OK", "image/jpeg", jpegBytes)
    return true
  }

  private fun readAsciiLine(input: BufferedInputStream): String? {
    val bytes = ArrayList<Byte>()
    while (bytes.size <= MAX_LINE_BYTES) {
      val value = input.read()
      if (value < 0) return null
      if (value == '\n'.code) {
        if (bytes.lastOrNull() == '\r'.code.toByte()) bytes.removeAt(bytes.lastIndex)
        return bytes.toByteArray().toString(StandardCharsets.US_ASCII)
      }
      bytes.add(value.toByte())
    }
    return null
  }

  private fun respond(output: BufferedOutputStream, status: String, contentType: String, body: ByteArray) {
    val headers =
      "HTTP/1.1 $status\r\n" +
        "Content-Type: $contentType\r\n" +
        "Content-Length: ${body.size}\r\n" +
        "Cache-Control: no-store\r\n" +
        "X-Content-Type-Options: nosniff\r\n" +
        "Connection: close\r\n\r\n"
    output.write(headers.toByteArray(StandardCharsets.US_ASCII))
    output.write(body)
    output.flush()
  }

  override fun close() {
    if (closed.compareAndSet(false, true)) runCatching { socket.close() }
  }

  companion object {
    fun start(jpegBytes: ByteArray, onState: (String) -> Unit): OneShotJpegServer {
      require(jpegBytes.size in 4..MAX_JPEG_BYTES) { "JPEG payload is outside the bounded size" }
      require(jpegBytes[0] == 0xff.toByte() && jpegBytes[1] == 0xd8.toByte()) { "payload is not JPEG" }
      val server = ServerSocket()
      server.reuseAddress = false
      server.soTimeout = ACCEPT_POLL_MS
      server.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0), 1)
      val tokenBytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
      val token = tokenBytes.joinToString("") { "%02x".format(it) }
      return OneShotJpegServer(server, jpegBytes.copyOf(), token, onState)
    }

    private const val MAX_JPEG_BYTES = 16 * 1024 * 1024
    private const val SERVER_LIFETIME_SECONDS = 30L
    private const val ACCEPT_POLL_MS = 1_000
    private const val CLIENT_TIMEOUT_MS = 3_000
    private const val MAX_ATTEMPTS = 4
    private const val MAX_LINE_BYTES = 4_096
    private const val MAX_HEADER_BYTES = 8_192
  }
}
