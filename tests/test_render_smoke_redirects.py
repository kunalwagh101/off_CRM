"""A17/A29: a Render smoke probe must never follow an HTTP redirect.

The local fixture uses only loopback and never touches a customer service.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from scripts.live import remote_render_smoke as smoke


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_render_smoke_request_does_not_follow_redirect(method: str) -> None:
    """An off-host redirect can turn a fake health response into false success."""
    seen: list[tuple[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen.append(("GET", self.path))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/trap")
            else:
                self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def do_POST(self) -> None:
            seen.append(("POST", self.path))
            self.send_response(302)
            self.send_header("Location", "/trap")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        data = b'{"test":true}' if method == "POST" else None
        status, _, _ = smoke._request(
            base, "/redirect", method=method, data=data
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 302
    assert seen == [(method, "/redirect")]
