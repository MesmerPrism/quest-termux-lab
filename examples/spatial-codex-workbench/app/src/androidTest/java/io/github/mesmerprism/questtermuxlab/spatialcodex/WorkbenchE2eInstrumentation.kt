package io.github.mesmerprism.questtermuxlab.spatialcodex

import android.app.Activity
import android.app.Instrumentation
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Bundle
import android.util.Base64
import android.util.Log
import java.security.SecureRandom
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject

/**
 * Shell-owned, debug-only end-to-end harness. It is deliberately kept in the
 * androidTest APK so the shipping APK has no confirmation-bypass entrypoint.
 */
class WorkbenchE2eInstrumentation : Instrumentation() {
  private var arguments = Bundle()
  private lateinit var token: String
  private val http = LoopbackHttpClient()

  override fun onCreate(arguments: Bundle?) {
    this.arguments = arguments ?: Bundle()
    super.onCreate(arguments)
    start()
  }

  override fun onStart() {
    val result = Bundle()
    try {
      token = loadOrCreateToken()
      val mode = arguments.getString("mode", "workflow")
      if (mode == "auth_start" || mode == "workflow" || mode == "deploy") startForegroundActivity()
      if (mode == "probe") {
        result.putString("summary", "probe ${probeTermuxTools().replace('\n', ' ').trim()}")
      } else if (mode == "setup") {
        setupTermuxTools()
        result.putString("summary", "setup public Termux prerequisites installed")
      } else if (mode == "stop_broker") {
        stopOwnedBroker()
        result.putString("summary", "owned workbench broker stopped")
      } else if (mode == "network_probe") {
        result.putString("summary", "network ${probeTermuxNetwork().replace('\n', ' ').trim()}")
      } else if (mode == "stage_android_jar") {
        stageAndroidJar()
        result.putString("summary", "Android platform jar staged and hash-verified in Termux-private storage")
      } else {
        WorkbenchSidecarLauncher(targetContext).start(token)
        waitForBroker()
      }
      when (mode) {
        "probe" -> Unit
        "setup" -> Unit
        "stop_broker" -> Unit
        "network_probe" -> Unit
        "stage_android_jar" -> Unit
        "auth_start" -> startCodexDeviceLogin(result)
        "workflow" -> runWorkflow(result)
        "deploy" -> runDeploy(result)
        else -> error("mode must be probe, setup, stop_broker, network_probe, stage_android_jar, auth_start, workflow, or deploy")
      }
      result.putString("stream", "SPATIAL_CODEX_E2E_PASS ${result.getString("summary")}")
      finish(Activity.RESULT_OK, result)
    } catch (error: Throwable) {
      val message = error.message?.replace('\n', ' ')?.take(512) ?: error.javaClass.simpleName
      Log.e(TAG, "SPATIAL_CODEX_E2E_FAIL $message", error)
      result.putString("stream", "SPATIAL_CODEX_E2E_FAIL $message")
      finish(Activity.RESULT_CANCELED, result)
    }
  }

