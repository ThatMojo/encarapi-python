"""export_to_file() and friends against a local stub HTTP server (real requests session, no API):
generated-at header, streaming to disk before the response has ended, errors, no leftover
files, and the new China lang params.
Run: python -m unittest discover tests"""
import gzip
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from encarapi import ChinaCarAPI, EnCarAPI, EnCarAPIError

ROW = b"1,Hyundai,Grandeur,2022,28900000\n"


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while not cond():
        if time.time() > end:
            raise TimeoutError("timed out waiting for the client to write to disk")
        time.sleep(0.01)


class Stub:
    """Local HTTP server; ``handler(h)`` answers with the BaseHTTPRequestHandler ``h``."""

    def __init__(self, handler):
        self.requests = []
        stub = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                u = urlsplit(self.path)
                stub.requests.append({"path": u.path, "query": parse_qs(u.query), "headers": dict(self.headers)})
                handler(self)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def send_chunk(h, data):
    h.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
    h.wfile.flush()


def end_chunks(h):
    h.wfile.write(b"0\r\n\r\n")
    h.wfile.flush()


class ExportToFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="encarapi-export-")
        for k in ("ENCARAPI_KEY", "CHINACARAPI_KEY"):
            os.environ.pop(k, None)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def stub(self, handler):
        s = Stub(handler)
        self.addCleanup(s.close)
        return s

    def test_korea_streams_before_the_response_ends(self):
        dest = os.path.join(self.dir, "korea.csv")
        head = b"listing_id,manufacturer,model,year,price\n" + ROW * 6000
        tail = ROW * 3000
        seen = {}

        def handler(h):
            h.send_response(200)
            h.send_header("Content-Type", "text/csv; charset=utf-8")
            h.send_header("X-Encarapi-Generated-At", "2026-10-22T08:55:00.000Z")
            h.send_header("Transfer-Encoding", "chunked")
            h.end_headers()
            send_chunk(h, head)
            # Hold the rest back until the client has written at least one 64 KiB chunk to
            # <dest>.part: a client that buffers the whole body would never get there (and
            # time out). Up to one chunk can sit in requests' / the file object's buffers.
            part = dest + ".part"
            wait_for(lambda: os.path.exists(part) and os.path.getsize(part) >= 1 << 16)
            seen["part"] = True
            send_chunk(h, tail)
            end_chunks(h)

        srv = self.stub(handler)
        client = EnCarAPI("kr_key", base_url=srv.url)
        out = client.korea.export_to_file(dest, source="kbc", lang="ru", sell_type=None)
        self.assertTrue(seen.get("part"))
        self.assertEqual(out, {"path": dest, "bytes": len(head) + len(tail), "generated_at": "2026-10-22T08:55:00.000Z"})
        with open(dest, "rb") as fh:
            self.assertEqual(fh.read(), head + tail)
        self.assertFalse(os.path.exists(dest + ".part"))
        req = srv.requests[0]
        self.assertEqual(req["path"], "/api/catalog/export")
        self.assertEqual(req["query"], {"source": ["kbc"], "lang": ["ru"]})
        self.assertEqual(req["headers"]["x-api-key"], "kr_key")
        self.assertEqual(req["headers"]["Accept"], "text/csv")

    def test_korea_compress_writes_decompressed_csv(self):
        dest = os.path.join(self.dir, "korea-gz.csv")
        csv = b"listing_id\n" + ROW * 500
        body = gzip.compress(csv)

        def handler(h):
            h.send_response(200)
            h.send_header("Content-Type", "text/csv")
            h.send_header("Content-Encoding", "gzip")
            h.send_header("Content-Length", str(len(body)))
            h.send_header("X-Encarapi-Generated-At", "2026-10-22T09:00:00.000Z")
            h.end_headers()
            h.wfile.write(body)

        srv = self.stub(handler)
        out = EnCarAPI("kr_key", base_url=srv.url).korea.export_to_file(dest, compress=True)
        self.assertEqual(srv.requests[0]["query"], {"compress": ["true"]})
        self.assertEqual(out["bytes"], len(csv))
        with open(dest, "rb") as fh:
            self.assertEqual(fh.read(), csv)

    def test_korea_trucks_and_equipment(self):
        body = b"listing_id\n1\n"

        def handler(h):
            h.send_response(200)
            h.send_header("Content-Length", str(len(body)))
            h.send_header("X-Encarapi-Generated-At", "2026-10-22T10:00:00.000Z")
            h.end_headers()
            h.wfile.write(body)

        srv = self.stub(handler)
        korea = EnCarAPI("kr_key", base_url=srv.url).korea
        t = korea.export_trucks_to_file(os.path.join(self.dir, "trucks.csv"))
        e = korea.export_equipment_to_file(os.path.join(self.dir, "equipment.csv"), compress=False)
        self.assertEqual([r["path"] for r in srv.requests], ["/api/catalog/trucks/export", "/api/catalog/equipment/export"])
        self.assertEqual(srv.requests[1]["query"], {"compress": ["false"]})
        self.assertEqual(t["generated_at"], "2026-10-22T10:00:00.000Z")
        self.assertEqual(e["bytes"], len(body))

    def test_china_header_and_lang_ru(self):
        dest = os.path.join(self.dir, "china-ru.csv")
        csv = "source,id,make,city\ndongchedi,357018451,Audi,Чжэнчжоу\n".encode()

        def handler(h):
            h.send_response(200)
            h.send_header("Content-Type", "text/csv")
            h.send_header("Content-Length", str(len(csv)))
            h.send_header("x-generated-at", "2026-10-22T07:40:00.000Z")
            h.end_headers()
            h.wfile.write(csv)

        srv = self.stub(handler)
        out = ChinaCarAPI("cn_key", base_url=srv.url).export_to_file(dest, lang="ru")
        self.assertEqual(out, {"path": dest, "bytes": len(csv), "generated_at": "2026-10-22T07:40:00.000Z"})
        self.assertEqual(srv.requests[0]["path"], "/api/catalog/export")
        self.assertEqual(srv.requests[0]["query"], {"lang": ["ru"]})
        self.assertEqual(srv.requests[0]["headers"]["x-api-key"], "cn_key")

    def test_pathlike_and_missing_header(self):
        import pathlib

        def handler(h):
            h.send_response(200)
            h.send_header("Content-Length", "2")
            h.end_headers()
            h.wfile.write(b"a\n")

        srv = self.stub(handler)
        out = ChinaCarAPI("cn_key", base_url=srv.url).export_to_file(pathlib.Path(self.dir) / "nohdr.csv")
        self.assertEqual(out["path"], os.path.join(self.dir, "nohdr.csv"))
        self.assertIsNone(out["generated_at"])

    def test_403_raises_and_leaves_no_file(self):
        dest = os.path.join(self.dir, "denied.csv")
        body = json.dumps({"error": "The full catalog export requires a Business or Scale plan."}).encode()

        def handler(h):
            h.send_response(403)
            h.send_header("Content-Type", "application/json")
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)

        srv = self.stub(handler)
        with self.assertRaises(EnCarAPIError) as ctx:
            ChinaCarAPI("cn_key", base_url=srv.url).export_to_file(dest)
        self.assertEqual(ctx.exception.status, 403)
        self.assertIn("Business or Scale", ctx.exception.body)
        self.assertFalse(os.path.exists(dest))
        self.assertFalse(os.path.exists(dest + ".part"))

    def test_abort_mid_stream_keeps_existing_file(self):
        dest = os.path.join(self.dir, "aborted.csv")
        with open(dest, "w") as fh:
            fh.write("previous export\n")

        def handler(h):
            h.send_response(200)
            h.send_header("Content-Length", "100000")
            h.send_header("x-generated-at", "2026-10-22T07:40:00.000Z")
            h.end_headers()
            h.wfile.write(b"source,id\n" + b"dongchedi,1\n" * 100)
            h.wfile.flush()
            h.close_connection = True

        srv = self.stub(handler)
        with self.assertRaises(Exception):
            ChinaCarAPI("cn_key", base_url=srv.url).export_to_file(dest)
        with open(dest) as fh:
            self.assertEqual(fh.read(), "previous export\n")
        self.assertFalse(os.path.exists(dest + ".part"))

    def test_short_gzip_body_keeps_existing_file(self):
        # Content-Length counts the gzip bytes; urllib3 1.x does not raise on a short body itself.
        dest = os.path.join(self.dir, "korea-short.csv")
        with open(dest, "w") as fh:
            fh.write("previous export\n")
        body = gzip.compress(b"listing_id\n" + os.urandom(1 << 16).hex().encode())

        def handler(h):
            h.send_response(200)
            h.send_header("Content-Encoding", "gzip")
            h.send_header("Content-Length", str(len(body)))
            h.send_header("X-Encarapi-Generated-At", "2026-10-22T09:00:00.000Z")
            h.end_headers()
            h.wfile.write(body[: len(body) // 2])
            h.wfile.flush()
            h.close_connection = True

        srv = self.stub(handler)
        with self.assertRaises(Exception):
            EnCarAPI("kr_key", base_url=srv.url).korea.export_to_file(dest, compress=True)
        with open(dest) as fh:
            self.assertEqual(fh.read(), "previous export\n")
        self.assertFalse(os.path.exists(dest + ".part"))


if __name__ == "__main__":
    unittest.main()
