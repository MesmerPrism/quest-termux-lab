package io.github.mesmerprism.questtermuxlab.spatialcodex

import android.app.AlertDialog
import android.os.Bundle
import android.util.Base64
import android.util.Log
import android.view.ViewTreeObserver
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import com.meta.spatial.core.Entity
import com.meta.spatial.core.Pose
import com.meta.spatial.core.Quaternion
import com.meta.spatial.core.SpatialFeature
import com.meta.spatial.core.SpatialSDKExperimentalAPI
import com.meta.spatial.core.Vector2
import com.meta.spatial.core.Vector3
import com.meta.spatial.runtime.ReferenceSpace
import com.meta.spatial.toolkit.AppSystemActivity
import com.meta.spatial.toolkit.DpPerMeterDisplayOptions
import com.meta.spatial.toolkit.Grabbable
import com.meta.spatial.toolkit.GrabbableType
import com.meta.spatial.toolkit.LayoutXMLPanelRegistration
import com.meta.spatial.toolkit.PanelDimensions
import com.meta.spatial.toolkit.PanelRegistration
import com.meta.spatial.toolkit.PanelRenderMode
import com.meta.spatial.toolkit.PanelStyleOptions
import com.meta.spatial.toolkit.QuadShapeOptions
import com.meta.spatial.toolkit.Scale
import com.meta.spatial.toolkit.Transform
import com.meta.spatial.toolkit.UIPanelRenderOptions
import com.meta.spatial.toolkit.UIPanelSettings
import com.meta.spatial.toolkit.Visible
import com.meta.spatial.toolkit.createPanelEntity
import com.meta.spatial.vr.LocomotionControls
import com.meta.spatial.vr.VRFeature
import com.meta.spatial.vr.VrInputSystemType
import java.security.SecureRandom
import java.util.concurrent.Executors
import org.json.JSONObject

class SpatialCodexWorkbenchActivity : AppSystemActivity() {
  private val executor = Executors.newSingleThreadExecutor()
  private val http = LoopbackHttpClient()
  private var panelEntity: Entity? = null
  private var webView: WebView? = null
  private lateinit var token: String

  override fun registerFeatures(): List<SpatialFeature> =
    listOf(VRFeature(this, LocomotionControls.Right, false, VrInputSystemType.INTERACTION_SDK))

  override fun registerPanels(): List<PanelRegistration> =
    listOf(
      LayoutXMLPanelRegistration(
        R.id.workbench_panel,
        layoutIdCreator = { R.layout.spatial_codex_workbench },
        settingsCreator = {
          UIPanelSettings(
            shape = QuadShapeOptions(width = PANEL_WIDTH_METERS, height = PANEL_HEIGHT_METERS),
            style = PanelStyleOptions(themeResourceId = R.style.AppTheme),
            display = DpPerMeterDisplayOptions(dpPerMeter = 800f),
            rendering = UIPanelRenderOptions(PanelRenderMode.Layer()),
          )
        },
        panelSetupWithRootView = { root, panel, _ ->
          panel.layer?.setZIndex(10)
          installFirstDrawMarker(root)
          configureWebView(root.findViewById(R.id.workbench_web))
        },
      )
    )

  override fun onCreate(savedInstanceState: Bundle?) {
    token = loadOrCreateToken()
    super.onCreate(savedInstanceState)
  }

  @OptIn(SpatialSDKExperimentalAPI::class)
  override fun onSceneReady() {
    super.onSceneReady()
    scene.setReferenceSpace(ReferenceSpace.LOCAL_FLOOR)
    panelEntity =
      Entity.createPanelEntity(
        R.id.workbench_panel,
        Transform(currentViewerRelativePose()),
        PanelDimensions(Vector2(PANEL_WIDTH_METERS, PANEL_HEIGHT_METERS)),
        Scale(Vector3(1f, 1f, 1f)),
        Grabbable(enabled = true, type = GrabbableType.PIVOT_Y, minHeight = 0.55f, maxHeight = 2.5f),
        Visible(true),
      )
    Log.i(TAG, "SPATIAL_CODEX_WORKBENCH_SCENE_READY grabbable=present layer=true")
  }

