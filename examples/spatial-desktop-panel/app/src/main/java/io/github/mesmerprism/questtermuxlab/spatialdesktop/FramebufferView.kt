package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.min

data class FramebufferRenderStats(
  var appliedFrames: Long = 0,
  var presentedFrames: Long = 0,
  var coalescedFrames: Long = 0,
  var backpressureBlocks: Long = 0,
  var queueNanos: Long = 0,
  var bitmapApplyNanos: Long = 0,
  var presentApproxNanos: Long = 0,
  var bitmapAllocations: Long = 0,
)

class FramebufferView(context: Context, attrs: AttributeSet? = null) : View(context, attrs) {
  var client: RfbClient? = null
  var input: InputLifecycle? = null
  var onInputDiagnostic: ((String) -> Unit)? = null
  var onFrameApplied: ((DecodedFrame, FramebufferRenderStats) -> Unit)? = null
  var onFramePresented: ((DecodedFrame, FramebufferRenderStats) -> Unit)? = null
  private var bitmap: Bitmap? = null
  private val pending = ArrayBlockingQueue<DecodedFrame>(MAX_PENDING_FRAMES)
  private val applyScheduled = AtomicBoolean(false)
  private val renderStats = FramebufferRenderStats()
  private var lastAppliedFrame: DecodedFrame? = null
  private var lastAppliedAtNanos = 0L
  private var lastPresentedSequence = 0L
  private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
  private val bg = Paint().apply { color = Color.rgb(0, 104, 183) }
  private val diagnostic =
    Paint(Paint.ANTI_ALIAS_FLAG).apply {
      color = Color.WHITE
      textAlign = Paint.Align.CENTER
      textSize = 54f
      isFakeBoldText = true
    }
  private val primaryGesture = PrimaryPointerGestureClassifier(::dispatchPrimaryGesture)

  fun submit(frame: DecodedFrame) {
    val offered = pending.offer(frame)
    if (!offered) {
      synchronized(renderStats) { renderStats.backpressureBlocks++ }
      pending.put(frame)
    }
    scheduleApply()
  }

  fun renderStatsSnapshot(): FramebufferRenderStats =
    synchronized(renderStats) { renderStats.copy() }

  private fun scheduleApply() {
    if (applyScheduled.compareAndSet(false, true)) post(::applyPending)
  }

  private fun applyPending() {
    val frames = ArrayList<DecodedFrame>(MAX_PENDING_FRAMES)
    pending.drainTo(frames)
    if (frames.isNotEmpty()) {
      val applyStarted = System.nanoTime()
      for (frame in frames) {
        ensureBitmap(frame.width, frame.height)
        val target = bitmap ?: continue
        synchronized(renderStats) { renderStats.queueNanos += applyStarted - frame.decodedAtNanos }
        for (patch in frame.patches) {
          target.setPixels(patch.pixels, 0, patch.width, patch.x, patch.y, patch.width, patch.height)
        }
        synchronized(renderStats) { renderStats.appliedFrames++ }
        lastAppliedFrame = frame
      }
      synchronized(renderStats) {
        renderStats.coalescedFrames += (frames.size - 1).coerceAtLeast(0)
        renderStats.bitmapApplyNanos += System.nanoTime() - applyStarted
      }
      lastAppliedAtNanos = System.nanoTime()
      onFrameApplied?.invoke(frames.last(), renderStatsSnapshot())
      postInvalidateOnAnimation()
    }
    applyScheduled.set(false)
    if (pending.isNotEmpty()) scheduleApply()
  }

  private fun ensureBitmap(frameWidth: Int, frameHeight: Int) {
    val current = bitmap
    if (current == null || current.width != frameWidth || current.height != frameHeight) {
      current?.recycle()
      bitmap = Bitmap.createBitmap(frameWidth, frameHeight, Bitmap.Config.ARGB_8888)
      synchronized(renderStats) { renderStats.bitmapAllocations++ }
    }
  }

