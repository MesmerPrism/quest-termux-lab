#!/data/data/com.termux/files/usr/bin/sh
set -eu

OUT_DIR="${QUEST_X11_EVIDENCE_DIR:-$HOME/quest-lab/x11-wide}"
RESOLUTION_MODE="${QUEST_X11_RESOLUTION_MODE:-custom}"
RESOLUTION="${QUEST_X11_RESOLUTION:-1920x1080}"
ADJUST_RESOLUTION="${QUEST_X11_ADJUST_RESOLUTION:-false}"
DISPLAY_STRETCH="${QUEST_X11_STRETCH:-true}"
FORCE_ORIENTATION="${QUEST_X11_FORCE_ORIENTATION:-landscape}"
FULLSCREEN="${QUEST_X11_FULLSCREEN:-true}"
SHOW_ADDITIONAL_KBD="${QUEST_X11_SHOW_ADDITIONAL_KBD:-false}"
TOUCH_MODE="${QUEST_X11_TOUCH_MODE:-1}"
POINTER_CAPTURE="${QUEST_X11_POINTER_CAPTURE:-false}"

mkdir -p "$OUT_DIR"
: > "$OUT_DIR/prefs.set.txt"

termux-x11-preference list > "$OUT_DIR/prefs.before.txt" 2>&1 || true

set_pref() {
  key="$1"
  value="$2"

  if termux-x11-preference "$key:$value" >> "$OUT_DIR/prefs.set.txt" 2>&1; then
    printf '%s=%s\n' "$key" "$value" >> "$OUT_DIR/prefs.selected.txt"
    return 0
  fi

  printf 'colon_syntax_failed %s=%s\n' "$key" "$value" >> "$OUT_DIR/prefs.set.txt"
  if termux-x11-preference "$key=$value" >> "$OUT_DIR/prefs.set.txt" 2>&1; then
    printf '%s=%s\n' "$key" "$value" >> "$OUT_DIR/prefs.selected.txt"
    return 0
  fi

  printf 'preference_set_failed %s=%s\n' "$key" "$value" >> "$OUT_DIR/prefs.set.txt"
  return 0
}

case "$RESOLUTION_MODE" in
  exact)
    RESOLUTION_KEY="displayResolutionExact"
    ;;
  custom)
    RESOLUTION_KEY="displayResolutionCustom"
    ;;
  native|scaled)
    RESOLUTION_KEY=""
    ;;
  *)
    echo "unsupported QUEST_X11_RESOLUTION_MODE=$RESOLUTION_MODE" >&2
    exit 2
    ;;
esac

rm -f "$OUT_DIR/prefs.selected.txt"
set_pref displayResolutionMode "$RESOLUTION_MODE"
if [ -n "$RESOLUTION_KEY" ]; then
  set_pref "$RESOLUTION_KEY" "$RESOLUTION"
fi
set_pref adjustResolution "$ADJUST_RESOLUTION"
set_pref displayStretch "$DISPLAY_STRETCH"
set_pref forceOrientation "$FORCE_ORIENTATION"
set_pref fullscreen "$FULLSCREEN"
set_pref showAdditionalKbd "$SHOW_ADDITIONAL_KBD"
set_pref touchMode "$TOUCH_MODE"
set_pref pointerCapture "$POINTER_CAPTURE"

termux-x11-preference list > "$OUT_DIR/prefs.after.txt" 2>&1 || true

printf 'wrote %s\n' "$OUT_DIR"
