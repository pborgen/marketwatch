"""Status and commands for the two Market Watch agents.

A configured runtime ARN is called through AgentCore. Otherwise a local
``serve.py`` is used, on port 8080 for the demo and 8081 for current events.
Inside ECS, with no ARN, the agent is reported as not configured instead of
dialing localhost.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

COMMAND_TIMEOUT = 50.0
PING_TIMEOUT = 1.5
_CACHE_SECONDS = 5.0


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    description: str
    prompts: tuple[str, ...]
    runtime_arn_env: str
    local_url_env: str
    default_local_url: str


AGENTS: tuple[Agent, ...] = (
    Agent(
        id="market-watch",
        name="Market watch",
        description="Quotes, headlines, and a watchlist kept for this session.",
        prompts=("Quote AAPL", "Add MSFT to my watchlist and show it"),
        runtime_arn_env="DEMO_AGENT_RUNTIME_ARN",
        local_url_env="DEMO_AGENT_URL",
        default_local_url="http://127.0.0.1:8080",
    ),
    Agent(
        id="current-events",
        name="Current events",
        description="Collects headlines and releases, then stores one OpenSearch document per line in S3 under today's date.",
        prompts=("Collect today's events", "Collect events about oil prices"),
        runtime_arn_env="EVENTS_AGENT_RUNTIME_ARN",
        local_url_env="EVENTS_AGENT_URL",
        default_local_url="http://127.0.0.1:8081",
    ),
)


def by_id(agent_id: str) -> Agent | None:
    for agent in AGENTS:
        if agent.id == agent_id:
            return agent
    return None


def resolve(agent: Agent) -> tuple[str, str]:
    """``agentcore`` and an ARN, ``local`` and a URL, or ``none``."""
    arn = os.environ.get(agent.runtime_arn_env, "").strip()
    if arn:
        return "agentcore", arn
    explicit = os.environ.get(agent.local_url_env, "").strip()
    if explicit:
        return "local", explicit.rstrip("/")
    if os.environ.get("AWS_EXECUTION_ENV"):
        return "none", ""
    return "local", agent.default_local_url


class Catalog:
    """What the monitor lists and the commands it can send."""

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._remote: tuple[float, dict[str, dict[str, Any]] | None] = (0.0, None)
        self._lock = threading.Lock()

    def list_status(self) -> list[dict[str, Any]]:
        remote = self._remote_status()
        rows: list[dict[str, Any]] = []
        for agent in AGENTS:
            kind, value = resolve(agent)
            row = self._status(agent, kind, value, remote)
            row["prompts"] = list(agent.prompts)
            rows.append(row)
        return rows

    def command(self, agent_id: str, prompt: str, *, reset: bool = False) -> dict[str, Any]:
        agent = by_id(agent_id)
        if agent is None:
            return {"ok": False, "error": "Unknown agent.", "status": 404}
        text = prompt.strip()
        if reset:
            self._reset(agent.id)
        if not text:
            if reset:
                return {"ok": True, "agent": agent.id, "result": "Started a new session."}
            return {"ok": False, "error": "Enter a command.", "status": 400}
        if len(text) > 4000:
            return {"ok": False, "error": "That command is too long.", "status": 400}
        kind, value = resolve(agent)
        if kind == "none":
            return {"ok": False, "error": "This agent has no runtime configured.", "status": 409}
        try:
            if kind == "local":
                payload = self._invoke_local(value, text)
            else:
                payload = self._invoke_runtime(agent.id, value, text)
        except TimeoutError:
            return {"ok": False, "error": "The agent did not answer in time.", "status": 502}
        except OSError:
            if kind == "local":
                return {"ok": False, "error": f"Nothing is listening at {value}.", "status": 502}
            return {"ok": False, "error": "The runtime could not be reached.", "status": 502}
        except Exception as exc:
            return {"ok": False, "error": _short(exc), "status": 502}
        answer = _interpret(payload)
        answer["agent"] = agent.id
        return answer

    def _status(
        self,
        agent: Agent,
        kind: str,
        value: str,
        remote: dict[str, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        base = {"id": agent.id, "name": agent.name, "description": agent.description}
        if kind == "none":
            return {**base, "status": "offline", "detail": "No runtime is configured.", "target": ""}
        if kind == "local":
            code, detail = _ping(value)
            if code == 200:
                return {**base, "status": "ready", "detail": "Local process answered.", "target": value}
            return {**base, "status": "offline", "detail": detail, "target": value}
        found = None if remote is None else remote.get(value)
        label = _runtime_label(value)
        if remote is None:
            return {**base, "status": "unavailable", "detail": "Could not read AgentCore status.", "target": label}
        if found is None:
            return {**base, "status": "unavailable", "detail": "Runtime is not in this account.", "target": label}
        status = str(found.get("status") or "unknown")
        ready = status.upper() == "READY"
        return {
            **base,
            "status": "ready" if ready else "unavailable",
            "detail": status,
            "target": label,
        }

    def _remote_status(self) -> dict[str, dict[str, Any]] | None:
        needs_remote = any(resolve(agent)[0] == "agentcore" for agent in AGENTS)
        if not needs_remote:
            return {}
        now = time.monotonic()
        with self._lock:
            cached_at, cached = self._remote
            if cached is not None and now - cached_at < _CACHE_SECONDS:
                return cached
        try:
            found = _list_runtimes()
        except Exception:
            found = None
        with self._lock:
            self._remote = (now, found)
        return found

    def _reset(self, agent_id: str) -> None:
        with self._lock:
            self._sessions.pop(agent_id, None)

    def _session(self, agent_id: str) -> str:
        with self._lock:
            session = self._sessions.get(agent_id)
            if session is None:
                session = "monitor" + uuid.uuid4().hex
                self._sessions[agent_id] = session
            return session

    def _invoke_local(self, base: str, prompt: str) -> dict[str, Any]:
        body = json.dumps({"prompt": prompt}).encode()
        _code, raw = _http(base.rstrip("/") + "/invocations", body, COMMAND_TIMEOUT)
        return _json_body(raw)

    def _invoke_runtime(self, agent_id: str, arn: str, prompt: str) -> dict[str, Any]:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "bedrock-agentcore",
            config=Config(connect_timeout=3, read_timeout=COMMAND_TIMEOUT, retries={"max_attempts": 1}),
        )
        response = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=self._session(agent_id),
            payload=json.dumps({"prompt": prompt}).encode(),
            contentType="application/json",
            accept="application/json",
        )
        raw = response.get("response")
        if hasattr(raw, "read"):
            raw = raw.read()
        if isinstance(raw, str):
            raw = raw.encode()
        return _json_body(raw or b"")


def _list_runtimes() -> dict[str, dict[str, Any]]:
    import boto3

    client = boto3.client("bedrock-agentcore-control")
    found: dict[str, dict[str, Any]] = {}
    token = ""
    while True:
        kwargs: dict[str, Any] = {}
        if token:
            kwargs["nextToken"] = token
        page = client.list_agent_runtimes(**kwargs)
        for item in page.get("agentRuntimes") or []:
            arn = str(item.get("agentRuntimeArn") or "")
            if arn:
                found[arn] = item
        token = str(page.get("nextToken") or "")
        if not token:
            return found


def _ping(base: str) -> tuple[int, str]:
    if not _http_url(base):
        return 0, "The agent URL is not an HTTP address."
    try:
        code, _body = _http(base.rstrip("/") + "/ping", None, PING_TIMEOUT)
    except TimeoutError:
        return 0, f"No answer from {base}."
    except OSError:
        return 0, f"Nothing is listening at {base}."
    if code == 200:
        return 200, "ok"
    return code, f"The process at {base} returned HTTP {code}."


def _http(url: str, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    if not _http_url(url):
        raise OSError("unsupported URL")
    request = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except TimeoutError:
        raise
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            raise TimeoutError(str(reason)) from exc
        raise OSError(str(reason)) from exc


def _http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _json_body(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"result": text[:2000]}
    if isinstance(parsed, dict):
        return parsed
    return {"result": text[:2000]}


def _interpret(payload: dict[str, Any]) -> dict[str, Any]:
    error = payload.get("error")
    if error:
        return {"ok": False, "error": _short(error), "status": 502}
    result = payload.get("result")
    if isinstance(result, str) and result.strip():
        return {"ok": True, "result": result.strip()}
    if result is not None:
        return {"ok": True, "result": json.dumps(result)}
    return {"ok": False, "error": "The agent returned no answer.", "status": 502}


def _runtime_label(arn: str) -> str:
    marker = ":runtime/"
    if marker in arn:
        return arn.rsplit(marker, 1)[-1]
    return arn.rsplit("/", 1)[-1]


def _short(value: object) -> str:
    text = " ".join(str(value).split())
    if len(text) > 300:
        return text[:297] + "..."
    return text
