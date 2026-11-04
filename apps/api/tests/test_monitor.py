from __future__ import annotations

import http.client
import json
from threading import Thread
from http.server import ThreadingHTTPServer

from agents import AGENTS, Catalog, resolve
from auth import password_matches, session_ok
from main import Handler


class FakeCatalog:
    def list_status(self) -> list[dict[str, object]]:
        return [
            {
                "id": "market-watch",
                "name": "Market watch",
                "description": "Quotes",
                "status": "ready",
                "detail": "Local process answered.",
                "target": "http://127.0.0.1:8080",
                "prompts": ["Quote AAPL"],
            }
        ]

    def command(self, agent_id: str, prompt: str, *, reset: bool = False) -> dict[str, object]:
        self.last = (agent_id, prompt, reset)
        return {"ok": True, "agent": agent_id, "result": "AAPL is delayed."}


def test_default_password_is_demo(monkeypatch) -> None:
    monkeypatch.delenv("MONITOR_PASSWORD", raising=False)
    assert password_matches("demo")
    assert not password_matches("secret")


def test_blank_password_locks_the_monitor(monkeypatch) -> None:
    monkeypatch.setenv("MONITOR_PASSWORD", " ")
    assert not password_matches("demo")
    assert not session_ok({"Cookie": "monitor=anything"})


def test_runtime_arn_wins_over_a_local_url(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:1:runtime/marketwatch_dev")
    monkeypatch.setenv("DEMO_AGENT_URL", "http://127.0.0.1:9")
    assert resolve(AGENTS[0]) == (
        "agentcore",
        "arn:aws:bedrock-agentcore:us-east-1:1:runtime/marketwatch_dev",
    )


def test_ecs_without_an_arn_does_not_dial_localhost(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_AGENT_RUNTIME_ARN", raising=False)
    monkeypatch.delenv("DEMO_AGENT_URL", raising=False)
    monkeypatch.setenv("AWS_EXECUTION_ENV", "AWS_ECS_FARGATE")
    assert resolve(AGENTS[0]) == ("none", "")


def test_offline_command_names_the_address(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_AGENT_RUNTIME_ARN", raising=False)
    monkeypatch.setenv("DEMO_AGENT_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)
    result = Catalog().command("market-watch", "Quote AAPL")
    assert result["ok"] is False
    assert result["error"] == "Nothing is listening at http://127.0.0.1:9."


def test_local_default_outside_ecs(monkeypatch) -> None:
    monkeypatch.delenv("EVENTS_AGENT_RUNTIME_ARN", raising=False)
    monkeypatch.delenv("EVENTS_AGENT_URL", raising=False)
    monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)
    assert resolve(AGENTS[1]) == ("local", "http://127.0.0.1:8081")


def test_password_gates_the_page_and_commands(monkeypatch) -> None:
    monkeypatch.setenv("MONITOR_PASSWORD", "secret")
    fake = FakeCatalog()
    previous = Handler.catalog
    Handler.catalog = fake
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        status, body, _cookie = _exchange(port, "GET", "/health")
        assert status == 200
        assert json.loads(body) == {"status": "ok"}

        status, body, _cookie = _exchange(port, "GET", "/")
        assert status == 200
        assert b'id="root"' in body
        assert b"<textarea" not in body

        status, body, _cookie = _exchange(port, "GET", "/api/agents")
        assert status == 401

        status, body, cookie = _exchange(port, "POST", "/login", "password=nope")
        assert status == 401
        assert b"not the demo password" in body
        assert cookie is None

        status, _body, cookie = _exchange(port, "POST", "/login", "password=secret")
        assert status == 303
        assert cookie is not None
        session = cookie.split(";", 1)[0]

        status, body, _cookie = _exchange(port, "GET", "/", cookie=session)
        assert status == 200
        assert b'id="root"' in body
        status, body, _cookie = _exchange(port, "GET", "/api/agents", cookie=session)
        assert status == 200
        assert json.loads(body)["agents"][0]["id"] == "market-watch"

        status, body, _cookie = _exchange(
            port,
            "POST",
            "/api/agents/market-watch/commands",
            json.dumps({"prompt": "Quote AAPL"}),
            cookie=session,
            content_type="application/json",
        )
        assert status == 200
        assert json.loads(body)["result"] == "AAPL is delayed."
        assert fake.last == ("market-watch", "Quote AAPL", False)

        status, _body, cleared = _exchange(port, "POST", "/logout", cookie=session)
        assert status == 303
        assert "Max-Age=0" in cleared
        status, body, _cookie = _exchange(port, "GET", "/")
        assert b"<textarea" not in body

        status, body, secure = _exchange(
            port,
            "POST",
            "/login",
            "password=secret",
            headers={"X-Monitor-Proto": "https"},
        )
        assert status == 303
        assert "Secure" in secure
    finally:
        Handler.catalog = previous
        server.shutdown()
        server.server_close()


def _exchange(
    port: int,
    method: str,
    path: str,
    body: str | None = None,
    cookie: str | None = None,
    content_type: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, str | None]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    sent = dict(headers or {})
    if cookie:
        sent["Cookie"] = cookie
    if body is not None and content_type is None:
        content_type = "application/x-www-form-urlencoded"
    if content_type:
        sent["Content-Type"] = content_type
    connection.request(method, path, body=body, headers=sent)
    response = connection.getresponse()
    payload = response.read()
    set_cookie = response.getheader("Set-Cookie")
    status = response.status
    connection.close()
    return status, payload, set_cookie
