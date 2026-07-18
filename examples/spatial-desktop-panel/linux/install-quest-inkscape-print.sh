#!/data/data/com.termux/files/usr/bin/bash
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
termux_prefix=${PREFIX:-/data/data/com.termux/files/usr}
termux_home=${HOME:-/data/data/com.termux/files/home}
install_bin="$termux_prefix/local/bin"
desktop_dir="$termux_home/Desktop"

for source_file in \
  "$script_dir/quest-inkscape-print" \
  "$script_dir/quest-inkscape-print.desktop"; do
  [ -f "$source_file" ] || {
    printf 'Missing installer input: %s\n' "$source_file" >&2
    exit 1
  }
done

install -d -m 0755 "$install_bin" "$desktop_dir"
install -m 0755 \
  "$script_dir/quest-inkscape-print" \
  "$install_bin/quest-inkscape-print"
install -m 0755 \
  "$script_dir/quest-inkscape-print.desktop" \
  "$desktop_dir/Export and Print SVG.desktop"

printf 'Installed executable: %s\n' "$install_bin/quest-inkscape-print"
printf 'Installed launcher:   %s\n' "$desktop_dir/Export and Print SVG.desktop"
