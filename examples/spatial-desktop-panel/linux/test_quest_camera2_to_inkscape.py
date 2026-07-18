import contextlib
import importlib.machinery
import importlib.util
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from PIL import Image


SCRIPT = Path(__file__).with_name("quest-camera2-to-inkscape")
loader = importlib.machinery.SourceFileLoader("quest_camera2_to_inkscape", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


def jpeg_fixture() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (12, 8), (32, 96, 160)).save(stream, format="JPEG", quality=90)
    return stream.getvalue()


class SnapshotHandler(BaseHTTPRequestHandler):
    payload = jpeg_fixture()
    bearer_value = "a" * 64

    def do_GET(self):
        if self.path != "/snapshot.jpg" or self.headers.get("Authorization") != f"Bearer {self.bearer_value}":
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        pass


@contextlib.contextmanager
def snapshot_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SnapshotHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/snapshot.jpg"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class CameraToInkscapeTest(unittest.TestCase):
    def test_rejects_non_loopback_and_credentialed_urls(self):
        for value in (
            "http://example.invalid:9000/snapshot.jpg",
            "http://127.0.0.1:9000/other.jpg",
            "http://user@127.0.0.1:9000/snapshot.jpg",
            "https://127.0.0.1:9000/snapshot.jpg",
        ):
            with self.assertRaises(module.CameraImportError):
                module.validate_snapshot_url(value)

    def test_authenticated_download_and_embedded_svg(self):
        with snapshot_server() as url, tempfile.TemporaryDirectory() as temporary:
            payload = module.download_snapshot(url, SnapshotHandler.bearer_value)
            jpeg_path, svg_path, width, height = module.save_import(Path(temporary), "50", payload)
            self.assertEqual((width, height), (12, 8))
            self.assertEqual(jpeg_path.read_bytes(), payload)
            svg = svg_path.read_text(encoding="utf-8")
            self.assertIn('href="data:image/jpeg;base64,', svg)
            self.assertIn("camera_id=50", svg)
            self.assertNotIn(url, svg)
            self.assertNotIn(SnapshotHandler.bearer_value, svg)

    def test_wrong_token_is_not_disclosed(self):
        wrong = "b" * 64
        with snapshot_server() as url:
            with self.assertRaises(module.CameraImportError) as raised:
                module.download_snapshot(url, wrong)
        self.assertNotIn(wrong, str(raised.exception))
        self.assertNotIn(url, str(raised.exception))

    def test_rejects_non_jpeg_payload(self):
        with self.assertRaises(module.CameraImportError):
            module.verify_jpeg(b"not a jpeg")


if __name__ == "__main__":
    unittest.main()
