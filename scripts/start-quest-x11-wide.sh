#!/data/data/com.termux/files/usr/bin/sh
set -eu

export DISPLAY="${DISPLAY:-:1}"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
QUEST_X11_PACKAGE="${QUEST_X11_PACKAGE:-com.termux.x11}"
QUEST_X11_ACTIVITY="${QUEST_X11_ACTIVITY:-$QUEST_X11_PACKAGE/.MainActivity}"
QUEST_X11_DPI="${QUEST_X11_DPI:-120}"
QUEST_X11_XSTARTUP="${QUEST_X11_XSTARTUP:-dbus-launch --exit-with-session xfce4-session}"
QUEST_X11_ACCESS_ARG="${QUEST_X11_ACCESS_ARG:--ac}"
PREF_SCRIPT="${QUEST_X11_PREF_SCRIPT:-$HOME/quest-termux-lab/scripts/quest-x11-wide-prefs.sh}"

if [ -x "$PREF_SCRIPT" ]; then
  "$PREF_SCRIPT"
else
  sh "$PREF_SCRIPT"
fi

pkill termux-x11 2>/dev/null || true
rm -f "$PREFIX/tmp/.X1-lock" 2>/dev/null || true
rm -f "$PREFIX/tmp/.X11-unix/X1" 2>/dev/null || true

am start -n "$QUEST_X11_ACTIVITY" >/dev/null 2>&1 || true
am broadcast -a com.termux.x11.ACTION_STOP -p "$QUEST_X11_PACKAGE" >/dev/null 2>&1 || true

if [ "$QUEST_X11_PACKAGE" != "com.termux.x11" ]; then
  export TERMUX_X11_OVERRIDE_PACKAGE="$QUEST_X11_PACKAGE"
fi

exec termux-x11 "$DISPLAY" $QUEST_X11_ACCESS_ARG -dpi "$QUEST_X11_DPI" -xstartup "$QUEST_X11_XSTARTUP"
