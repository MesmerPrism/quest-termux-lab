package io.github.mesmerprism.questtermuxlab.spatialcodex

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets

class LoopbackHttpClient {
  fun request(method: String, path: String, body: String, token: String): String {
    require(BrokerContract.isAllowed(method, path)) { "request is not allowlisted" }
    require(body.toByteArray(StandardCharsets.UTF_8).size <= BrokerContract.MAX_BODY_BYTES) { "request body is too large" }
    Socket().use { socket ->
      socket.connect(InetSocketAddress(BrokerContract.HOST, BrokerContract.PORT), CONNECT_TIMEOUT_MS)
      socket.soTimeout = READ_TIMEOUT_MS
      val output = BufferedOutputStream(socket.getOutputStream())
      output.write(HttpWireCodec.encodeRequest(method, path, body, token))
      output.flush()
      return HttpWireCodec.readResponse(BufferedInputStream(socket.getInputStream()))
    }
  }

  companion object {
    private const val CONNECT_TIMEOUT_MS = 3_000
    private const val READ_TIMEOUT_MS = 120_000
  }
}
object HttpWireCodec {
  fun encodeRequest(method: String, path: String, body: String, token: String): ByteArray {
    require(token.length in 32..256 && token.all { it.isLetterOrDigit() || it in "._~-" }) { "invalid broker token" }
    val bodyBytes = body.toByteArray(StandardCharsets.UTF_8)
    val head =
      "$method $path HTTP/1.1\r\n" +
        "Host: ${BrokerContract.HOST}:${BrokerContract.PORT}\r\n" +
        "Authorization: Bearer $token\r\n" +
        "Content-Type: application/json\r\n" +
        "Content-Length: ${bodyBytes.size}\r\n" +
        "Connection: close\r\n\r\n"
    return head.toByteArray(StandardCharsets.US_ASCII) + bodyBytes
  }

  fun readResponse(input: BufferedInputStream): String {
    val header = readHeader(input)
    val lines = header.split("\r\n")
    require(lines.firstOrNull()?.matches(Regex("HTTP/1\\.1 [1-5][0-9]{2} .+")) == true) { "invalid HTTP status" }
    val contentLength =
      lines.drop(1).firstOrNull { it.startsWith("Content-Length:", ignoreCase = true) }
        ?.substringAfter(':')?.trim()?.toIntOrNull()
        ?: error("missing Content-Length")
    require(contentLength in 0..BrokerContract.MAX_RESPONSE_BYTES) { "response body is too large" }
    val bytes = ByteArray(contentLength)
    var offset = 0
    while (offset < bytes.size) {
      val count = input.read(bytes, offset, bytes.size - offset)
      require(count >= 0) { "truncated response body" }
      offset += count
    }
    return bytes.toString(StandardCharsets.UTF_8)
  }

  private fun readHeader(input: BufferedInputStream): String {
    val bytes = ArrayList<Byte>()
    while (bytes.size < MAX_HEADER_BYTES) {
      val value = input.read()
      require(value >= 0) { "truncated HTTP response" }
      bytes.add(value.toByte())
      val size = bytes.size
      if (size >= 4 && bytes[size - 4] == 13.toByte() && bytes[size - 3] == 10.toByte() && bytes[size - 2] == 13.toByte() && bytes[size - 1] == 10.toByte()) {
        return bytes.dropLast(4).toByteArray().toString(StandardCharsets.US_ASCII)
      }
    }
    error("HTTP response headers are too large")
  }

  private const val MAX_HEADER_BYTES = 16 * 1024
}
