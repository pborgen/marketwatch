import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            self._send(200, {"status": "ok"})
            return
        self._send(200, {"message": "hello world"})

    def log_message(self, fmt: str, *args: object) -> None:
        if self.path.split("?", 1)[0] == "/health":
            return
        super().log_message(fmt, *args)

    def _send(self, status: int, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
