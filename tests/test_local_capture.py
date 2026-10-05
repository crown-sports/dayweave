"""Behavioral checks for local capture routing, invalid model text, and redirect confinement."""

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

from dayweave.capture import capture_note, deadline_time
from dayweave.contracts import local_time


@contextmanager
def provider(raw, redirect=False):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            if redirect:
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/should-not-receive-notes")
                self.end_headers()
            else:
                payload = json.dumps({"message": {"content": raw}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_invalid_model_text_is_preserved_with_visible_offline_fallback():
    with provider("not valid JSON") as endpoint:
        result = capture_note("读书30分钟，周三18:00前", "2026-10-05T09:00", endpoint=endpoint)
    assert result["provider"] == "offline" and result["rejection"]
    assert result["model_output"] == "not valid JSON"
    assert result["items"][0]["duration"] == 30


def test_local_model_redirect_is_rejected_and_note_stays_on_configured_endpoint():
    with provider("", redirect=True) as endpoint:
        result = capture_note("读书30分钟", "2026-10-05T09:00", endpoint=endpoint)
    assert result["provider"] == "offline" and "redirect" in result["rejection"]


def test_structured_lines_use_deterministic_capture_even_with_an_unavailable_model():
    result = capture_note("读书 | 30分钟 | 周三18:00前", "2026-10-05T09:00", endpoint="http://127.0.0.1:1")
    assert result["provider"] == "offline" and result["rejection"] is None
    assert result["items"][0]["deadline"] == "2026-10-07T18:00+08:00"


def test_explicit_before_suffix_is_interpreted_without_inventing_time():
    zone = ZoneInfo("Asia/Shanghai")
    anchor = local_time("2026-10-05T09:00", zone).astimezone(zone)
    assert deadline_time("周三18:00之前", anchor, zone) == "2026-10-07T18:00+08:00"
    assert deadline_time("周三前", anchor, zone) is None
