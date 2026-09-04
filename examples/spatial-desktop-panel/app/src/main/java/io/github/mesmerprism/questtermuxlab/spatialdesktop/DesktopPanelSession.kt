package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.util.Log
import android.view.KeyEvent
import android.view.View
import android.view.ViewTreeObserver
import android.widget.Button
import android.widget.EditText
import android.widget.TextView

/** Shared RFB, input, camera, and lifecycle owner for both hybrid presentations. */
class DesktopPanelSession(
  private val activity: Activity,
  private val presentation: DesktopPresentationHost,
) : RfbListener {
  private val client = RfbClient(this)
  private var framebufferView: FramebufferView? = null
  private var statusView: TextView? = null
  private var focusLosses = 0L
  private var inputLine = ""
  private val pendingActions = ArrayDeque<PanelActionRequest>()
  private val lifecycleHandler = Handler(Looper.getMainLooper())
  private val deferredPauseDisconnect = Runnable { disconnect("activity pause") }
  private var pendingCameraId: String? = null
  private var cameraCapture: Camera2StillCapture? = null
  private var snapshotServer: OneShotJpegServer? = null
  private var cameraLauncher: CameraToInkscapeLauncher? = null

  fun bindPanelViews(root: View) {
    installFirstDrawMarker(root)
    root.findViewById<TextView>(R.id.grab_label).text =
      if (presentation.presentationMode == DesktopPresentationMode.SPATIAL) {
        "SPATIAL DESKTOP • grab panel"
      } else {
        "LINUX DESKTOP • OS-managed window"
      }
    val sizeDown = root.findViewById<Button>(R.id.size_down)
    val sizeUp = root.findViewById<Button>(R.id.size_up)
    val spatial = presentation.presentationMode == DesktopPresentationMode.SPATIAL
    sizeDown.visibility = if (spatial) View.VISIBLE else View.GONE
    sizeUp.visibility = if (spatial) View.VISIBLE else View.GONE
    root.findViewById<Button>(R.id.mode_switch).apply {
      text = if (spatial) "Window" else "Spatial"
      setOnClickListener { dispatchHuman(PanelAction.SwitchPresentation) }
    }
    framebufferView =
      root.findViewById<FramebufferView>(R.id.framebuffer).also {
        it.client = client
        it.input = InputLifecycle { packet -> client.pointer(packet.mask, packet.x, packet.y) }
        it.onInputDiagnostic = { line -> inputLine = line; refreshStatus() }
        it.onFrameApplied = { frame, render ->
          Log.i(
            TAG,
            "SPATIAL_DESKTOP_RFB_APPLIED frame=${frame.sequence} patches=${frame.patches.size} " +
              "queueMs=${render.queueNanos / 1_000_000} applyMs=${render.bitmapApplyNanos / 1_000_000} " +
              "applied=${render.appliedFrames} coalesced=${render.coalescedFrames} " +
              "backpressure=${render.backpressureBlocks} bitmapAllocations=${render.bitmapAllocations}",
          )
          refreshStatus()
        }
        it.onFramePresented = { frame, render ->
          Log.i(
            TAG,
            "SPATIAL_DESKTOP_RFB_PRESENTED frame=${frame.sequence} presented=${render.presentedFrames} " +
              "presentApproxMs=${render.presentApproxNanos / 1_000_000}",
          )
          refreshStatus()
        }
      }
    statusView = root.findViewById(R.id.status)
    root.findViewById<Button>(R.id.connect).setOnClickListener {
      dispatchHuman(if (client.isActive) PanelAction.Disconnect else PanelAction.Connect)
    }
    sizeUp.setOnClickListener { dispatchHuman(PanelAction.SizeUp) }
    sizeDown.setOnClickListener { dispatchHuman(PanelAction.SizeDown) }
    root.findViewById<Button>(R.id.camera_50).setOnClickListener { dispatchHuman(PanelAction.Camera50) }
    root.findViewById<Button>(R.id.camera_51).setOnClickListener { dispatchHuman(PanelAction.Camera51) }
    root.findViewById<Button>(R.id.right_click).setOnClickListener { dispatchHuman(PanelAction.RightClick) }
    root.findViewById<Button>(R.id.scroll_up).setOnClickListener { dispatchHuman(PanelAction.ScrollUp) }
    root.findViewById<Button>(R.id.scroll_down).setOnClickListener { dispatchHuman(PanelAction.ScrollDown) }
    bindKeyboard(root.findViewById(R.id.ime))
    refreshStatus()
    drainPendingActions()
  }

  fun handleIntent(intent: Intent?) {
    if (intent?.getBooleanExtra(HybridDesktopNavigator.EXTRA_AUTO_CONNECT, false) == true) {
      intent.removeExtra(HybridDesktopNavigator.EXTRA_AUTO_CONNECT)
      if (framebufferView != null && !client.isActive) client.connect()
    }
    handleDebugIntent(intent)
  }

  fun onPresentationReady() {
    drainPendingActions()
    refreshStatus()
  }

  fun onRequestPermissionsResult(requestCode: Int) {
    if (requestCode != CAMERA_PERMISSION_REQUEST) return
    val cameraId = pendingCameraId
    pendingCameraId = null
    if (cameraId == null || !hasCameraPermissions()) {
      inputLine = "camera=${cameraId ?: "unknown"} state=permission-denied"
      refreshStatus()
      return
    }
    captureCameraIntoInkscape(cameraId)
  }

  fun onPause() {
    focusLosses++
    framebufferView?.releaseInput()
    lifecycleHandler.removeCallbacks(deferredPauseDisconnect)
    lifecycleHandler.postDelayed(deferredPauseDisconnect, PAUSE_DISCONNECT_DELAY_MS)
  }

  fun onResume() {
    lifecycleHandler.removeCallbacks(deferredPauseDisconnect)
  }

  fun onWindowFocusChanged(hasFocus: Boolean) {
    if (!hasFocus) {
      focusLosses++
      framebufferView?.releaseInput()
      refreshStatus()
    }
  }

  /** Maps the right Touch controller A button to a Linux secondary click. */
  fun handleControllerKey(event: KeyEvent): Boolean {
    if (!ControllerButtonMapper.isSecondaryClick(event.keyCode)) return false
    if (!client.isActive || client.framebuffer.width <= 0 || client.framebuffer.height <= 0) return false
    if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) {
      val input = framebufferView?.input ?: return false
      input.click(3)
      inputLine =
        "controllerButton=A semanticAction=RightClick inputSeq=${input.sequence} " +
          "mapped=${input.last.x},${input.last.y} buttons=${input.mask}"
      Log.i(
        TAG,
        "$MARKER_CONTROLLER_RIGHT_CLICK keyCode=${event.keyCode} inputSeq=${input.sequence} " +
          "mapped=${input.last.x},${input.last.y}",
      )
      refreshStatus()
    }
    return event.action == KeyEvent.ACTION_DOWN || event.action == KeyEvent.ACTION_UP
  }

  fun onDestroy() {
    lifecycleHandler.removeCallbacks(deferredPauseDisconnect)
    cameraCapture?.close()
    cameraCapture = null
    snapshotServer?.close()
    snapshotServer = null
    cameraLauncher?.close()
    cameraLauncher = null
    disconnect("activity destroy")
  }

  private fun installFirstDrawMarker(root: View) {
    lateinit var listener: ViewTreeObserver.OnDrawListener
    var logged = false
    listener =
      ViewTreeObserver.OnDrawListener {
        if (!logged) {
          logged = true
          Log.i(
            TAG,
            "${SpatialPresentationContract.MARKER_FIRST_DRAW} mode=${presentation.presentationMode} " +
              "size=${root.width}x${root.height} visible=${root.visibility}",
          )
          root.post { if (root.viewTreeObserver.isAlive) root.viewTreeObserver.removeOnDrawListener(listener) }
        }
      }
    root.viewTreeObserver.addOnDrawListener(listener)
  }

  private fun beginCameraImport(cameraId: String) {
    require(cameraId == "50" || cameraId == "51") { "unsupported camera ID" }
    if (cameraCapture != null) {
      inputLine = "camera=$cameraId state=busy"
      refreshStatus()
      return
    }
    if (!hasCameraPermissions()) {
      pendingCameraId = cameraId
      inputLine = "camera=$cameraId state=requesting-permission"
      refreshStatus()
      activity.requestPermissions(CAMERA_PERMISSIONS, CAMERA_PERMISSION_REQUEST)
      return
    }
    captureCameraIntoInkscape(cameraId)
  }

  private fun hasCameraPermissions(): Boolean =
    CAMERA_PERMISSIONS.all { activity.checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }

  private fun captureCameraIntoInkscape(cameraId: String) {
    inputLine = "camera=$cameraId state=capturing"
    refreshStatus()
    val capture = Camera2StillCapture(activity)
    cameraCapture = capture
    capture.capture(cameraId) { result ->
      cameraCapture = null
      result.onFailure { error ->
        inputLine = "camera=$cameraId state=failed reason=${error.javaClass.simpleName}"
        Log.w(TAG, "SPATIAL_DESKTOP_CAMERA_CAPTURE_FAILED cameraId=$cameraId type=${error.javaClass.simpleName} reason=${error.message}")
        refreshStatus()
      }
      result.onSuccess { still ->
        runCatching { handStillToTermux(still) }
          .onFailure { error ->
            inputLine = "camera=$cameraId state=bridge-failed reason=${error.javaClass.simpleName}"
            Log.w(TAG, "SPATIAL_DESKTOP_CAMERA_BRIDGE_FAILED cameraId=$cameraId type=${error.javaClass.simpleName} reason=${error.message}")
            refreshStatus()
          }
      }
    }
  }

  private fun handStillToTermux(still: CameraStill) {
    snapshotServer?.close()
    lateinit var server: OneShotJpegServer
    server =
      OneShotJpegServer.start(still.jpegBytes) { state ->
        activity.runOnUiThread {
          if (snapshotServer === server) {
            inputLine = "camera=${still.cameraId} ${still.width}x${still.height} transfer=$state"
            refreshStatus()
          }
        }
      }
    snapshotServer = server
    val launcher =
      cameraLauncher ?: CameraToInkscapeLauncher(activity) { state ->
        activity.runOnUiThread {
          inputLine = state
          refreshStatus()
        }
      }.also { cameraLauncher = it }
    try {
      launcher.launch(still.cameraId, server.url, server.token)
    } catch (error: Exception) {
      server.close()
      snapshotServer = null
      throw error
    }
    inputLine = "camera=${still.cameraId} ${still.width}x${still.height} transfer=loopback-pending"
    Log.i(TAG, "SPATIAL_DESKTOP_CAMERA_CAPTURED cameraId=${still.cameraId} size=${still.width}x${still.height} route=one-shot-loopback")
    refreshStatus()
  }

  private fun dispatchHuman(action: PanelAction) {
    runCatching { dispatchPanelAction(action, "human") }
      .onFailure { Log.w(TAG, "panel action rejected source=human reason=${it.message}") }
  }

  private fun handleDebugIntent(intent: Intent?) {
    if (intent?.action != DebugPanelActionContract.INTENT_ACTION) return
    val requestId = intent.getStringExtra(DebugPanelActionContract.EXTRA_REQUEST_ID)
    val parsed =
      DebugPanelActionContract.parse(
        isDebug = BuildConfig.DEBUG,
        intentAction = intent.action,
        requestId = requestId,
        actionName = intent.getStringExtra(DebugPanelActionContract.EXTRA_ACTION),
        x = if (intent.hasExtra(DebugPanelActionContract.EXTRA_X)) intent.getIntExtra(DebugPanelActionContract.EXTRA_X, -1) else null,
        y = if (intent.hasExtra(DebugPanelActionContract.EXTRA_Y)) intent.getIntExtra(DebugPanelActionContract.EXTRA_Y, -1) else null,
        text = intent.getStringExtra(DebugPanelActionContract.EXTRA_TEXT),
        x2 = if (intent.hasExtra(DebugPanelActionContract.EXTRA_X2)) intent.getIntExtra(DebugPanelActionContract.EXTRA_X2, -1) else null,
        y2 = if (intent.hasExtra(DebugPanelActionContract.EXTRA_Y2)) intent.getIntExtra(DebugPanelActionContract.EXTRA_Y2, -1) else null,
      )
    parsed.onFailure {
      Log.w(TAG, "${DebugPanelActionContract.MARKER_REJECTED} requestId=${requestId ?: "missing"} reason=${it.message}")
    }
    parsed.onSuccess { request ->
      Log.i(TAG, "${DebugPanelActionContract.MARKER_ACCEPTED} requestId=${request.requestId} action=${request.action.javaClass.simpleName}")
      activity.runOnUiThread {
        if (!isReady(request.action)) {
          if (pendingActions.size >= MAX_PENDING_ACTIONS) {
            Log.w(TAG, "${DebugPanelActionContract.MARKER_REJECTED} requestId=${request.requestId} reason=panel-not-ready-queue-full")
          } else {
            pendingActions.addLast(request)
          }
        } else {
          completeDebugAction(request)
        }
      }
    }
  }

  private fun drainPendingActions() {
    repeat(pendingActions.size) {
      val request = pendingActions.removeFirst()
      if (isReady(request.action)) completeDebugAction(request) else pendingActions.addLast(request)
    }
  }

  private fun isReady(action: PanelAction): Boolean =
    framebufferView != null && presentation.isPresentationReady(action)

  private fun completeDebugAction(request: PanelActionRequest) {
    runCatching { dispatchPanelAction(request.action, request.requestId) }
      .onSuccess {
        val stats = client.stats
        Log.i(
          TAG,
          "${DebugPanelActionContract.MARKER_COMPLETED} requestId=${request.requestId} " +
            "mode=${presentation.presentationMode} active=${client.isActive} " +
            "fb=${client.framebuffer.width}x${client.framebuffer.height} " +
            "updates=${stats.updates} frames=${stats.frames} errors=${stats.errors} " +
            "forcedRelease=${framebufferView?.input?.forcedReleases ?: 0} ${presentation.presentationState()}",
        )
      }
      .onFailure {
        Log.w(
          TAG,
          "${DebugPanelActionContract.MARKER_REJECTED} requestId=${request.requestId} " +
            "type=${it.javaClass.simpleName} reason=${it.message}",
        )
      }
  }

  private fun dispatchPanelAction(action: PanelAction, source: String) {
    val input = framebufferView?.input ?: error("panel not ready")
    fun requireConnected() =
      require(client.isActive && client.framebuffer.width > 0 && client.framebuffer.height > 0) { "RFB not connected" }
    fun checked(point: DesktopPoint): DesktopPoint {
      requireConnected()
      require(point.x in 0 until client.framebuffer.width && point.y in 0 until client.framebuffer.height) {
        "point outside framebuffer"
      }
      return point
    }
    when (action) {
      PanelAction.Connect -> if (!client.isActive) client.connect()
      PanelAction.Disconnect -> disconnect(source)
      PanelAction.SizeUp -> presentation.resizeBy(1.1f)
      PanelAction.SizeDown -> presentation.resizeBy(1f / 1.1f)
      PanelAction.RecenterPanel -> presentation.recenterPanel(source)
      PanelAction.SwitchPresentation -> {
        Log.i(TAG, "${HybridDesktopNavigator.MARKER_SWITCH} from=${presentation.presentationMode} source=$source")
        disconnect("presentation switch")
        presentation.switchPresentation()
      }
      PanelAction.RightClick -> { requireConnected(); input.click(3) }
      PanelAction.ScrollUp -> { requireConnected(); input.scroll(-1) }
      PanelAction.ScrollDown -> { requireConnected(); input.scroll(1) }
      PanelAction.Camera50 -> beginCameraImport("50")
      PanelAction.Camera51 -> beginCameraImport("51")
      is PanelAction.PointerMove -> input.move(checked(action.point))
      is PanelAction.PointerDown -> input.press(1, checked(action.point))
      is PanelAction.PointerUp -> input.release(1, checked(action.point))
      is PanelAction.Tap -> input.click(1, checked(action.point))
      is PanelAction.Drag -> input.drag(checked(action.start), checked(action.end))
      is PanelAction.TypeText -> {
        requireConnected()
        action.text.forEach { client.key(true, it.code); client.key(false, it.code) }
      }
      PanelAction.Enter -> {
        requireConnected()
        client.key(true, Keysyms.RETURN)
        client.key(false, Keysyms.RETURN)
      }
      PanelAction.StartSidecar -> {
        require(BuildConfig.DEBUG) { "sidecar start disabled in release build" }
        TermuxSidecarLauncher(activity).start()
      }
      PanelAction.StartWitness -> {
        require(BuildConfig.DEBUG) { "witness start disabled in release build" }
        TermuxWitnessLauncher(activity).start()
      }
      PanelAction.StopWitness -> {
        require(BuildConfig.DEBUG) { "witness stop disabled in release build" }
        TermuxWitnessLauncher(activity).stop()
      }
    }
    inputLine =
      "semanticAction=${action.javaClass.simpleName} inputSeq=${input.sequence} " +
        "mapped=${input.last.x},${input.last.y} buttons=${input.mask}"
    refreshStatus()
  }

  private fun bindKeyboard(ime: EditText) {
    ime.setOnKeyListener { _, _, event ->
      val key = AndroidKeyMapper.map(event) ?: return@setOnKeyListener false
      client.key(event.action == KeyEvent.ACTION_DOWN, key)
      true
    }
    ime.addTextChangedListener(
      object : TextWatcher {
        var internal = false
        override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
        override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
        override fun afterTextChanged(editable: Editable?) {
          if (internal) return
          editable.toString().filter { it.code in 0x20..0x7e }.forEach {
            client.key(true, it.code)
            client.key(false, it.code)
          }
          internal = true
          editable?.clear()
          internal = false
        }
      },
    )
  }

  override fun onFramebuffer(frame: DecodedFrame, stats: RfbStats) {
    if (stats.frames == 1L || stats.frames % 60L == 0L) {
      Log.i(
        TAG,
        "SPATIAL_DESKTOP_RFB_FRAME mode=${presentation.presentationMode} " +
          "fb=${frame.width}x${frame.height} generation=${stats.generation} " +
          "updates=${stats.updates} frames=${stats.frames} changedPixels=${stats.changedPixels} bytes=${stats.wireBytes}",
      )
    }
    Log.i(
      TAG,
      "SPATIAL_DESKTOP_RFB_DECODED frame=${frame.sequence} patches=${frame.patches.size} " +
        "framePixels=${frame.changedPixels} frameBytes=${frame.wireBytes} " +
        "socketMs=${stats.socketReadNanos / 1_000_000} decodeMs=${stats.decodeNanos / 1_000_000} " +
        "retainedCopyMs=${stats.retainedCopyNanos / 1_000_000} patchAllocations=${stats.patchAllocations} " +
        "copyRects=${stats.copyRects}",
    )
    framebufferView?.submit(frame)
  }

  override fun onStatus(message: String, stats: RfbStats) {
    Log.i(
      TAG,
      "SPATIAL_DESKTOP_RFB_STATUS mode=${presentation.presentationMode} status=${message.replace(' ', '_')} " +
        "active=${client.isActive} fb=${client.framebuffer.width}x${client.framebuffer.height} " +
        "pixelFormat=${client.pixelFormat} updates=${stats.updates} frames=${stats.frames} errors=${stats.errors}",
    )
    activity.runOnUiThread {
      if (message == "disconnected") framebufferView?.releaseInput()
      statusView?.tag = message
      refreshStatus()
    }
  }

  private fun refreshStatus() {
    val stats = client.stats
    val render = framebufferView?.renderStatsSnapshot() ?: FramebufferRenderStats()
    statusView?.text =
      "${statusView?.tag ?: "ready"} mode=${presentation.presentationMode} " +
        "fb=${client.framebuffer.width}x${client.framebuffer.height} gen=${stats.generation} " +
        "updates=${stats.updates} frames=${stats.frames} bytes=${stats.wireBytes} " +
        "socketMs=${stats.socketReadNanos / 1_000_000} decodeMs=${stats.decodeNanos / 1_000_000} " +
        "copyMs=${stats.retainedCopyNanos / 1_000_000} queueMs=${render.queueNanos / 1_000_000} " +
        "applyMs=${render.bitmapApplyNanos / 1_000_000} presentMs=${render.presentApproxNanos / 1_000_000} " +
        "coalesced=${render.coalescedFrames} backpressure=${render.backpressureBlocks} " +
        "inputQueueMs=${stats.inputQueueNanos / 1_000_000} inputWriteMs=${stats.inputWriteNanos / 1_000_000} " +
        "focusLoss=$focusLosses forcedRelease=${framebufferView?.input?.forcedReleases ?: 0} " +
        "${presentation.presentationState()}\n$inputLine"
  }

  private fun disconnect(reason: String) {
    framebufferView?.releaseInput()
    client.disconnect(reason)
  }

  companion object {
    private const val TAG = "SpatialDesktop"
    const val MARKER_CONTROLLER_RIGHT_CLICK = "SPATIAL_DESKTOP_CONTROLLER_RIGHT_CLICK"
    private const val MAX_PENDING_ACTIONS = 8
    private const val PAUSE_DISCONNECT_DELAY_MS = 2_000L
    private const val CAMERA_PERMISSION_REQUEST = 501
    private val CAMERA_PERMISSIONS = arrayOf(Manifest.permission.CAMERA, "horizonos.permission.HEADSET_CAMERA")
  }
}
