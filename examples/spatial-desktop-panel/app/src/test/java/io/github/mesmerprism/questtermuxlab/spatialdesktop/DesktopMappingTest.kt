package io.github.mesmerprism.questtermuxlab.spatialdesktop

import org.junit.Assert.*
import org.junit.Test

class DesktopMappingTest {
  @Test fun centerAndCorners(){assertEquals(DesktopPoint(640,360),DesktopMapping.map(640f,360f,1280,720,1280,720));assertEquals(DesktopPoint(0,0),DesktopMapping.map(0f,0f,1280,720,1280,720));assertEquals(DesktopPoint(1279,719),DesktopMapping.map(1279.9f,719.9f,1280,720,1280,720))}
  @Test fun rejectsLetterbox(){assertNull(DesktopMapping.map(10f,10f,1000,1000,1280,720));assertNull(DesktopMapping.map(500f,950f,1000,1000,1280,720));assertEquals(DesktopPoint(640,360),DesktopMapping.map(500f,500f,1000,1000,1280,720))}
  @Test fun resizingAndRemoteResolution(){assertEquals(DesktopPoint(640,360),DesktopMapping.map(800f,450f,1600,900,1280,720));assertEquals(DesktopPoint(960,540),DesktopMapping.map(800f,450f,1600,900,1920,1080))}
  @Test fun invalidSizesReject(){assertNull(DesktopMapping.map(0f,0f,0,720,1280,720));assertNull(DesktopMapping.map(0f,0f,1280,720,0,720))}
}