  override fun onDraw(canvas: Canvas) {
    super.onDraw(canvas)
    canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), bg)
    val b = bitmap
    if (b == null) {
      canvas.drawText("SPATIAL DESKTOP", width / 2f, height / 2f - 16f, diagnostic)
      diagnostic.textSize = 30f
      canvas.drawText("DISCONNECTED • START TERMUX:X11 + x11vnc, THEN CONNECT", width / 2f, height / 2f + 40f, diagnostic)
      diagnostic.textSize = 54f
      return
    }
    val scale = min(width.toFloat() / b.width, height.toFloat() / b.height)
    val left = (width - b.width * scale) / 2
    val top = (height - b.height * scale) / 2
    canvas.drawBitmap(b, null, android.graphics.RectF(left, top, left + b.width * scale, top + b.height * scale), paint)
    val frame = lastAppliedFrame
    if (frame != null && frame.sequence > lastPresentedSequence) {
      synchronized(renderStats) {
        renderStats.presentedFrames++
        renderStats.presentApproxNanos += System.nanoTime() - lastAppliedAtNanos
      }
      lastPresentedSequence = frame.sequence
      onFramePresented?.invoke(frame, renderStatsSnapshot())
    }
  }

  override fun onTouchEvent(e: MotionEvent): Boolean {
    val b = bitmap ?: return false
    val index = e.actionIndex
    val id = e.getPointerId(index)
    val point = DesktopMapping.map(e.getX(index), e.getY(index), width, height, b.width, b.height)
    when (e.actionMasked) {
      MotionEvent.ACTION_HOVER_MOVE -> if (point != null) input?.move(point)
      MotionEvent.ACTION_DOWN ->
        if (point != null) {
          requestFocus()
          primaryGesture.down(id, point, e.eventTime)
        } else {
          return false
        }
      MotionEvent.ACTION_MOVE -> {
        val activeId = e.findPointerIndex(primaryGesture.pointerId ?: -1)
        if (activeId >= 0) DesktopMapping.map(e.getX(activeId), e.getY(activeId), width, height, b.width, b.height)?.let {
          primaryGesture.move(primaryGesture.pointerId ?: -1, it)
        }
      }
      MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> primaryGesture.up(id, point, e.eventTime)
      MotionEvent.ACTION_CANCEL -> {
        primaryGesture.cancel()
      }
      MotionEvent.ACTION_SCROLL -> if (point != null) input?.scroll(if (e.getAxisValue(MotionEvent.AXIS_VSCROLL) > 0) -1 else 1, point)
      MotionEvent.ACTION_POINTER_DOWN, MotionEvent.ACTION_POINTER_UP -> Unit
    }
    input?.let { onInputDiagnostic?.invoke("inputSeq=${it.sequence} mapped=${it.last.x},${it.last.y} buttons=${it.mask} gesture=${primaryGesture.lastClassification} doubleTapSnap=${primaryGesture.doubleTapSnapCount}") }
    return true
  }

  override fun onGenericMotionEvent(event: MotionEvent): Boolean = onTouchEvent(event) || super.onGenericMotionEvent(event)

  override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean = sendKey(true, event) || super.onKeyDown(keyCode, event)

  override fun onKeyUp(keyCode: Int, event: KeyEvent): Boolean = sendKey(false, event) || super.onKeyUp(keyCode, event)

  private fun sendKey(down: Boolean, event: KeyEvent): Boolean {
    val keysym = AndroidKeyMapper.map(event) ?: return false
    client?.key(down, keysym)
    return true
  }

  fun releaseInput() {
    primaryGesture.reset()
    input?.forceRelease()
  }

  private fun dispatchPrimaryGesture(event: PrimaryPointerGestureEvent) {
    val lifecycle = input ?: return
    when (event) {
      is PrimaryPointerGestureEvent.CursorMove -> lifecycle.move(event.point)
      is PrimaryPointerGestureEvent.Press -> lifecycle.press(1, event.point)
      is PrimaryPointerGestureEvent.HeldMove -> lifecycle.move(event.point)
      is PrimaryPointerGestureEvent.Release -> lifecycle.release(1, event.point)
      is PrimaryPointerGestureEvent.Click -> lifecycle.click(1, event.point)
    }
  }

  companion object {
    private const val MAX_PENDING_FRAMES = 2
  }
}
