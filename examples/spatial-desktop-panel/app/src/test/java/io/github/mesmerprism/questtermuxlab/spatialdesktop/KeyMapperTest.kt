package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.view.KeyEvent
import org.junit.Assert.*
import org.junit.Test

class KeyMapperTest {
  @Test fun navigationAndModifiers(){assertEquals(Keysyms.LEFT,AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_DPAD_LEFT));assertEquals(Keysyms.CONTROL_L,AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_CTRL_LEFT));assertEquals(Keysyms.ESCAPE,AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_ESCAPE))}
  @Test fun functions(){assertEquals(0xffbe,AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_F1));assertEquals(0xffc9,AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_F12))}
  @Test fun printableAndRepeatsMapSameKeysym(){assertEquals('A'.code,AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_A,'A'.code));assertEquals(AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_A,'a'.code),AndroidKeyMapper.mapKeyCode(KeyEvent.KEYCODE_A,'a'.code))}
  @Test fun controllerAIsSecondaryClickButKeyboardAAndControllerBRemainDistinct() {
    assertTrue(ControllerButtonMapper.isSecondaryClick(KeyEvent.KEYCODE_BUTTON_A))
    assertFalse(ControllerButtonMapper.isSecondaryClick(KeyEvent.KEYCODE_A))
    assertFalse(ControllerButtonMapper.isSecondaryClick(KeyEvent.KEYCODE_BUTTON_B))
  }
}
