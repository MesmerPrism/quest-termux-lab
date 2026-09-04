package io.github.mesmerprism.questtermuxlab.spatialcodex

object BrokerContract {
  const val HOST = "127.0.0.1"
  const val PORT = 47821
  const val MAX_BODY_BYTES = 64 * 1024
  const val MAX_RESPONSE_BYTES = 4 * 1024 * 1024
  private val requestId = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
  private val safeDynamic = Regex("[A-Za-z0-9._-]{1,64}")

  private val exact =
    setOf(
      "GET /v1/status",
      "GET /v1/capabilities",
      "POST /v1/workspaces/demo",
      "POST /v1/workspaces/clone",
      "POST /v1/runs",
      "POST /v1/codex/runs",
      "POST /v1/codex/auth/device",
      "GET /v1/codex/auth/device",
      "POST /v1/codex/auth/device/cancel",
      "GET /v1/repository/status",
      "GET /v1/repository/diff",
      "POST /v1/repository/version/patch",
      "POST /v1/repository/commit",
      "POST /v1/repository/discard",
      "POST /v1/builds",
      "GET /v1/github/status",
      "POST /v1/github/push-draft-pr",
      "GET /v1/adb/targets",
      "POST /v1/deploy/install",
      "POST /v1/deploy/launch",
    )

  private val confirmations =
    mapOf(
      "POST /v1/repository/commit" to "Commit exactly the reviewed changes?",
      "POST /v1/repository/discard" to "Discard the run-owned uncommitted changes?",
      "POST /v1/github/push-draft-pr" to "Push this run branch and create a draft pull request?",
      "POST /v1/deploy/install" to "Install the verified candidate APK on the selected ADB target?",
      "POST /v1/deploy/launch" to "Launch the verified candidate APK on the selected ADB target?",
    )

  fun validateRequestId(value: String): Boolean = requestId.matches(value)

  fun isAllowed(method: String, rawPath: String): Boolean {
    if (method !in setOf("GET", "POST")) return false
    if (rawPath.length !in 1..256 || rawPath.any { it <= '\u001f' } || rawPath.contains("..")) return false
    val path = rawPath.substringBefore('?')
    if ("$method $path" in exact) return true
    if (method == "GET" && path == "/v1/events") return rawPath == path || rawPath.matches(Regex("/v1/events\\?after=[0-9]+"))
    val segments = path.split('/').filter { it.isNotEmpty() }
    if (segments.size == 4 && segments.take(3) == listOf("v1", "codex", "runs") && method == "GET") return safeDynamic.matches(segments[3])
    if (segments.size == 5 && segments.take(3) == listOf("v1", "codex", "runs") && segments[4] == "cancel" && method == "POST") return safeDynamic.matches(segments[3])
    if (segments.size == 3 && segments.take(2) == listOf("v1", "builds") && method == "GET") return safeDynamic.matches(segments[2])
    return false
  }

  fun confirmationFor(method: String, rawPath: String): String? = confirmations["$method ${rawPath.substringBefore('?')}"]
}
