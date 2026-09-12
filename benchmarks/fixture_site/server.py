"""Tiny multi-page fixture site with an injected console-error bug."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PAGES = {
    "/": """<!DOCTYPE html>
<html><head><title>Fixture Home</title></head>
<body>
  <h1>Fixture Home</h1>
  <nav>
    <a id="link-about" href="/about">About</a>
    <a id="link-form" href="/form">Form</a>
    <a id="link-buggy" href="/buggy">Buggy Page</a>
  </nav>
  <p>Welcome to the Phase 1 fixture.</p>
</body></html>""",
    "/about": """<!DOCTYPE html>
<html><head><title>About</title></head>
<body>
  <h1>About</h1>
  <p>This is a controlled benchmark-like fixture.</p>
  <a id="link-home" href="/">Home</a>
  <a id="link-form" href="/form">Form</a>
</body></html>""",
    "/form": """<!DOCTYPE html>
<html><head><title>Form</title></head>
<body>
  <h1>Search Form</h1>
  <form action="/results" method="get">
    <label for="q">Query</label>
    <input id="q" name="q" type="text" />
    <button id="submit" type="submit">Search</button>
  </form>
  <a id="link-home" href="/">Home</a>
</body></html>""",
    "/results": """<!DOCTYPE html>
<html><head><title>Results</title></head>
<body>
  <h1>Results</h1>
  <p>No results (fixture).</p>
  <a id="link-home" href="/">Home</a>
</body></html>""",
    "/buggy": """<!DOCTYPE html>
<html><head><title>Buggy</title>
<script>
  console.error("Injected fixture bug: something went wrong");
</script>
</head>
<body>
  <h1>Buggy Page</h1>
  <p>This page intentionally emits a console error.</p>
  <a id="link-home" href="/">Home</a>
</body></html>""",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        body = PAGES.get(path)
        if body is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Fixture site at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
