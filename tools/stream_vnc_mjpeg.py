#!/usr/bin/env python3
"""Expose a no-auth localhost VNC display as a local MJPEG browser stream.

This is intentionally narrow lab tooling. It is meant for a VNC server that is
already bound to device localhost and reached through an explicit ADB forward.
It is not a general VNC client and does not implement keyboard or pointer
control.
"""

from __future__ import annotations

import argparse
import io
import json
import socket
import struct
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


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


def choose_none_security(sock: socket.socket, version: bytes) -> None:
    if version.startswith(b"RFB 003.003"):
        security_type = struct.unpack(">I", read_exact(sock, 4))[0]
        if security_type != 1:
            raise RuntimeError(f"expected no-auth security type 1, got {security_type}")
        return

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


class RfbRawClient:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.width = 0
        self.height = 0
        self._image: Any | None = None

    def connect(self) -> None:
        try:
            from PIL import Image  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("Pillow is required: python -m pip install Pillow") from exc

        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        version = read_exact(sock, 12)
        if not version.startswith(b"RFB "):
            raise RuntimeError(f"unexpected VNC version header: {version!r}")
        sock.sendall(b"RFB 003.008\n")
        choose_none_security(sock, version)
        sock.sendall(b"\x01")  # ClientInit: shared.

        self.width, self.height = struct.unpack(">HH", read_exact(sock, 4))
        _server_pixel_format = read_exact(sock, 16)
        name_len = struct.unpack(">I", read_exact(sock, 4))[0]
        _name = read_exact(sock, name_len)

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

        from PIL import Image

        self.sock = sock
        self._image = Image.new("RGB", (self.width, self.height))

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def capture_jpeg(self, quality: int) -> bytes:
        if self.sock is None or self._image is None:
            raise RuntimeError("RFB client is not connected")

        self.sock.sendall(struct.pack(">BBHHHH", 3, 0, 0, 0, self.width, self.height))
        while True:
            message_type = read_exact(self.sock, 1)[0]
            if message_type == 0:
                break
            if message_type == 2:
                continue
            if message_type == 3:
                read_exact(self.sock, 3)
                text_len = struct.unpack(">I", read_exact(self.sock, 4))[0]
                read_exact(self.sock, text_len)
                continue
            raise RuntimeError(f"unsupported VNC server message type: {message_type}")

        read_exact(self.sock, 1)
        rect_count = struct.unpack(">H", read_exact(self.sock, 2))[0]

        from PIL import Image

        for _ in range(rect_count):
            x, y, rect_width, rect_height, encoding = struct.unpack(">HHHHi", read_exact(self.sock, 12))
            if encoding != 0:
                raise RuntimeError(f"unsupported VNC encoding: {encoding}")
            raw = read_exact(self.sock, rect_width * rect_height * 4)
            rect_image = Image.frombuffer("RGBA", (rect_width, rect_height), raw, "raw", "BGRA", 0, 1)
            self._image.paste(rect_image.convert("RGB"), (x, y))

        output = io.BytesIO()
        self._image.save(output, format="JPEG", quality=quality, optimize=False)
        return output.getvalue()


class VncFramePump(threading.Thread):
    def __init__(
        self,
        vnc_host: str,
        vnc_port: int,
        fps: float,
        jpeg_quality: int,
        timeout: float,
        reconnect_delay: float,
    ) -> None:
        super().__init__(daemon=True)
        self.vnc_host = vnc_host
        self.vnc_port = vnc_port
        self.fps = max(0.1, fps)
        self.jpeg_quality = jpeg_quality
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self.started_at = time.time()
        self.condition = threading.Condition()
        self.latest_jpeg: bytes | None = None
        self.frame_counter = 0
        self.last_frame_at: float | None = None
        self.last_error: str | None = None
        self.width = 0
        self.height = 0
        self.connected = False
        self.stop_event = threading.Event()

    def run(self) -> None:
        delay = 1.0 / self.fps
        while not self.stop_event.is_set():
            client = RfbRawClient(self.vnc_host, self.vnc_port, self.timeout)
            try:
                client.connect()
                with self.condition:
                    self.connected = True
                    self.width = client.width
                    self.height = client.height
                    self.last_error = None
                    self.condition.notify_all()
                while not self.stop_event.is_set():
                    start = time.time()
                    jpeg = client.capture_jpeg(self.jpeg_quality)
                    with self.condition:
                        self.latest_jpeg = jpeg
                        self.frame_counter += 1
                        self.last_frame_at = time.time()
                        self.condition.notify_all()
                    elapsed = time.time() - start
                    if elapsed < delay:
                        self.stop_event.wait(delay - elapsed)
            except Exception as exc:  # noqa: BLE001 - status endpoint reports exact lab failure.
                with self.condition:
                    self.connected = False
                    self.last_error = str(exc)
                    self.condition.notify_all()
                self.stop_event.wait(self.reconnect_delay)
            finally:
                client.close()
                with self.condition:
                    self.connected = False
                    self.condition.notify_all()

    def snapshot_status(self) -> dict[str, Any]:
        now = time.time()
        age = None if self.last_frame_at is None else now - self.last_frame_at
        elapsed = max(0.001, now - self.started_at)
        with self.condition:
            return {
                "connected": self.connected,
                "width": self.width,
                "height": self.height,
                "frames": self.frame_counter,
                "configured_fps": self.fps,
                "average_fps": self.frame_counter / elapsed,
                "last_frame_age_seconds": age,
                "last_error": self.last_error,
                "vnc_host": self.vnc_host,
                "vnc_port": self.vnc_port,
            }


