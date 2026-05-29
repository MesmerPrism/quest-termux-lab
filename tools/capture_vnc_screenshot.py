#!/usr/bin/env python3
"""Capture one raw-encoding VNC framebuffer as a PNG.

This helper is intentionally narrow. It supports the no-auth localhost test
path used by the lab recipes and does not implement keyboard, pointer, or
remote-control behavior.
"""

from __future__ import annotations

import argparse
import socket
import struct
import sys
from pathlib import Path


def read_exact(sock: socket.socket, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError(f"connection closed while reading {count} bytes")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def capture(host: str, port: int, output: Path, timeout: float) -> tuple[int, int]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required: python -m pip install Pillow") from exc

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)

        server_version = read_exact(sock, 12)
        if not server_version.startswith(b"RFB "):
            raise RuntimeError(f"unexpected VNC version header: {server_version!r}")
        sock.sendall(b"RFB 003.008\n")

        security_count = read_exact(sock, 1)[0]
        if security_count == 0:
            reason_len = struct.unpack(">I", read_exact(sock, 4))[0]
            reason = read_exact(sock, reason_len).decode("utf-8", errors="replace")
            raise RuntimeError(f"server rejected connection: {reason}")

        security_types = read_exact(sock, security_count)
        if 1 not in security_types:
            raise RuntimeError(f"server does not offer no-auth security: {list(security_types)}")
        sock.sendall(b"\x01")

        security_result = struct.unpack(">I", read_exact(sock, 4))[0]
        if security_result != 0:
            raise RuntimeError(f"security negotiation failed: {security_result}")

        sock.sendall(b"\x01")
        width, height = struct.unpack(">HH", read_exact(sock, 4))
        _server_pixel_format = read_exact(sock, 16)
        name_len = struct.unpack(">I", read_exact(sock, 4))[0]
        _name = read_exact(sock, name_len)

        # Request a narrow client-side format instead of trusting each VNC
        # server's default. Some x11vnc builds report true_color as 255.
        pixel_format = struct.pack(
            ">BBBBHHHBBBxxx",
            32,
            24,
            0,
            1,
            255,
            255,
            255,
            16,
            8,
            0,
        )
        sock.sendall(b"\x00\x00\x00\x00" + pixel_format)
        sock.sendall(struct.pack(">BBH", 2, 0, 1) + struct.pack(">i", 0))
        sock.sendall(struct.pack(">B?HHHH", 3, False, 0, 0, width, height))

        message_type = read_exact(sock, 1)[0]
        if message_type != 0:
            raise RuntimeError(f"unexpected VNC server message type: {message_type}")
        _padding = read_exact(sock, 1)
        rect_count = struct.unpack(">H", read_exact(sock, 2))[0]
        if rect_count < 1:
            raise RuntimeError("server returned no rectangles")

        framebuffer = bytearray(width * height * 4)
        for _ in range(rect_count):
            x, y, rect_w, rect_h, encoding = struct.unpack(">HHHHi", read_exact(sock, 12))
            if encoding != 0:
                raise RuntimeError(f"unsupported VNC encoding: {encoding}")
            rect = read_exact(sock, rect_w * rect_h * 4)
            for row in range(rect_h):
                src_start = row * rect_w * 4
                src_end = src_start + rect_w * 4
                dst_start = ((y + row) * width + x) * 4
                framebuffer[dst_start : dst_start + rect_w * 4] = rect[src_start:src_end]

    rgba = bytearray(width * height * 4)
    for index in range(0, len(framebuffer), 4):
        blue = framebuffer[index]
        green = framebuffer[index + 1]
        red = framebuffer[index + 2]
        rgba[index] = red
        rgba[index + 1] = green
        rgba[index + 2] = blue
        rgba[index + 3] = 255

    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.frombytes("RGBA", (width, height), bytes(rgba))
    if output.suffix.lower() in {".jpg", ".jpeg"}:
        image = image.convert("RGB")
    image.save(output)
    return width, height


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    try:
        width, height = capture(args.host, args.port, args.output, args.timeout)
    except Exception as exc:
        print(f"vnc_capture_failed: {exc}", file=sys.stderr)
        return 1

    print(f"vnc_capture_ok {width}x{height} {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
