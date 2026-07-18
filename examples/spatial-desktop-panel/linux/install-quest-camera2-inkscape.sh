#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
INSTALL_DIR="$PREFIX/local/bin"

install -d -m 0755 "$INSTALL_DIR"
install -m 0755 "$SCRIPT_DIR/quest-camera2-to-inkscape" "$INSTALL_DIR/quest-camera2-to-inkscape"

printf 'Installed %s\n' "$INSTALL_DIR/quest-camera2-to-inkscape"
