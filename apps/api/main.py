"""Monitor for the Market Watch agents.

The page is locked with one shared password. When ``MONITOR_PASSWORD`` is
unset, the password is ``demo``. After signing in you can see whether each
agent is up and send it a command.

Run it from the repo root:

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
_WEB = Path(os.environ["WEB_DIR"]) if os.environ.get("WEB_DIR") else Path(__file__).resolve().parents[1] / "web"


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
        if path not in {"/", "/login"}:
            self._json(404, {"error": "Not found."})
            return
        if path == "/login" and session_ok(self.headers):
            self._redirect("/")
            return
        page = "monitor.html" if session_ok(self.headers) else "login.html"
        self._html(200, _page(page, ""))

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
        form = _form(self._body())
        if not password_matches(form.get("password", "")):
            self._html(401, _page("login.html", "That password is not the demo password."))
            return
        self._redirect("/", set_cookie(_secure(self.headers)))

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

    def _html(self, status: int, page: str) -> None:
        body = page.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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


def _page(name: str, error: str) -> str:
    return (_WEB / name).read_text(encoding="utf-8").replace("{{error}}", error)


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
