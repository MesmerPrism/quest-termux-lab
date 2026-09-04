package io.github.mesmerprism.questtermuxlab.spatialdesktop

import android.view.KeyEvent
import android.view.InputDevice
import android.view.MotionEvent
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
    assertTrue(ControllerButtonMapper.isVoiceClickToggle(KeyEvent.KEYCODE_BUTTON_B))
    assertFalse(ControllerButtonMapper.isVoiceClickToggle(KeyEvent.KEYCODE_BUTTON_A))
    assertFalse(ControllerButtonMapper.isVoiceClickToggle(KeyEvent.KEYCODE_BACK))
    assertTrue(ControllerButtonMapper.isWindowVoiceClickToggle(KeyEvent.KEYCODE_BACK))
    assertTrue(ControllerButtonMapper.isWindowVoiceClickToggle(KeyEvent.KEYCODE_BUTTON_B))
    assertFalse(ControllerButtonMapper.isWindowVoiceClickToggle(KeyEvent.KEYCODE_BUTTON_A))
  }

  @Test fun joystickPrimaryButtonMotionMapsButPointerMotionDoesNot() {
    assertTrue(
      ControllerButtonMapper.isSecondaryClickMotion(
        InputDevice.SOURCE_JOYSTICK,
        MotionEvent.ACTION_BUTTON_PRESS,
        MotionEvent.BUTTON_PRIMARY,
        MotionEvent.BUTTON_PRIMARY,
      )
    )
    assertFalse(
      ControllerButtonMapper.isSecondaryClickMotion(
        InputDevice.SOURCE_MOUSE,
        MotionEvent.ACTION_BUTTON_PRESS,
        MotionEvent.BUTTON_PRIMARY,
        MotionEvent.BUTTON_PRIMARY,
      )
    )
    assertTrue(
      ControllerButtonMapper.isVoiceClickToggleMotion(
        InputDevice.SOURCE_JOYSTICK,
        MotionEvent.ACTION_BUTTON_PRESS,
        MotionEvent.BUTTON_SECONDARY,
        MotionEvent.BUTTON_SECONDARY,
      )
    )
    assertFalse(
      ControllerButtonMapper.isVoiceClickToggleMotion(
        InputDevice.SOURCE_MOUSE,
        MotionEvent.ACTION_BUTTON_PRESS,
        MotionEvent.BUTTON_SECONDARY,
        MotionEvent.BUTTON_SECONDARY,
      )
    )
  }

  @Test fun oneShotSecondaryClickArmsConsumesAndCancels() {
    val state = OneShotSecondaryClickState()
    assertTrue(state.toggle())
    assertTrue(state.armed)
    assertTrue(state.consume())
    assertFalse(state.armed)
    assertFalse(state.consume())
    assertTrue(state.toggle())
    assertTrue(state.cancel())
    assertFalse(state.cancel())
  }
}
