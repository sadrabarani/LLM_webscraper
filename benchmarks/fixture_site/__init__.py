from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from benchmarks.fixture_site.server import Handler


def start_fixture_server(host: str = "127.0.0.1", port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bound_port = server.server_address[1]
    return server, f"http://{host}:{bound_port}"