  private fun runWorkflow(result: Bundle) {
    val capabilities = request("GET", "/v1/capabilities").getJSONArray("capabilities")
    for (required in listOf("node", "git", "codex", "codex_auth", "adb")) {
      val capability = capabilities.objects().firstOrNull { it.getString("id") == required }
      check(capability?.getString("state") == "ready") { "$required is unavailable in Termux" }
    }
    progress("capabilities_ready")

    val workspaceId = "quest-e2e-${System.currentTimeMillis()}"
    request("POST", "/v1/workspaces/demo", JSONObject().put("workspace_id", workspaceId))
    request("POST", "/v1/runs", JSONObject().put("purpose", "quest-e2e"))
    progress("isolated_run_ready")

    val prompt =
      arguments.getString("prompt")
        ?: "Edit only MainActivity.java. Change the subtitle text from 'Source → Git → APK → Quest' to 'Codex CLI → Git → APK → Quest'. Do not change any other file and do not commit."
    val codex = request("POST", "/v1/codex/runs", JSONObject().put("prompt", prompt)).getJSONObject("codex")
    val codexId = codex.getString("operation_id")
    val completedCodex = poll("/v1/codex/runs/$codexId", "codex", CODEX_TIMEOUT_MS)
    check(completedCodex.getString("status") == "completed") { "Codex did not complete: ${completedCodex.optJSONObject("error")}" }
    progress("codex_completed")

    val firstDiff = request("GET", "/v1/repository/diff").getJSONObject("repository")
    check(firstDiff.getString("diff").contains("Codex CLI → Git → APK → Quest")) { "reviewed diff is missing the requested Codex edit" }
    request("POST", "/v1/repository/version/patch")
    val reviewed = request("GET", "/v1/repository/diff").getJSONObject("repository")
    check(!reviewed.getBoolean("truncated") && !reviewed.getBoolean("clean")) { "reviewed change set is not committable" }
    request(
      "POST",
      "/v1/repository/commit",
      JSONObject()
        .put("message", "Build Quest demo through Spatial Codex Workbench")
        .put("review_token", reviewed.getString("review_token")),
    )
    val repository = request("GET", "/v1/repository/status").getJSONObject("repository")
    check(repository.getBoolean("clean")) { "candidate source is not clean after commit" }
    progress("reviewed_commit_ready")

    val startedBuild = request("POST", "/v1/builds", JSONObject().put("kind", "candidate")).getJSONObject("build")
    val buildId = startedBuild.getString("build_id")
    val completedBuild = poll("/v1/builds/$buildId", "build", BUILD_TIMEOUT_MS)
    check(completedBuild.getString("status") == "completed") { "candidate build did not complete: ${completedBuild.optJSONObject("error")}" }
    val artifact = completedBuild.getJSONObject("artifact")
    check(artifact.getString("apk_sha256").matches(Regex("[0-9a-f]{64}"))) { "candidate artifact hash is invalid" }
    targetContext.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putString(BUILD_ID_KEY, buildId).apply()

    val github = request("GET", "/v1/github/status").getJSONObject("github")
    val targets = request("GET", "/v1/adb/targets").getJSONArray("targets")
    result.putString(
      "summary",
      "workflow build_id=$buildId version=${artifact.getString("version_name")} github=${github.optString("state", "unknown")} adb_targets=${targets.length()}",
    )
    progress("candidate_verified")
  }

  private fun startCodexDeviceLogin(result: Bundle) {
    var auth = request("POST", "/v1/codex/auth/device").getJSONObject("auth")
    val deadline = System.currentTimeMillis() + 30_000L
    while (auth.getString("status") == "running" && auth.optString("output").isBlank() && System.currentTimeMillis() < deadline) {
      Thread.sleep(500)
      auth = request("GET", "/v1/codex/auth/device").getJSONObject("auth")
    }
    val output = auth.optString("output", "Codex device login started.").replace('\u0000', ' ').take(8_192)
    Log.i(TAG, "SPATIAL_CODEX_AUTH_OUTPUT ${output.replace('\n', ' ')}")
    result.putString("summary", "auth status=${auth.getString("status")} output=$output")
  }

  private fun runDeploy(result: Bundle) {
    val target = requireNotNull(arguments.getString("adb_target")) { "deploy mode requires adb_target" }
    check(target.matches(Regex("[A-Za-z0-9._:-]{1,128}"))) { "adb_target is invalid" }
    val buildId =
      requireNotNull(targetContext.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(BUILD_ID_KEY, null)) {
        "no completed workflow build is recorded"
      }
    val install =
      request(
        "POST",
        "/v1/deploy/install",
        JSONObject().put("target", target).put("build_id", buildId).put("allow_downgrade", false),
      ).getJSONObject("deploy")
    check(install.getString("status") == "installed") { "candidate APK installation was not confirmed" }
    val launch =
      request("POST", "/v1/deploy/launch", JSONObject().put("target", target).put("build_id", buildId)).getJSONObject("deploy")
    check(launch.getString("status") == "launched" && launch.getInt("fatal_count") == 0) { "candidate APK launch was not verified" }
    result.putString("summary", "deploy build_id=$buildId version=${launch.getString("version_name")} fatal_count=0")
    progress("candidate_installed_and_launched")
  }

  private fun request(method: String, path: String, body: JSONObject = JSONObject()): JSONObject {
    val response = JSONObject(http.request(method, path, body.toString(), token))
    if (response.has("error")) error(response.getJSONObject("error").optString("message", "broker request failed"))
    return response
  }

  private fun poll(path: String, property: String, timeoutMs: Long): JSONObject {
    val deadline = System.currentTimeMillis() + timeoutMs
    while (System.currentTimeMillis() < deadline) {
      val value = request("GET", path).getJSONObject(property)
      if (value.getString("status") != "running") return value
      Thread.sleep(POLL_MS)
    }
    error("timed out waiting for $property")
  }

