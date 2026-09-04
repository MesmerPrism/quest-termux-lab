package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.content.Context
import android.util.AttributeSet
import org.junit.Test

class XmlInflationCompatibilityTest {
  @Test fun framebufferViewExposesXmlInflaterConstructor() {
    FramebufferView::class.java.getConstructor(Context::class.java, AttributeSet::class.java)
  }
}