  @Suppress("SetJavaScriptEnabled")
  private fun configureWebView(view: WebView) {
    webView = view
    view.settings.apply {
      javaScriptEnabled = true
      allowFileAccess = false
      allowContentAccess = false
      domStorageEnabled = false
      databaseEnabled = false
      setGeolocationEnabled(false)
      mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
      allowFileAccessFromFileURLs = false
      allowUniversalAccessFromFileURLs = false
      mediaPlaybackRequiresUserGesture = true
    }
    view.webViewClient =
      object : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean = true
      }
    view.addJavascriptInterface(WorkbenchJavascriptBridge(), "WorkbenchNative")
    val html = assets.open("index.html").bufferedReader(Charsets.UTF_8).use { it.readText() }
    view.loadDataWithBaseURL(APP_ASSET_ORIGIN, html, "text/html", "UTF-8", null)
  }

  private inner class WorkbenchJavascriptBridge {
    @JavascriptInterface
    fun startBroker(requestId: String) {
      if (!BrokerContract.validateRequestId(requestId)) return
      executor.execute {
        runCatching {
          WorkbenchSidecarLauncher(this@SpatialCodexWorkbenchActivity).start(token)
          waitForBroker()
        }.onSuccess { reply(requestId, it) }
          .onFailure { replyError(requestId, it) }
      }
    }

    @JavascriptInterface
    fun request(requestId: String, method: String, path: String, body: String) {
      if (!BrokerContract.validateRequestId(requestId)) return
      val normalizedMethod = method.uppercase()
      if (!BrokerContract.isAllowed(normalizedMethod, path)) {
        replyError(requestId, IllegalArgumentException("Request is not allowlisted."))
        return
      }
      if (body.toByteArray(Charsets.UTF_8).size > BrokerContract.MAX_BODY_BYTES) {
        replyError(requestId, IllegalArgumentException("Request body is too large."))
        return
      }
      val confirmation = BrokerContract.confirmationFor(normalizedMethod, path)
      if (confirmation == null) {
        executeRequest(requestId, normalizedMethod, path, body)
      } else {
        runOnUiThread {
          AlertDialog.Builder(this@SpatialCodexWorkbenchActivity)
            .setTitle("Confirm workbench action")
            .setMessage(confirmation)
            .setNegativeButton("Cancel") { _, _ -> replyError(requestId, IllegalStateException("Action canceled by operator.")) }
            .setPositiveButton("Continue") { _, _ -> executeRequest(requestId, normalizedMethod, path, body) }
            .show()
        }
      }
    }

    @JavascriptInterface
    fun recenterPanel(requestId: String) {
      if (!BrokerContract.validateRequestId(requestId)) return
      runOnUiThread {
        runCatching {
          val entity = requireNotNull(panelEntity) { "Panel is not ready." }
          val scale = entity.getComponent<Scale>()
          entity.setComponent(Transform(currentViewerRelativePose()))
          check(entity.getComponent<Scale>() == scale) { "Panel scale changed during recenter." }
          "{\"status\":\"recentered\"}"
        }.onSuccess { reply(requestId, it) }
          .onFailure { replyError(requestId, it) }
      }
    }
  }

  private fun executeRequest(requestId: String, method: String, path: String, body: String) {
    executor.execute {
      runCatching { http.request(method, path, body, token) }
        .onSuccess { reply(requestId, it) }
        .onFailure { replyError(requestId, it) }
    }
  }

  private fun waitForBroker(): String {
    var last: Throwable? = null
    repeat(40) {
      runCatching { http.request("GET", "/v1/status", "{}", token) }
        .onSuccess { return it }
        .onFailure { last = it }
      Thread.sleep(500)
    }
    throw IllegalStateException("Broker did not become ready.", last)
  }

  private fun reply(requestId: String, payload: String) {
    val request = JSONObject.quote(requestId)
    val value = JSONObject.quote(payload)
    runOnUiThread { webView?.evaluateJavascript("window.Workbench && window.Workbench.onNativeResponse($request,$value)", null) }
  }

  private fun replyError(requestId: String, error: Throwable) {
    val payload =
      JSONObject()
        .put("error", JSONObject().put("message", error.message?.take(512) ?: "Operation failed."))
        .toString()
    reply(requestId, payload)
  }

  private fun loadOrCreateToken(): String {
    val preferences = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
    preferences.getString(TOKEN_KEY, null)?.let { existing ->
      if (existing.length in 32..256) return existing
    }
    val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
    val created = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    preferences.edit().putString(TOKEN_KEY, created).apply()
    return created
  }

  private fun installFirstDrawMarker(root: android.view.View) {
    lateinit var listener: ViewTreeObserver.OnDrawListener
    var logged = false
    listener =
      ViewTreeObserver.OnDrawListener {
        if (!logged) {
          logged = true
          Log.i(TAG, "SPATIAL_CODEX_WORKBENCH_FIRST_DRAW size=${root.width}x${root.height}")
          root.post { if (root.viewTreeObserver.isAlive) root.viewTreeObserver.removeOnDrawListener(listener) }
        }
      }
    root.viewTreeObserver.addOnDrawListener(listener)
  }

  @OptIn(SpatialSDKExperimentalAPI::class)
  private fun currentViewerRelativePose(): Pose {
    val viewer = runCatching { scene.getViewerPose() }.getOrNull()
    val origin = viewer?.t ?: Vector3(0f, 1.6f, 0f)
    val rawForward = viewer?.forward() ?: Vector3(0f, 0f, -1f)
    val horizontal = Vector3(rawForward.x, 0f, rawForward.z)
    val length = kotlin.math.sqrt(horizontal.x * horizontal.x + horizontal.z * horizontal.z).coerceAtLeast(0.001f)
    val forward = Vector3(horizontal.x / length, 0f, horizontal.z / length)
    val center =
      Vector3(
        origin.x + forward.x * PANEL_DISTANCE_METERS,
        origin.y - 0.10f,
        origin.z + forward.z * PANEL_DISTANCE_METERS,
      )
    return Pose(center, Quaternion.fromDirection(forward, Vector3(0f, 1f, 0f)))
  }

  override fun onDestroy() {
    webView?.removeJavascriptInterface("WorkbenchNative")
    webView?.destroy()
    webView = null
    executor.shutdownNow()
    super.onDestroy()
  }

  companion object {
    private const val TAG = "SpatialCodex"
    private const val APP_ASSET_ORIGIN = "https://appassets.androidplatform.net/"
    private const val PANEL_WIDTH_METERS = 1.60f
    private const val PANEL_HEIGHT_METERS = 0.90f
    private const val PANEL_DISTANCE_METERS = 1.45f
    private const val PREFERENCES = "spatial_codex_workbench"
    private const val TOKEN_KEY = "broker_token"
  }
}
