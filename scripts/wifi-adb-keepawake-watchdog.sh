#!/data/data/com.termux/files/usr/bin/sh
set -eu

# Temporary, operator-visible keep-awake loop for a Quest that already has an
# authorized ADB TCP endpoint. This is not a pairing helper, not a boot service,
# and not an authorization bypass.

ADB_TARGET="${ADB_TARGET:-127.0.0.1:5555}"
INTERVAL_SEC="${INTERVAL_SEC:-20}"
STATE_DIR="${STATE_DIR:-$HOME/quest-lab/watchdogs}"
STOP_FILE="${STOP_FILE:-$STATE_DIR/stop-wifi-adb-keepawake}"
STATE_FILE="${STATE_FILE:-$STATE_DIR/wifi-adb-keepawake.status}"

mkdir -p "$STATE_DIR"
rm -f "$STOP_FILE"

write_status() {
  tmp="$STATE_FILE.tmp"
  {
    printf 'timestamp_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'target=%s\n' "$ADB_TARGET"
    printf 'status=%s\n' "$1"
    shift
    for line in "$@"; do
      printf '%s\n' "$line"
    done
  } > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

while [ ! -e "$STOP_FILE" ]; do
  connect_out="$(adb connect "$ADB_TARGET" 2>&1 || true)"
  id_out="$(adb -s "$ADB_TARGET" shell id 2>&1 || true)"

  case "$id_out" in
    *uid=2000*shell*)
      stay_out="$(adb -s "$ADB_TARGET" shell svc power stayon true 2>&1 || true)"
      wake_out="$(adb -s "$ADB_TARGET" shell input keyevent KEYCODE_WAKEUP 2>&1 || true)"
      power_out="$(adb -s "$ADB_TARGET" shell dumpsys power 2>&1 | grep -E 'mWakefulness|mStayOn' || true)"
      write_status ok "adb_connect=$connect_out" "shell_id=$id_out" "stay_awake=$stay_out" "wake=$wake_out" "$power_out"
      ;;
    *)
      write_status blocked "adb_connect=$connect_out" "shell_id=$id_out"
      ;;
  esac

  sleep "$INTERVAL_SEC"
done

write_status stopped "stop_file=$STOP_FILE"
