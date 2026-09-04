package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Color
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.text.Editable
import android.text.TextWatcher
import android.util.Log
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewTreeObserver
import android.view.inputmethod.InputMethodManager
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
  private var connectButton: Button? = null
  private var focusLosses = 0L
  private var inputLine = ""
  private val pendingActions = ArrayDeque<PanelActionRequest>()
  private val lifecycleHandler = Handler(Looper.getMainLooper())
  private val deferredPauseDisconnect = Runnable { disconnect("activity pause") }
  private var pendingCameraId: String? = null
  private var cameraCapture: Camera2StillCapture? = null
  private var snapshotServer: OneShotJpegServer? = null
  private var cameraLauncher: CameraToInkscapeLauncher? = null
  private var microphoneButton: Button? = null
  private var microphoneIndicator: TextView? = null
  private var microphoneLauncher: QuestMicrophoneBridgeLauncher? = null
  private var microphoneStreamer: QuestMicrophoneStreamer? = null
  private var microphoneSourceReady = false
  private var pendingMicrophoneStart = false
  private var microphoneStartInFlight = false
  private var controllerAKeyDown = false
  private var controllerAMotionDown = false
  private var controllerBKeyDown = false
  private var controllerBMotionDown = false
  private var lastControllerRightClickAtMs = 0L
  private var lastControllerVoiceToggleAtMs = 0L
  private var pendingMicrophoneStartedAction: (() -> Unit)? = null
  private var microphoneIndicatorActive = false
  private var imeView: EditText? = null

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
    val rightClick = root.findViewById<Button>(R.id.right_click)
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
        it.onSecondaryClickArmChanged = { armed ->
          rightClick.text = if (armed) "Cancel right-click" else "Right-click mode"
          inputLine = if (armed) "rightClick=armed nextDesktopTap=button3" else "rightClick=normal"
          refreshStatus()
        }
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
    connectButton = root.findViewById<Button>(R.id.connect).also { button ->
      button.text = if (client.isActive) "Disconnect" else "Connect"
      button.setOnClickListener {
        dispatchHuman(if (client.isActive) PanelAction.Disconnect else PanelAction.Connect)
      }
    }
    sizeUp.setOnClickListener { dispatchHuman(PanelAction.SizeUp) }
    sizeDown.setOnClickListener { dispatchHuman(PanelAction.SizeDown) }
    root.findViewById<Button>(R.id.camera_50).setOnClickListener { dispatchHuman(PanelAction.Camera50) }
    root.findViewById<Button>(R.id.camera_51).setOnClickListener { dispatchHuman(PanelAction.Camera51) }
    microphoneButton = root.findViewById<Button>(R.id.microphone).also { button ->
      button.text = "MIC OFF"
      button.setOnClickListener { dispatchHuman(PanelAction.ToggleMicrophone) }
    }
    microphoneIndicator = root.findViewById(R.id.recording_indicator)
    prepareMicrophoneSource()
    rightClick.apply {
      text = "Right-click mode"
      setOnClickListener {
        val armed = framebufferView?.toggleSecondaryClickArm() ?: false
        Log.i(TAG, "$MARKER_RIGHT_CLICK_ARM armed=$armed mode=${presentation.presentationMode}")
      }
    }
    root.findViewById<Button>(R.id.scroll_up).setOnClickListener { dispatchHuman(PanelAction.ScrollUp) }
    root.findViewById<Button>(R.id.scroll_down).setOnClickListener { dispatchHuman(PanelAction.ScrollDown) }
    imeView = root.findViewById<EditText>(R.id.ime).also(::bindKeyboard)
    root.findViewById<Button>(R.id.virtual_keyboard).setOnClickListener {
      dispatchHuman(PanelAction.ShowVirtualKeyboard)
    }
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
    if (requestCode == MICROPHONE_PERMISSION_REQUEST) {
      val shouldStart = pendingMicrophoneStart
      pendingMicrophoneStart = false
      if (shouldStart && hasMicrophonePermission()) {
        startMicrophoneBridge()
      } else {
        microphoneStartInFlight = false
        pendingMicrophoneStartedAction = null
        updateMicrophoneState(MicrophoneStreamState(false, "permission-denied"))
      }
      return
    }
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
    controllerAKeyDown = false
    controllerAMotionDown = false
    controllerBKeyDown = false
    controllerBMotionDown = false
    framebufferView?.releaseInput()
    stopMicrophone("activity-pause")
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
    val windowBackAsControllerB =
      presentation.presentationMode == DesktopPresentationMode.WINDOWED && event.keyCode == KeyEvent.KEYCODE_BACK
    val voiceToggle =
      if (presentation.presentationMode == DesktopPresentationMode.WINDOWED) {
        ControllerButtonMapper.isWindowVoiceClickToggle(event.keyCode)
      } else {
        ControllerButtonMapper.isVoiceClickToggle(event.keyCode)
      }
    if (voiceToggle) {
      if (!client.isActive || client.framebuffer.width <= 0 || client.framebuffer.height <= 0) return false
      when (event.action) {
        KeyEvent.ACTION_DOWN -> {
          val firstDown = !controllerBKeyDown && event.repeatCount == 0
          controllerBKeyDown = true
          if (firstDown) {
            performControllerVoiceToggle(if (windowBackAsControllerB) "horizon-window-back-key" else "android-key-event")
          }
        }
        KeyEvent.ACTION_UP -> controllerBKeyDown = false
      }
      return event.action == KeyEvent.ACTION_DOWN || event.action == KeyEvent.ACTION_UP
    }
    if (!ControllerButtonMapper.isSecondaryClick(event.keyCode)) return false
    if (!client.isActive || client.framebuffer.width <= 0 || client.framebuffer.height <= 0) return false
    when (event.action) {
      KeyEvent.ACTION_DOWN -> {
        val firstDown = !controllerAKeyDown && event.repeatCount == 0
        controllerAKeyDown = true
        if (firstDown) performControllerRightClick("android-key-event")
      }
      KeyEvent.ACTION_UP -> controllerAKeyDown = false
    }
    return event.action == KeyEvent.ACTION_DOWN || event.action == KeyEvent.ACTION_UP
  }

  /** Handles a raw gamepad A event where Horizon exposes it separately from panel pointing. */
  fun handleControllerMotion(event: MotionEvent): Boolean {
    if (
      ControllerButtonMapper.isVoiceClickToggleMotion(
        event.source,
        event.actionMasked,
        event.actionButton,
        event.buttonState,
      )
    ) {
      val down = event.actionMasked == MotionEvent.ACTION_BUTTON_PRESS
      if (down && !controllerBMotionDown) performControllerVoiceToggle("android-gamepad-motion")
      controllerBMotionDown = down
      return true
    }
    if (
      !ControllerButtonMapper.isSecondaryClickMotion(
        event.source,
        event.actionMasked,
        event.actionButton,
        event.buttonState,
      )
    ) return false
    val down = event.actionMasked == MotionEvent.ACTION_BUTTON_PRESS
    if (down && !controllerAMotionDown) performControllerRightClick("android-gamepad-motion")
    controllerAMotionDown = down
    return true
  }

  /** Called from the immersive Spatial SDK controller-component poller on an A pressed edge. */
  fun handleSpatialControllerA(): Boolean = performControllerRightClick("spatial-sdk-controller")
  fun handleSpatialControllerB(): Boolean = performControllerVoiceToggle("spatial-sdk-controller")

  /** Fallback for Horizon window builds that invoke Android Back without dispatching its key event. */
  fun handleWindowBackInvoked(): Boolean {
    if (presentation.presentationMode != DesktopPresentationMode.WINDOWED) return false
    return performControllerVoiceToggle("horizon-window-back-callback")
  }

  private fun performControllerRightClick(source: String): Boolean {
    if (!client.isActive || client.framebuffer.width <= 0 || client.framebuffer.height <= 0) return false
    val now = SystemClock.uptimeMillis()
    if (now - lastControllerRightClickAtMs < CONTROLLER_RIGHT_CLICK_DEDUP_MS) return true
    val view = framebufferView ?: return false
    val input = view.input ?: return false
    lastControllerRightClickAtMs = now
    view.cancelSecondaryClickArm()
    view.suppressPrimaryGestureForControllerAction()
    input.click(3)
    inputLine =
      "controllerButton=A source=$source semanticAction=RightClick inputSeq=${input.sequence} " +
        "mapped=${input.last.x},${input.last.y} buttons=${input.mask}"
    Log.i(
      TAG,
      "$MARKER_CONTROLLER_RIGHT_CLICK source=$source mode=${presentation.presentationMode} " +
        "inputSeq=${input.sequence} mapped=${input.last.x},${input.last.y}",
    )
    refreshStatus()
    return true
  }

  /** B starts capture before clicking Codex voice; the second B click stops both. */
  private fun performControllerVoiceToggle(source: String): Boolean {
    if (!client.isActive || client.framebuffer.width <= 0 || client.framebuffer.height <= 0) return false
    val now = SystemClock.uptimeMillis()
    if (now - lastControllerVoiceToggleAtMs < CONTROLLER_VOICE_TOGGLE_DEDUP_MS) return true
    val view = framebufferView ?: return false
    val input = view.input ?: return false
    lastControllerVoiceToggleAtMs = now
    val clickCodexVoice = {
      view.cancelSecondaryClickArm()
      view.suppressPrimaryGestureForControllerAction()
      input.click(1)
      inputLine =
        "controllerButton=B source=$source semanticAction=VoiceClickToggle inputSeq=${input.sequence} " +
          "mapped=${input.last.x},${input.last.y} microphone=${if (microphoneStreamer?.isActive == true) "on" else "off"}"
      Log.i(
        TAG,
        "$MARKER_CONTROLLER_VOICE_TOGGLE source=$source mode=${presentation.presentationMode} " +
          "inputSeq=${input.sequence} mapped=${input.last.x},${input.last.y}",
      )
      refreshStatus()
    }
    if (microphoneStreamer?.isActive == true) {
      clickCodexVoice()
      stopMicrophone("controller-b")
    } else {
      beginMicrophoneStart(clickCodexVoice)
    }
    return true
  }

  fun onDestroy() {
    lifecycleHandler.removeCallbacks(deferredPauseDisconnect)
    cameraCapture?.close()
    cameraCapture = null
    snapshotServer?.close()
    snapshotServer = null
    cameraLauncher?.close()
    cameraLauncher = null
    microphoneLauncher?.close()
    microphoneLauncher = null
    microphoneStreamer?.close()
    microphoneStreamer = null
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

  private fun toggleMicrophone() {
    if (microphoneStreamer?.isActive == true) {
      stopMicrophone("operator-toggle")
      return
    }
    beginMicrophoneStart()
  }

  private fun beginMicrophoneStart(afterStarted: (() -> Unit)? = null) {
    if (microphoneStartInFlight) {
      inputLine = "microphone=start-already-pending"
      refreshStatus()
      return
    }
    microphoneStartInFlight = true
    pendingMicrophoneStartedAction = afterStarted
    if (!hasMicrophonePermission()) {
      pendingMicrophoneStart = true
      inputLine = "microphone=requesting-permission"
      refreshStatus()
      activity.requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), MICROPHONE_PERMISSION_REQUEST)
      return
    }
    startMicrophoneBridge()
  }

  private fun hasMicrophonePermission(): Boolean =
    activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

  private fun startMicrophoneBridge() {
    updateMicrophoneState(MicrophoneStreamState(false, "preparing-virtual-source"))
    if (microphoneSourceReady) {
      startMicrophoneStreamer()
    } else {
      prepareMicrophoneSource(forceStart = true)
    }
  }

  /** Keep the Linux device present for the session; this does not open Android AudioRecord. */
  private fun prepareMicrophoneSource(forceStart: Boolean = false) {
    if (microphoneLauncher == null) {
      microphoneLauncher =
        QuestMicrophoneBridgeLauncher(activity) { ready ->
          activity.runOnUiThread {
            microphoneSourceReady = ready
            if (!ready) {
              if (microphoneStartInFlight) {
                microphoneStartInFlight = false
                pendingMicrophoneStartedAction = null
              }
              updateMicrophoneState(MicrophoneStreamState(false, "source-unavailable"))
            } else if (microphoneStartInFlight) {
              startMicrophoneStreamer()
            } else {
              updateMicrophoneState(MicrophoneStreamState(false, "source-ready:capture-off"))
            }
          }
        }
    }
    if (!microphoneSourceReady || forceStart) microphoneLauncher?.start()
  }

  private fun startMicrophoneStreamer() {
    val streamer =
      microphoneStreamer ?: QuestMicrophoneStreamer { state ->
        activity.runOnUiThread {
          updateMicrophoneState(state)
          if (state.active) {
            microphoneStartInFlight = false
            pendingMicrophoneStartedAction?.also { pendingMicrophoneStartedAction = null }?.invoke()
          }
          if (!state.active && state.detail.startsWith("failed")) {
            microphoneStartInFlight = false
            pendingMicrophoneStartedAction = null
          }
        }
      }.also { microphoneStreamer = it }
    streamer.start()
  }

  private fun stopMicrophone(reason: String) {
    val wasActive = microphoneStreamer?.isActive == true
    microphoneStreamer?.stop()
    pendingMicrophoneStart = false
    microphoneStartInFlight = false
    pendingMicrophoneStartedAction = null
    if (wasActive) {
      Log.i(TAG, "SPATIAL_DESKTOP_MIC_RELEASED reason=$reason")
      updateMicrophoneState(MicrophoneStreamState(false, "stopped:$reason"))
    }
  }

  private fun updateMicrophoneState(state: MicrophoneStreamState) {
    microphoneButton?.apply {
      text = if (state.active) "● MIC LIVE" else "MIC OFF"
      backgroundTintList = ColorStateList.valueOf(Color.parseColor(if (state.active) "#D50000" else "#E6E0E9"))
      setTextColor(Color.parseColor(if (state.active) "#FFFFFF" else "#1D1B20"))
      contentDescription = if (state.active) "Quest microphone live. Activate to stop." else "Quest microphone off."
    }
    microphoneIndicator?.visibility = if (state.active) View.VISIBLE else View.GONE
    if (state.active != microphoneIndicatorActive) {
      microphoneIndicatorActive = state.active
      Log.i(TAG, "SPATIAL_DESKTOP_MIC_INDICATOR visible=${state.active} actualCapture=${state.active}")
    }
    inputLine = "microphone=${state.detail} bytes=${state.bytesSent} rms=${state.rms} source=quest_mic"
    refreshStatus()
  }

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
      PanelAction.ToggleMicrophone -> toggleMicrophone()
      PanelAction.ShowVirtualKeyboard -> showVirtualKeyboard()
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
    ime.showSoftInputOnFocus = true
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

  private fun showVirtualKeyboard() {
    val ime = imeView ?: error("keyboard input not ready")
    ime.requestFocus()
    ime.post {
      val manager = activity.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
      val accepted = manager.showSoftInput(ime, InputMethodManager.SHOW_IMPLICIT)
      inputLine = "virtualKeyboard=requested accepted=$accepted mode=${presentation.presentationMode}"
      Log.i(
        TAG,
        "SPATIAL_DESKTOP_VIRTUAL_KEYBOARD_REQUESTED mode=${presentation.presentationMode} " +
          "accepted=$accepted focused=${ime.hasFocus()}",
      )
      refreshStatus()
    }
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
      connectButton?.text = if (client.isActive) "Disconnect" else "Connect"
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
    const val MARKER_RIGHT_CLICK_ARM = "SPATIAL_DESKTOP_RIGHT_CLICK_ARM"
    const val MARKER_CONTROLLER_VOICE_TOGGLE = "SPATIAL_DESKTOP_CONTROLLER_VOICE_TOGGLE"
    private const val CONTROLLER_RIGHT_CLICK_DEDUP_MS = 150L
    private const val CONTROLLER_VOICE_TOGGLE_DEDUP_MS = 150L
    private const val MAX_PENDING_ACTIONS = 8
    private const val PAUSE_DISCONNECT_DELAY_MS = 2_000L
    private const val CAMERA_PERMISSION_REQUEST = 501
    private const val MICROPHONE_PERMISSION_REQUEST = 502
    private val CAMERA_PERMISSIONS = arrayOf(Manifest.permission.CAMERA, "horizonos.permission.HEADSET_CAMERA")
  }
}
