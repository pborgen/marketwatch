"""Monitor for the Market Watch agents.

The page is locked with one shared password. When ``MONITOR_PASSWORD`` is
unset, the password is ``demo``. After signing in you can see whether each
agent is up and send it a command.

The pages are the React app in ``apps/web``. Build it once, then run the API:

    npm --prefix apps/web install
    npm --prefix apps/web run build
    .venv/bin/python apps/api/main.py

Then open http://127.0.0.1:8000/
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from agents import Catalog
from auth import clear_cookie, password_matches, session_ok, set_cookie

CATALOG = Catalog()
_SOURCE = Path(__file__).resolve().parents[1] / "web"
_BUILT = _SOURCE / "dist"
_WEB = Path(os.environ["WEB_DIR"]) if os.environ.get("WEB_DIR") else (_BUILT if (_BUILT / "index.html").is_file() else _SOURCE)
_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".map": "application/json",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}
_LOGIN_ERROR = "That password is not the demo password."


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    catalog = CATALOG

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._json(200, {"status": "ok"})
            return
        if path == "/api/agents":
            if not session_ok(self.headers):
                self._json(401, {"error": "Sign in."})
                return
            self._json(200, {"agents": self.catalog.list_status()})
            return
        if path == "/login" and session_ok(self.headers):
            self._redirect("/")
            return
        if path.startswith("/api/"):
            self._json(404, {"error": "Not found."})
            return
        self._serve(path)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/login":
            self._login()
            return
        if path == "/logout":
            self._redirect("/", clear_cookie(_secure(self.headers)))
            return
        if path.startswith("/api/agents/") and path.endswith("/commands"):
            self._command(path)
            return
        self._json(404, {"error": "Not found."})

    def log_message(self, fmt: str, *args: object) -> None:
        if self.path.split("?", 1)[0] == "/health":
            return
        super().log_message(fmt, *args)

    def _login(self) -> None:
        password, as_json = self._password()
        if not password_matches(password):
            self._json(401, {"error": _LOGIN_ERROR})
            return
        cookie = set_cookie(_secure(self.headers))
        if as_json:
            self.send_response(204)
            self.send_header("Set-Cookie", cookie)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._redirect("/", cookie)

    def _password(self) -> tuple[str, bool]:
        raw = self._body()
        if "application/json" in self.headers.get("Content-Type", ""):
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return "", True
            password = payload.get("password") if isinstance(payload, dict) else ""
            return password if isinstance(password, str) else "", True
        return _form(raw).get("password", ""), False

    def _serve(self, url_path: str) -> None:
        root = _WEB.resolve()
        index = root / "index.html"
        relative = url_path.lstrip("/")
        if not relative:
            self._file(index)
            return
        candidate = (root / relative).resolve()
        if (candidate == root or root in candidate.parents) and candidate.is_file():
            self._file(candidate)
            return
        if "." not in Path(relative).name:
            self._file(index)
            return
        self._json(404, {"error": "Not found."})

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self._json(500, {"error": "The monitor build is missing."})
            return
        media = _TYPES.get(path.suffix, "application/octet-stream")
        self._bytes(200, path.read_bytes(), media)

    def _command(self, path: str) -> None:
        if not session_ok(self.headers):
            self._json(401, {"error": "Sign in."})
            return
        agent_id = path.removeprefix("/api/agents/").removesuffix("/commands").strip("/")
        if "/" in agent_id or not agent_id:
            self._json(404, {"error": "Unknown agent."})
            return
        try:
            payload = json.loads(self._body().decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Send a JSON command."})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "Send a JSON command."})
            return
        prompt = payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""
        reset = payload.get("reset") is True
        result = self.catalog.command(agent_id, prompt, reset=reset)
        status = int(result.pop("status", 200 if result.get("ok") else 502))
        self._json(status, result)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length < 0 or length > 16384:
            return b""
        if length == 0:
            return b""
        return self.rfile.read(length)

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _bytes(self, status: int, body: bytes, media: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items() if values}


def _secure(headers: object) -> bool:
    getter = getattr(headers, "get", None)
    if getter is None:
        return False
    forwarded = getter("X-Monitor-Proto") or ""
    return forwarded.split(",", 1)[0].strip().lower() == "https"


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    if "MONITOR_PASSWORD" not in os.environ:
        print("Demo password: demo")
    print(f"Monitor on http://127.0.0.1:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
