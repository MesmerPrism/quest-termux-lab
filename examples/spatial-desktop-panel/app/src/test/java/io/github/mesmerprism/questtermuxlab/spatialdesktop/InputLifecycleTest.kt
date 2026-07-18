package io.github.mesmerprism.questtermuxlab.spatialdesktop

import org.junit.Assert.*
import org.junit.Test

class InputLifecycleTest {
  @Test fun dragOrderAndCancel(){val p=mutableListOf<PointerPacket>();val i=InputLifecycle(p::add);i.move(DesktopPoint(2,3));i.press(1);i.move(DesktopPoint(7,8));i.cancel();assertEquals(listOf(0,1,1,0),p.map{it.mask});assertEquals(1,i.forcedReleases)}
  @Test fun focusReleaseIsIdempotent(){val p=mutableListOf<PointerPacket>();val i=InputLifecycle(p::add);i.press(1);i.press(3);i.forceRelease();i.forceRelease();assertEquals(listOf(1,5,0),p.map{it.mask});assertEquals(1,i.forcedReleases)}
  @Test fun rightClickAndScrollPackets(){val p=mutableListOf<PointerPacket>();val i=InputLifecycle(p::add);i.click(3,DesktopPoint(4,5));i.scroll(-1);i.scroll(1);assertEquals(listOf(4,0,8,0,16,0),p.map{it.mask})}
  @Test fun atomicDragEmitsHeldMoveAndRelease(){val p=mutableListOf<PointerPacket>();val i=InputLifecycle(p::add);i.drag(DesktopPoint(2,3),DesktopPoint(7,8));assertEquals(listOf(1,1,0),p.map{it.mask});assertEquals(listOf(DesktopPoint(2,3),DesktopPoint(7,8),DesktopPoint(7,8)),p.map{DesktopPoint(it.x,it.y)})}
  @Test fun badButtonRejected(){assertThrows(IllegalArgumentException::class.java){InputLifecycle{}.press(9)}}
}
