import array
import importlib.util
import pathlib
import socket
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("quest-mic-loopback-server.py")
SPEC = importlib.util.spec_from_file_location("quest_mic_loopback_server", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class QuestMicLoopbackServerTest(unittest.TestCase):
    def test_copy_pcm_preserves_bytes(self):
        left, right = socket.socketpair()
        read_fd, write_fd = __import__("os").pipe()
        try:
            payload = array.array("h", [-32768, -1, 0, 1, 32767]).tobytes()
            left.sendall(payload)
            left.shutdown(socket.SHUT_WR)
            self.assertEqual(len(payload), MODULE.copy_pcm(right, write_fd))
            __import__("os").close(write_fd)
            write_fd = -1
            self.assertEqual(payload, __import__("os").read(read_fd, len(payload)))
        finally:
            left.close()
            right.close()
            __import__("os").close(read_fd)
            if write_fd >= 0:
                __import__("os").close(write_fd)

    def test_listener_is_hard_coded_to_ipv4_loopback(self):
        self.assertEqual("127.0.0.1", MODULE.LOOPBACK)
        self.assertEqual(5911, MODULE.DEFAULT_PORT)
        self.assertLessEqual(MODULE.MAX_CHUNK, 32 * 1024)

    def test_idle_frame_is_silence(self):
        read_fd, write_fd = __import__("os").pipe()
        try:
            buffered = bytearray()
            self.assertEqual(MODULE.FRAME_BYTES, MODULE.write_frame(write_fd, buffered))
            self.assertEqual(bytes(MODULE.FRAME_BYTES), __import__("os").read(read_fd, MODULE.FRAME_BYTES))
        finally:
            __import__("os").close(read_fd)
            __import__("os").close(write_fd)

    def test_live_audio_is_padded_to_one_frame(self):
        read_fd, write_fd = __import__("os").pipe()
        try:
            payload = b"\x01\x02" * 16
            buffered = bytearray(payload)
            MODULE.write_frame(write_fd, buffered)
            frame = __import__("os").read(read_fd, MODULE.FRAME_BYTES)
            self.assertEqual(payload, frame[: len(payload)])
            self.assertEqual(bytes(MODULE.FRAME_BYTES - len(payload)), frame[len(payload) :])
            self.assertEqual(bytearray(), buffered)
        finally:
            __import__("os").close(read_fd)
            __import__("os").close(write_fd)

    def test_frame_size_matches_20ms_mono_pcm16(self):
        self.assertEqual(1920, MODULE.FRAME_BYTES)
        self.assertEqual(MODULE.FRAME_BYTES * 10, MODULE.MAX_BUFFER_BYTES)


if __name__ == "__main__":
    unittest.main()
