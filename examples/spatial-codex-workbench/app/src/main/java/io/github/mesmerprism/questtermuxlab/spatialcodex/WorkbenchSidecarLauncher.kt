package io.github.mesmerprism.questtermuxlab.spatialcodex

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class WorkbenchSidecarLauncher(private val context: Context) {
  fun start(token: String) {
    synchronized(START_LOCK) {
      if (brokerReady(token)) return
      installBundledRuntime()
      dispatchServer(token)
      waitForBroker(token)
    }
  }

  private fun brokerReady(token: String): Boolean =
    runCatching { LoopbackHttpClient().request("GET", "/v1/status", "{}", token) }.isSuccess

  private fun waitForBroker(token: String) {
    var last: Throwable? = null
    repeat(60) {
      runCatching { LoopbackHttpClient().request("GET", "/v1/status", "{}", token) }
        .onSuccess { return }
        .onFailure { last = it }
      Thread.sleep(500)
    }
    throw IllegalStateException("Broker did not become ready after launch.", last)
  }

  private fun installBundledRuntime() {
    val requestId = REQUEST_IDS.incrementAndGet()
    val resultAction = "$RESULT_ACTION.$requestId"
    val latch = CountDownLatch(1)
    var failure: IllegalStateException? = null
    val receiver =
      object : BroadcastReceiver() {
        override fun onReceive(receiverContext: Context?, intent: Intent?) {
          val result = intent?.getBundleExtra(EXTRA_RESULT)
          val exitCode = result?.getInt("exitCode", Int.MIN_VALUE) ?: Int.MIN_VALUE
          if (exitCode != 0) {
            val detail =
              sequenceOf(result?.getString("stderr"), result?.getString("errmsg"))
                .filterNotNull()
                .joinToString(" ")
                .replace('\n', ' ')
                .take(MAX_RESULT_CHARS)
            failure = IllegalStateException("Termux runtime bootstrap failed (exit $exitCode): $detail")
          }
          latch.countDown()
        }
      }
    context.registerReceiver(receiver, IntentFilter(resultAction), Context.RECEIVER_NOT_EXPORTED)
    try {
      val pendingIntent =
        PendingIntent.getBroadcast(
          context,
          requestId,
          Intent(resultAction).setPackage(context.packageName),
          PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_MUTABLE,
        )
      dispatch(
        path = SH_PATH,
        arguments = arrayOf("-s"),
        workdir = TERMUX_HOME,
        stdin = bundledRuntimeScript(),
        pendingIntent = pendingIntent,
      )
      check(latch.await(BOOTSTRAP_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
        "Timed out while installing the bundled Termux runtime."
      }
      failure?.let { throw it }
    } finally {
      runCatching { context.unregisterReceiver(receiver) }
    }
  }

  private fun bundledRuntimeScript(): String {
    val script = StringBuilder("set -eu\numask 077\nmkdir -p '$TERMUX_PREFIX/tmp'\n")
    for ((assetPath, destination) in BUNDLED_FILES) {
      val content = context.assets.open(assetPath).bufferedReader(Charsets.UTF_8).use { it.readText() }
      appendBundledFile(script, destination, content)
    }
    appendBundledFile(script, "demo-project/.gitignore", "build/\n*.apk\n*.idsig\n*.keystore\n")
    return script.toString()
  }

  private fun appendBundledFile(script: StringBuilder, relative: String, content: String) {
    require(relative.matches(Regex("[A-Za-z0-9._/-]+")) && !relative.contains("..") && !relative.startsWith('/'))
    val destination = "$BUNDLE_ROOT/$relative"
    val parent = destination.substringBeforeLast('/')
    val encoded = android.util.Base64.encodeToString(content.toByteArray(Charsets.UTF_8), android.util.Base64.NO_WRAP)
    script.append("mkdir -p '").append(parent).append("'\n")
    script.append("printf '%s' '").append(encoded).append("' | '").append(BASE64_PATH).append("' -d > '").append(destination).append("'\n")
    script.append("chmod ").append(if (relative == "demo-project/build.sh") "700" else "600").append(" '").append(destination).append("'\n")
  }

  private fun dispatchServer(token: String) {
    val resultIntent = Intent(RESULT_ACTION).setPackage(context.packageName)
    val resultPendingIntent =
      PendingIntent.getBroadcast(
        context,
        1,
        resultIntent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
      )
    dispatch(
      path = ENV_PATH,
      arguments =
        arrayOf(
          "WORKBENCH_TOKEN=$token",
          "WORKBENCH_PORT=${BrokerContract.PORT}",
          "WORKBENCH_PROXY_PORT=$PROXY_PORT",
          "WORKBENCH_ROOT=$WORKSPACE_ROOT",
          "WORKBENCH_TEMPLATE_ROOT=$TEMPLATE_ROOT",
          // Horizon OS blocks the Linux kernel primitives used by Codex's
          // workspace-write sandbox. The broker still confines this PoC to a
          // generated worktree and keeps Git, build, and deploy behind typed
          // review gates, but this is not an OS-level filesystem boundary.
          "WORKBENCH_CODEX_SANDBOX=danger-full-access",
          "ANDROID_JAR=$ANDROID_JAR",
          "SSL_CERT_FILE=$TERMUX_PREFIX/etc/tls/cert.pem",
          "TMPDIR=$TERMUX_PREFIX/tmp",
          "HTTPS_PROXY=http://127.0.0.1:$PROXY_PORT",
          "https_proxy=http://127.0.0.1:$PROXY_PORT",
          "NO_PROXY=127.0.0.1,localhost",
          "node",
          SERVER_PATH,
        ),
      workdir = BUNDLE_ROOT,
      pendingIntent = resultPendingIntent,
    )
  }

  private fun dispatch(
    path: String,
    arguments: Array<String>,
    workdir: String,
    stdin: String? = null,
    pendingIntent: PendingIntent,
  ) {
    val command =
      Intent(RUN_COMMAND_ACTION)
        .setComponent(ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE))
        .putExtra(EXTRA_PATH, path)
        .putExtra(EXTRA_ARGUMENTS, arguments)
        .putExtra(EXTRA_WORKDIR, workdir)
        .putExtra(EXTRA_BACKGROUND, true)
        .putExtra(EXTRA_PENDING_INTENT, pendingIntent)
    if (stdin != null) command.putExtra(EXTRA_STDIN, stdin)
    context.startForegroundService(command)
  }

  companion object {
    private const val TERMUX_PACKAGE = "com.termux"
    private const val RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService"
    private const val RUN_COMMAND_ACTION = "com.termux.RUN_COMMAND"
    private const val EXTRA_PATH = "com.termux.RUN_COMMAND_PATH"
    private const val EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS"
    private const val EXTRA_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR"
    private const val EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND"
    private const val EXTRA_STDIN = "com.termux.RUN_COMMAND_STDIN"
    private const val EXTRA_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT"
    private const val EXTRA_RESULT = "result"
    private const val TERMUX_PREFIX = "/data/data/com.termux/files/usr"
    private const val TERMUX_HOME = "/data/data/com.termux/files/home"
    private const val BUNDLE_ROOT = "$TERMUX_HOME/.local/share/spatial-codex-workbench"
    private const val SERVER_PATH = "$BUNDLE_ROOT/sidecar/src/server.mjs"
    private const val TEMPLATE_ROOT = "$BUNDLE_ROOT/demo-project"
    private const val WORKSPACE_ROOT = "$TERMUX_HOME/codex-workspaces"
    private const val ANDROID_JAR = "$TERMUX_HOME/quest-lab/android-sdk/platforms/android-33/android.jar"
    private const val ENV_PATH = "$TERMUX_PREFIX/bin/env"
    private const val SH_PATH = "$TERMUX_PREFIX/bin/sh"
    private const val BASE64_PATH = "$TERMUX_PREFIX/bin/base64"
    private const val RESULT_ACTION = "io.github.mesmerprism.questtermuxlab.spatialcodex.SIDECAR_RESULT"
    private const val BOOTSTRAP_TIMEOUT_SECONDS = 20L
    private const val PROXY_PORT = 47822
    private const val MAX_RESULT_CHARS = 512
    private val START_LOCK = Any()
    private val REQUEST_IDS = AtomicInteger(100)
    private val BUNDLED_FILES =
      listOf(
        "workbench/sidecar/package.json" to "sidecar/package.json",
        "workbench/sidecar/src/adb-adapter.mjs" to "sidecar/src/adb-adapter.mjs",
        "workbench/sidecar/src/build-adapter.mjs" to "sidecar/src/build-adapter.mjs",
        "workbench/sidecar/src/codex-runner.mjs" to "sidecar/src/codex-runner.mjs",
        "workbench/sidecar/src/connect-proxy.mjs" to "sidecar/src/connect-proxy.mjs",
        "workbench/sidecar/src/errors.mjs" to "sidecar/src/errors.mjs",
        "workbench/sidecar/src/event-journal.mjs" to "sidecar/src/event-journal.mjs",
        "workbench/sidecar/src/github-adapter.mjs" to "sidecar/src/github-adapter.mjs",
        "workbench/sidecar/src/process-runner.mjs" to "sidecar/src/process-runner.mjs",
        "workbench/sidecar/src/server.mjs" to "sidecar/src/server.mjs",
        "workbench/sidecar/src/tool-registry.mjs" to "sidecar/src/tool-registry.mjs",
        "workbench/sidecar/src/util.mjs" to "sidecar/src/util.mjs",
        "workbench/sidecar/src/workspace-manager.mjs" to "sidecar/src/workspace-manager.mjs",
        "workbench/demo-project/AndroidManifest.xml.template" to "demo-project/AndroidManifest.xml.template",
        "workbench/demo-project/build.sh" to "demo-project/build.sh",
        "workbench/demo-project/README.md" to "demo-project/README.md",
        "workbench/demo-project/version.properties" to "demo-project/version.properties",
        "workbench/demo-project/src/io/github/mesmerprism/questtermuxlab/codexdemo/MainActivity.java" to
          "demo-project/src/io/github/mesmerprism/questtermuxlab/codexdemo/MainActivity.java",
      )
  }
}
