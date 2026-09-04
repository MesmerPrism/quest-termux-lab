package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.view.KeyEvent

data class PointerPacket(val mask: Int, val x: Int, val y: Int)

class InputLifecycle(private val send: (PointerPacket) -> Unit) {
  var mask = 0; private set
  var last = DesktopPoint(0, 0); private set
  var sequence = 0L; private set
  var forcedReleases = 0L; private set
  fun move(p: DesktopPoint) { last=p; emit() }
  fun press(button: Int, p: DesktopPoint = last) { last=p; mask = mask or bit(button); emit() }
  fun release(button: Int, p: DesktopPoint = last) { last=p; mask = mask and bit(button).inv(); emit() }
  fun click(button: Int, p: DesktopPoint = last) { press(button,p); release(button,p) }
  fun drag(start: DesktopPoint, end: DesktopPoint) { press(1,start); move(end); release(1,end) }
  fun scroll(verticalSteps: Int, p: DesktopPoint = last) { val button=if(verticalSteps<0) 4 else 5; repeat(kotlin.math.abs(verticalSteps).coerceAtMost(16)){ click(button,p) } }
  fun cancel() = forceRelease()
  fun forceRelease() { if(mask != 0) { mask=0; forcedReleases++; emit() } }
  private fun emit() { sequence++; send(PointerPacket(mask,last.x,last.y)) }
  private fun bit(button: Int)=when(button){1->1;2->2;3->4;4->8;5->16;else->throw IllegalArgumentException("button")}
}

object Keysyms {
  const val BACKSPACE=0xff08; const val TAB=0xff09; const val RETURN=0xff0d; const val ESCAPE=0xff1b; const val DELETE=0xffff
  const val HOME=0xff50; const val LEFT=0xff51; const val UP=0xff52; const val RIGHT=0xff53; const val DOWN=0xff54; const val PAGE_UP=0xff55; const val PAGE_DOWN=0xff56; const val END=0xff57; const val INSERT=0xff63
  const val SHIFT_L=0xffe1; const val SHIFT_R=0xffe2; const val CONTROL_L=0xffe3; const val CONTROL_R=0xffe4; const val ALT_L=0xffe9; const val ALT_R=0xffea; const val SUPER_L=0xffeb; const val SUPER_R=0xffec
}

object AndroidKeyMapper {
  fun map(event: KeyEvent): Int? = mapKeyCode(event.keyCode, event.unicodeChar)
  fun mapKeyCode(keyCode: Int, unicode: Int = 0): Int? {
    if (unicode in 0x20..0x7e) return unicode
    return when(keyCode) {
      KeyEvent.KEYCODE_DEL->Keysyms.BACKSPACE; KeyEvent.KEYCODE_TAB->Keysyms.TAB; KeyEvent.KEYCODE_ENTER,KeyEvent.KEYCODE_NUMPAD_ENTER->Keysyms.RETURN; KeyEvent.KEYCODE_ESCAPE->Keysyms.ESCAPE; KeyEvent.KEYCODE_FORWARD_DEL->Keysyms.DELETE
      KeyEvent.KEYCODE_MOVE_HOME->Keysyms.HOME; KeyEvent.KEYCODE_DPAD_LEFT->Keysyms.LEFT; KeyEvent.KEYCODE_DPAD_UP->Keysyms.UP; KeyEvent.KEYCODE_DPAD_RIGHT->Keysyms.RIGHT; KeyEvent.KEYCODE_DPAD_DOWN->Keysyms.DOWN; KeyEvent.KEYCODE_PAGE_UP->Keysyms.PAGE_UP; KeyEvent.KEYCODE_PAGE_DOWN->Keysyms.PAGE_DOWN; KeyEvent.KEYCODE_MOVE_END->Keysyms.END; KeyEvent.KEYCODE_INSERT->Keysyms.INSERT
      KeyEvent.KEYCODE_SHIFT_LEFT->Keysyms.SHIFT_L; KeyEvent.KEYCODE_SHIFT_RIGHT->Keysyms.SHIFT_R; KeyEvent.KEYCODE_CTRL_LEFT->Keysyms.CONTROL_L; KeyEvent.KEYCODE_CTRL_RIGHT->Keysyms.CONTROL_R; KeyEvent.KEYCODE_ALT_LEFT->Keysyms.ALT_L; KeyEvent.KEYCODE_ALT_RIGHT->Keysyms.ALT_R; KeyEvent.KEYCODE_META_LEFT->Keysyms.SUPER_L; KeyEvent.KEYCODE_META_RIGHT->Keysyms.SUPER_R
      in KeyEvent.KEYCODE_F1..KeyEvent.KEYCODE_F12 -> 0xffbe + keyCode-KeyEvent.KEYCODE_F1
      else->null
    }
  }
}

object ControllerButtonMapper {
  fun isSecondaryClick(keyCode: Int): Boolean = keyCode == KeyEvent.KEYCODE_BUTTON_A
}
