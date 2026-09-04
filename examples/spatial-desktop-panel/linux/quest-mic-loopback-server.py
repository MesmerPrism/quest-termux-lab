#!/data/data/com.termux/files/usr/bin/python
"""Bounded loopback PCM receiver for the Quest microphone PulseAudio source."""

from __future__ import annotations

import argparse
import errno
import os
import selectors
import signal
import socket
import time
from pathlib import Path

LOOPBACK = "127.0.0.1"
DEFAULT_PORT = 5911
MAX_CHUNK = 32 * 1024
SAMPLE_RATE = 48_000
CHANNELS = 1
SAMPLE_BYTES = 2
FRAME_MILLIS = 20
FRAME_BYTES = SAMPLE_RATE * CHANNELS * SAMPLE_BYTES * FRAME_MILLIS // 1000
MAX_BUFFER_BYTES = FRAME_BYTES * 10


def copy_pcm(client: socket.socket, fifo_fd: int) -> int:
    total = 0
    while True:
        chunk = client.recv(MAX_CHUNK)
        if not chunk:
            return total
        view = memoryview(chunk)
        while view:
            written = os.write(fifo_fd, view)
            view = view[written:]
            total += written


def write_frame(fifo_fd: int, buffered: bytearray) -> int:
    """Write one real-time frame, padding with silence and never blocking."""
    take = min(len(buffered), FRAME_BYTES)
    frame = bytes(buffered[:take])
    del buffered[:take]
    if take < FRAME_BYTES:
        frame += bytes(FRAME_BYTES - take)
    try:
        return os.write(fifo_fd, frame)
    except BlockingIOError:
        return 0
    except OSError as error:
        if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
            return 0
        raise


def serve(fifo: Path, ready_file: Path, port: int) -> None:
    # O_RDWR keeps the virtual source present while PulseAudio suspends its
    # reader. O_NONBLOCK prevents an idle source from wedging the TCP receiver.
    fifo_fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((LOOPBACK, port))
        listener.listen(2)
        listener.setblocking(False)
        ready_file.write_text(f"loopback={LOOPBACK}:{port}\n", encoding="ascii")
        selector = selectors.DefaultSelector()
        selector.register(listener, selectors.EVENT_READ)
        client: socket.socket | None = None
        buffered = bytearray()
        next_frame = time.monotonic()
        try:
            while True:
                timeout = max(0.0, next_frame - time.monotonic())
                for key, _mask in selector.select(timeout):
                    if key.fileobj is listener:
                        candidate, address = listener.accept()
                        candidate.setblocking(False)
                        if address[0] != LOOPBACK:
                            candidate.close()
                            continue
                        if client is not None:
                            selector.unregister(client)
                            client.close()
                        client = candidate
                        selector.register(client, selectors.EVENT_READ)
                        buffered.clear()
                    elif client is not None and key.fileobj is client:
                        try:
                            chunk = client.recv(MAX_CHUNK)
                        except BlockingIOError:
                            chunk = None
                        if chunk:
                            buffered.extend(chunk)
                            if len(buffered) > MAX_BUFFER_BYTES:
                                del buffered[: len(buffered) - MAX_BUFFER_BYTES]
                        elif chunk == b"":
                            selector.unregister(client)
                            client.close()
                            client = None
                            buffered.clear()

                now = time.monotonic()
                if now >= next_frame:
                    write_frame(fifo_fd, buffered)
                    next_frame += FRAME_MILLIS / 1000
                    if next_frame < now - FRAME_MILLIS / 1000:
                        next_frame = now + FRAME_MILLIS / 1000
        finally:
            if client is not None:
                selector.unregister(client)
                client.close()
            selector.close()
            ready_file.unlink(missing_ok=True)
            os.close(fifo_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fifo", required=True, type=Path)
    parser.add_argument("--ready-file", required=True, type=Path)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    signal.signal(signal.SIGTERM, lambda _signum, _frame: raise_system_exit())
    serve(args.fifo, args.ready_file, args.port)
    return 0


def raise_system_exit() -> None:
    raise SystemExit(0)


if __name__ == "__main__":
    raise SystemExit(main())
