#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d -m 755 "$PREFIX/local/bin" "$PREFIX/local/libexec"
install -m 755 "$script_dir/quest-mic-pulse-bridge" "$PREFIX/local/bin/quest-mic-pulse-bridge"
install -m 755 "$script_dir/quest-mic-loopback-server.py" "$PREFIX/local/libexec/quest-mic-loopback-server.py"
pkg install -y pulseaudio python
printf 'Installed Quest microphone bridge.\n'
