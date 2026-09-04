package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.params.StreamConfigurationMap
import android.media.Image
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.util.Size
import java.io.ByteArrayOutputStream
import java.io.Closeable
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs

data class CameraStill(val cameraId: String, val width: Int, val height: Int, val jpegBytes: ByteArray)

internal data class PackedYuvPlane(val bytes: ByteArray, val rowStride: Int, val pixelStride: Int)

internal object Yuv420ToNv21 {
  fun pack(width: Int, height: Int, y: PackedYuvPlane, u: PackedYuvPlane, v: PackedYuvPlane): ByteArray {
    require(width > 0 && height > 0 && width % 2 == 0 && height % 2 == 0) { "YUV dimensions must be positive and even" }
    val output = ByteArray(width * height * 3 / 2)
    copyPlane(y, width, height, output, 0, 1)
    copyPlane(v, width / 2, height / 2, output, width * height, 2)
    copyPlane(u, width / 2, height / 2, output, width * height + 1, 2)
    return output
  }

  fun pack(image: Image): ByteArray {
    require(image.format == ImageFormat.YUV_420_888) { "expected YUV_420_888" }
    val planes = image.planes
    require(planes.size >= 3) { "expected three YUV planes" }
    return pack(
      image.width,
      image.height,
      planes[0].packed(),
      planes[1].packed(),
      planes[2].packed(),
    )
  }

  private fun Image.Plane.packed(): PackedYuvPlane {
    val source = buffer.duplicate()
    val bytes = ByteArray(source.remaining())
    source.get(bytes)
    return PackedYuvPlane(bytes, rowStride, pixelStride)
  }

  private fun copyPlane(
    plane: PackedYuvPlane,
    width: Int,
    height: Int,
    output: ByteArray,
    outputOffset: Int,
    outputPixelStride: Int,
  ) {
    require(plane.rowStride > 0 && plane.pixelStride > 0) { "invalid plane strides" }
    for (row in 0 until height) {
      for (column in 0 until width) {
        val inputIndex = row * plane.rowStride + column * plane.pixelStride
        val outputIndex = outputOffset + row * width * outputPixelStride + column * outputPixelStride
        require(inputIndex in plane.bytes.indices) { "plane buffer is shorter than its declared layout" }
        output[outputIndex] = plane.bytes[inputIndex]
      }
    }
  }
}

class Camera2StillCapture(private val context: Context) : Closeable {
  private val finished = AtomicBoolean(false)
  private val mainHandler = Handler(Looper.getMainLooper())
  private val worker = HandlerThread("quest-camera2-still").apply { start() }
  private val workerHandler = Handler(worker.looper)
  private var reader: ImageReader? = null
  private var device: CameraDevice? = null
  private var session: CameraCaptureSession? = null
  private var completion: ((Result<CameraStill>) -> Unit)? = null
  private val timeout = Runnable { finish(Result.failure(IllegalStateException("camera capture timed out"))) }

  @SuppressLint("MissingPermission")
  fun capture(cameraId: String, callback: (Result<CameraStill>) -> Unit) {
    require(cameraId == "50" || cameraId == "51") { "camera ID must be 50 or 51" }
    check(completion == null) { "capture already started" }
    completion = callback
    try {
      val manager = requireNotNull(context.getSystemService(Context.CAMERA_SERVICE) as? CameraManager) { "Camera2 manager unavailable" }
      require(cameraId in manager.cameraIdList) { "Camera2 camera $cameraId is unavailable" }
      val size = chooseSize(manager.getCameraCharacteristics(cameraId))
      val imageReader = ImageReader.newInstance(size.width, size.height, ImageFormat.YUV_420_888, 2)
      reader = imageReader
      imageReader.setOnImageAvailableListener({ available -> onImage(cameraId, available) }, workerHandler)
      workerHandler.postDelayed(timeout, CAPTURE_TIMEOUT_MS)
      manager.openCamera(
        cameraId,
        object : CameraDevice.StateCallback() {
          override fun onOpened(camera: CameraDevice) {
            if (finished.get()) {
              camera.close()
              return
            }
            device = camera
            configureCapture(camera, imageReader)
          }

          override fun onDisconnected(camera: CameraDevice) {
            camera.close()
            finish(Result.failure(IllegalStateException("camera disconnected")))
          }

          override fun onError(camera: CameraDevice, error: Int) {
            camera.close()
            finish(Result.failure(IllegalStateException("Camera2 open error $error")))
          }
        },
        workerHandler,
      )
    } catch (error: Exception) {
      finish(Result.failure(error))
    }
  }

  private fun chooseSize(characteristics: CameraCharacteristics): Size {
    val map = requireNotNull(characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)) { "camera has no stream map" }
    val sizes = map.getOutputSizes(ImageFormat.YUV_420_888).orEmpty().filter {
      it.width > 0 && it.height > 0 && it.width % 2 == 0 && it.height % 2 == 0 &&
        it.width <= MAX_DIMENSION && it.height <= MAX_DIMENSION
    }
    require(sizes.isNotEmpty()) { "camera has no bounded YUV_420_888 output" }
    return sizes.minBy { size ->
      abs(size.width - PREFERRED_WIDTH).toLong() + abs(size.height - PREFERRED_HEIGHT).toLong()
    }
  }

  private fun configureCapture(camera: CameraDevice, imageReader: ImageReader) {
    camera.createCaptureSession(
      listOf(imageReader.surface),
      object : CameraCaptureSession.StateCallback() {
        override fun onConfigured(configured: CameraCaptureSession) {
          if (finished.get()) {
            configured.close()
            return
          }
          session = configured
          try {
            val request = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply {
              addTarget(imageReader.surface)
              set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
            }
            configured.capture(request.build(), object : CameraCaptureSession.CaptureCallback() {}, workerHandler)
          } catch (error: Exception) {
            finish(Result.failure(error))
          }
        }

        override fun onConfigureFailed(configured: CameraCaptureSession) {
          configured.close()
          finish(Result.failure(IllegalStateException("Camera2 session configuration failed")))
        }
      },
      workerHandler,
    )
  }

  private fun onImage(cameraId: String, imageReader: ImageReader) {
    val image = imageReader.acquireLatestImage() ?: return
    val outcome =
      runCatching {
        val nv21 = Yuv420ToNv21.pack(image)
        val output = ByteArrayOutputStream()
        val compressed =
          YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
            .compressToJpeg(Rect(0, 0, image.width, image.height), JPEG_QUALITY, output)
        check(compressed) { "YUV to JPEG conversion failed" }
        CameraStill(cameraId, image.width, image.height, output.toByteArray())
      }
    image.close()
    finish(outcome)
  }

  private fun finish(result: Result<CameraStill>) {
    if (!finished.compareAndSet(false, true)) return
    workerHandler.removeCallbacks(timeout)
    runCatching { session?.close() }
    runCatching { device?.close() }
    runCatching { reader?.close() }
    session = null
    device = null
    reader = null
    val callback = completion
    completion = null
    worker.quitSafely()
    if (callback != null) mainHandler.post { callback(result) }
  }

  override fun close() {
    finish(Result.failure(CancellationException("camera capture closed")))
  }

  companion object {
    private const val PREFERRED_WIDTH = 1280
    private const val PREFERRED_HEIGHT = 960
    private const val MAX_DIMENSION = 1920
    private const val JPEG_QUALITY = 92
    private const val CAPTURE_TIMEOUT_MS = 6_000L
  }
}