def make_handler(pump: VncFramePump) -> type[BaseHTTPRequestHandler]:
    class StreamHandler(BaseHTTPRequestHandler):
        server_version = "QuestTermuxVncStream/0.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature.
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook.
            if self.path in ("/", "/index.html"):
                self._send_index()
            elif self.path == "/status.json":
                self._send_json(pump.snapshot_status())
            elif self.path == "/frame.jpg":
                self._send_frame()
            elif self.path == "/stream.mjpg":
                self._send_stream()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def _send_index(self) -> None:
            body = b"""<!doctype html>
<meta charset="utf-8">
<title>Quest Termux VNC Stream</title>
<style>
body{margin:0;background:#111;color:#eee;font:14px system-ui,Segoe UI,sans-serif}
header{display:flex;gap:16px;align-items:center;padding:10px 14px;background:#20242a}
img{display:block;max-width:100vw;max-height:calc(100vh - 46px);margin:0 auto;background:#000}
code{color:#9ee}
</style>
<header><strong>Quest Termux VNC Stream</strong><span id="status">connecting...</span></header>
<img src="/stream.mjpg" alt="VNC stream">
<script>
async function tick(){
  try{
    const s=await fetch('/status.json',{cache:'no-store'}).then(r=>r.json());
    document.getElementById('status').innerHTML =
      `${s.connected?'connected':'disconnected'} | ${s.width}x${s.height} | frames ${s.frames} | avg ${s.average_fps.toFixed(2)} fps | age ${s.last_frame_age_seconds?.toFixed(2) ?? 'n/a'}s | ${s.last_error ?? ''}`;
  }catch(e){document.getElementById('status').textContent='status error: '+e}
}
setInterval(tick,1000); tick();
</script>
"""
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, value: dict[str, Any]) -> None:
            body = json.dumps(value, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_frame(self) -> None:
            with pump.condition:
                if pump.latest_jpeg is None:
                    pump.condition.wait(timeout=5.0)
                frame = pump.latest_jpeg
            if frame is None:
                self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "no VNC frame available yet")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(frame)))
            self.end_headers()
            self.wfile.write(frame)

        def _send_stream(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            last_counter = -1
            while True:
                with pump.condition:
                    pump.condition.wait_for(lambda: pump.frame_counter != last_counter or pump.stop_event.is_set(), timeout=5.0)
                    if pump.stop_event.is_set():
                        return
                    frame = pump.latest_jpeg
                    last_counter = pump.frame_counter
                if frame is None:
                    continue
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

    return StreamHandler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vnc-host", default="127.0.0.1")
    parser.add_argument("--vnc-port", type=int, required=True)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=18080)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    parser.add_argument("--pid-file", type=Path)
    args = parser.parse_args()

    if not 1 <= args.jpeg_quality <= 95:
        raise SystemExit("--jpeg-quality must be between 1 and 95")

    pump = VncFramePump(
        vnc_host=args.vnc_host,
        vnc_port=args.vnc_port,
        fps=args.fps,
        jpeg_quality=args.jpeg_quality,
        timeout=args.timeout,
        reconnect_delay=args.reconnect_delay,
    )
    pump.start()

    if args.pid_file:
        args.pid_file.parent.mkdir(parents=True, exist_ok=True)
        args.pid_file.write_text(str(__import__("os").getpid()), encoding="utf-8")

    server = ThreadingHTTPServer((args.listen_host, args.listen_port), make_handler(pump))
    print(f"vnc_mjpeg_stream_ready http://{args.listen_host}:{args.listen_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        pump.stop_event.set()
        with pump.condition:
            pump.condition.notify_all()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
