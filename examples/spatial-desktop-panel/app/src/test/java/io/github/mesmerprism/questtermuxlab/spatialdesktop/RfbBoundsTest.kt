package io.github.mesmerprism.questtermuxlab.spatialdesktop

import java.io.ByteArrayInputStream
import java.io.DataInputStream
import java.io.IOException
import org.junit.Assert.*
import org.junit.Test

class RfbBoundsTest {
  @Test fun dimensionsAreBounded(){validateDimensions(1280,720);assertThrows(IOException::class.java){validateDimensions(5000,720)};assertThrows(IOException::class.java){validateDimensions(4096,4096)}}
  @Test fun malformedRectanglesRejected(){assertThrows(IOException::class.java){validateRect(-1,0,1,1,1280,720)};assertThrows(IOException::class.java){validateRect(1279,719,2,2,1280,720)};assertThrows(IOException::class.java){validateRect(0,0,0,2,1280,720)}}
  @Test fun rawDecodesBgrx(){val f=RetainedFramebuffer();f.resize(1,1);f.rawRect(0,0,1,1,DataInputStream(ByteArrayInputStream(byteArrayOf(3,2,1,0))));assertEquals(0xff010203.toInt(),f.snapshot()[0]);assertEquals(2,f.generation)}
  @Test fun bulkRawDecodeProducesBoundedImmutablePatch(){val f=RetainedFramebuffer();f.resize(2,1);val patch=f.rawRect(0,0,2,1,DataInputStream(ByteArrayInputStream(byteArrayOf(3,2,1,0,6,5,4,0))));assertArrayEquals(intArrayOf(0xff010203.toInt(),0xff040506.toInt()),patch.pixels);assertEquals(8,patch.wireBytes);assertEquals(2,f.generation)}
  @Test fun rgb565DecodesLittleEndianAndExpandsChannels(){val f=RetainedFramebuffer();f.resize(3,1);val patch=f.rawRect(0,0,3,1,DataInputStream(ByteArrayInputStream(byteArrayOf(0x00,0xf8.toByte(),0xe0.toByte(),0x07,0x1f,0x00))),RfbPixelFormat.RGB565);assertArrayEquals(intArrayOf(0xffff0000.toInt(),0xff00ff00.toInt(),0xff0000ff.toInt()),patch.pixels);assertEquals(6,patch.wireBytes)}
  @Test fun copyRectIsOverlapSafe(){val f=RetainedFramebuffer();f.resize(4,1);f.rawRect(0,0,4,1,DataInputStream(ByteArrayInputStream(byteArrayOf(1,0,0,0,2,0,0,0,3,0,0,0,4,0,0,0))));val patch=f.copyRect(1,0,3,1,0,0);assertArrayEquals(intArrayOf(0xff000001.toInt(),0xff000002.toInt(),0xff000003.toInt()),patch.pixels);assertArrayEquals(intArrayOf(0xff000001.toInt(),0xff000001.toInt(),0xff000002.toInt(),0xff000003.toInt()),f.snapshot())}
  @Test fun loopbackEnforcedBeforeConnection(){val c=RfbClient(object:RfbListener{override fun onFramebuffer(frame:DecodedFrame,stats:RfbStats){};override fun onStatus(status:String,stats:RfbStats){}});assertThrows(IllegalArgumentException::class.java){c.connect("192.0.2.1",5900)}}
  @Test fun reconnectAndDisconnectAreSafe(){val statuses=mutableListOf<String>();val c=RfbClient(object:RfbListener{override fun onFramebuffer(frame:DecodedFrame,stats:RfbStats){};override fun onStatus(status:String,stats:RfbStats){statuses+=status}});c.disconnect();c.connect("127.0.0.1",1);Thread.sleep(100);c.disconnect();assertEquals(1,c.stats.reconnects)}
}