  private fun waitForBroker() {
    var last: Throwable? = null
    repeat(60) {
      runCatching { request("GET", "/v1/status") }
        .onSuccess { return }
        .onFailure { last = it }
      Thread.sleep(500)
    }
    throw IllegalStateException("broker did not become ready", last)
  }

  private fun startForegroundActivity() {
    val intent =
      Intent(targetContext, SpatialCodexWorkbenchActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
    startActivitySync(intent)
    waitForIdleSync()
  }

  private fun loadOrCreateToken(): String {
    val preferences = targetContext.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    preferences.getString(TOKEN_KEY, null)?.let { if (it.length in 32..256) return it }
    val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
    val created = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    preferences.edit().putString(TOKEN_KEY, created).apply()
    return created
  }

  private fun progress(marker: String) {
    Log.i(TAG, "SPATIAL_CODEX_E2E_STEP $marker")
    sendStatus(0, Bundle().apply { putString("stream", "SPATIAL_CODEX_E2E_STEP $marker\n") })
  }

  private fun probeTermuxTools(): String {
    return runTermuxCommand(
      path = TERMUX_SH,
      arguments = arrayOf("-c", PROBE_SCRIPT),
      timeoutSeconds = 20,
    )
  }

  private fun setupTermuxTools() {
    progress("termux_packages_installing")
    runTermuxCommand(
      path = "$TERMUX_PREFIX/bin/pkg",
      arguments = arrayOf("install", "-y", "nodejs-lts", "git", "gh", "d8"),
      timeoutSeconds = 15 * 60,
    )
    progress("codex_cli_installing")
    runTermuxCommand(
      path = "$TERMUX_PREFIX/bin/npm",
      arguments = arrayOf("install", "--global", "@openai/codex"),
      timeoutSeconds = 15 * 60,
    )
    runTermuxCommand(
      path = TERMUX_SH,
      arguments = arrayOf("-c", INSTALL_CODEX_ARM64_SCRIPT),
      timeoutSeconds = 15 * 60,
    )
    runTermuxCommand(
      path = "$TERMUX_PREFIX/bin/termux-fix-shebang",
      arguments = arrayOf("$TERMUX_PREFIX/lib/node_modules/@openai/codex/bin/codex.js"),
      timeoutSeconds = 30,
    )
    val probe = probeTermuxTools()
    for (required in listOf("node=ready", "git=ready", "codex=ready", "gh=ready", "d8=ready")) {
      check(probe.contains(required)) { "setup completed without $required" }
    }
    progress("termux_prerequisites_ready")
  }

  private fun stopOwnedBroker() {
    runTermuxCommand(
      path = TERMUX_SH,
      arguments = arrayOf("-c", STOP_BROKER_SCRIPT),
      timeoutSeconds = 30,
    )
  }

  private fun probeTermuxNetwork(): String {
    return runTermuxCommand(
      path = TERMUX_SH,
      arguments = arrayOf("-c", NETWORK_PROBE_SCRIPT),
      timeoutSeconds = 60,
    )
  }

  private fun stageAndroidJar() {
    val expectedSha256 = requireNotNull(arguments.getString("sha256")) { "stage_android_jar requires sha256" }
    check(expectedSha256.matches(Regex("[0-9a-f]{64}"))) { "sha256 must be 64 lowercase hexadecimal characters" }
    runTermuxCommand(
      path = TERMUX_SH,
      arguments = arrayOf("-c", STAGE_ANDROID_JAR_SCRIPT, "stage-android-jar", expectedSha256),
      timeoutSeconds = 5 * 60,
    )
  }

  private fun runTermuxCommand(path: String, arguments: Array<String>, timeoutSeconds: Long): String {
    val action = "${targetContext.packageName}.TERMUX_COMMAND.${System.nanoTime()}"
    val latch = CountDownLatch(1)
    var output = ""
    var failure = ""
    val receiver =
      object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
          val command = intent?.getBundleExtra("result")
          output = command?.getString("stdout").orEmpty()
          val exitCode = command?.getInt("exitCode", Int.MIN_VALUE) ?: Int.MIN_VALUE
          if (exitCode != 0) failure = command?.getString("stderr").orEmpty() + command?.getString("errmsg").orEmpty()
          latch.countDown()
        }
      }
    targetContext.registerReceiver(receiver, IntentFilter(action), Context.RECEIVER_NOT_EXPORTED)
    try {
      val resultIntent =
        PendingIntent.getBroadcast(
          targetContext,
          9001,
          Intent(action).setPackage(targetContext.packageName),
          PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_MUTABLE,
        )
      val command =
        Intent("com.termux.RUN_COMMAND")
          .setComponent(ComponentName("com.termux", "com.termux.app.RunCommandService"))
          .putExtra("com.termux.RUN_COMMAND_PATH", path)
          .putExtra("com.termux.RUN_COMMAND_ARGUMENTS", arguments)
          .putExtra("com.termux.RUN_COMMAND_WORKDIR", TERMUX_HOME)
          .putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
          .putExtra("com.termux.RUN_COMMAND_PENDING_INTENT", resultIntent)
      targetContext.startForegroundService(command)
      check(latch.await(timeoutSeconds, TimeUnit.SECONDS)) { "Termux command timed out" }
      check(failure.isBlank()) { "Termux command failed: ${failure.replace('\n', ' ').take(512)}" }
      return output
    } finally {
      runCatching { targetContext.unregisterReceiver(receiver) }
    }
  }

  private fun JSONArray.objects(): Sequence<JSONObject> = sequence {
    for (index in 0 until length()) yield(getJSONObject(index))
  }

  companion object {
    private const val TAG = "SpatialCodexE2E"
    private const val PREFERENCES = "spatial_codex_workbench"
    private const val TOKEN_KEY = "broker_token"
    private const val BUILD_ID_KEY = "e2e_candidate_build_id"
    private const val POLL_MS = 1_000L
    private const val CODEX_TIMEOUT_MS = 15 * 60 * 1000L
    private const val BUILD_TIMEOUT_MS = 15 * 60 * 1000L
    private const val PROBE_SCRIPT =
      "for tool in node nodejs git codex gh adb aapt2 d8 apksigner javac keytool; do " +
        "if command -v \"\$tool\" >/dev/null 2>&1; then echo \"\$tool=ready\"; else echo \"\$tool=missing\"; fi; done; " +
        "echo versions_begin; node --version 2>&1; git --version 2>&1; " +
        "codex_path=\$(command -v codex || true); echo \"codex_path=\$codex_path\"; ls -l \"\$codex_path\" 2>&1; head -n 1 \"\$codex_path\" 2>&1; " +
        "codex --version 2>&1; codex login status 2>&1 || true; gh --version 2>&1 | head -n 1; echo versions_end"
    private const val TERMUX_PREFIX = "/data/data/com.termux/files/usr"
    private const val TERMUX_HOME = "/data/data/com.termux/files/home"
    private const val TERMUX_SH = "$TERMUX_PREFIX/bin/sh"
    private const val INSTALL_CODEX_ARM64_SCRIPT =
      "set -eu; version=\$(node -p \"require('$TERMUX_PREFIX/lib/node_modules/@openai/codex/package.json').version\"); " +
        "npm install --global --force \"@openai/codex-linux-arm64@npm:@openai/codex@\${version}-linux-arm64\""
    private const val STOP_BROKER_SCRIPT =
      "pkill -f '$TERMUX_HOME/.local/share/spatial-codex-workbench/sidecar/src/[s]erver.mjs' || true"
    private const val NETWORK_PROBE_SCRIPT =
      "if test -r '$TERMUX_PREFIX/etc/tls/cert.pem'; then echo cert=ready; else echo cert=missing; fi; " +
        "curl --max-time 20 --silent --show-error --output /dev/null --write-out 'curl_http=%{http_code}\\n' https://auth.openai.com/; " +
        "SSL_CERT_FILE='$TERMUX_PREFIX/etc/tls/cert.pem' node -e \"fetch('https://auth.openai.com/').then(r=>console.log('node_http='+r.status)).catch(e=>{console.error(e.message);process.exit(1)})\""
    private const val STAGE_ANDROID_JAR_SCRIPT =
      "set -eu; expected=\"\$1\"; destination='$TERMUX_HOME/quest-lab/android-sdk/platforms/android-33/android.jar'; " +
        "if test -e \"\$destination\"; then actual=\$(sha256sum \"\$destination\" | sed 's/[[:space:]].*\$//'); test \"\$actual\" = \"\$expected\"; exit 0; fi; " +
        "incoming=\"\$destination.incoming-\$expected\"; test ! -e \"\$incoming\"; mkdir -p \"\$(dirname \"\$destination\")\"; " +
        "curl --fail --silent --show-error --max-time 240 'http://127.0.0.1:47823/android.jar' --output \"\$incoming\"; " +
        "actual=\$(sha256sum \"\$incoming\" | sed 's/[[:space:]].*\$//'); test \"\$actual\" = \"\$expected\"; " +
        "chmod 600 \"\$incoming\"; mv \"\$incoming\" \"\$destination\""
  }
}
