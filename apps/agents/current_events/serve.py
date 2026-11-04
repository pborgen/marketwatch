"""The current-events agent behind the AgentCore HTTP contract.

``POST /invocations`` with ``{"prompt": "..."}`` talks to the agent.
``{"action": "collect"}`` stores events without a model call, which is the
shape a schedule can invoke. Optional fields are ``topics`` (string),
``limit`` (integer), and ``include_releases`` (boolean).

Run it from the repo root, after the installs in ``agent.py``:

    DATA_BUCKET=your-bucket .venv/bin/python apps/agents/current_events/serve.py
"""

from __future__ import annotations

from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp

from agent import answer_text, build_agent
from collect import run_collection

app = BedrockAgentCoreApp()
_sessions: dict[str, Any] = {}


def _session_id(context: Any) -> str:
    session_id = getattr(context, "session_id", None)
    if isinstance(session_id, str) and session_id:
        return session_id
    return "local"


def _collect(payload: dict[str, Any]) -> dict[str, Any]:
    topics = payload.get("topics") if isinstance(payload.get("topics"), str) else ""
    limit = payload.get("limit") if isinstance(payload.get("limit"), int) else 8
    include = payload.get("include_releases")
    if not isinstance(include, bool):
        include = True
    return run_collection(topics, limit, include_releases=include)


@app.entrypoint
def invoke(payload: dict[str, Any], context: Any) -> dict[str, Any]:
    """Collect events, or handle one prompt. The prompt body is ``{"prompt": "..."}``."""
    if isinstance(payload, dict) and payload.get("action") == "collect":
        return _collect(payload)
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return {"error": "Send JSON with a non-empty prompt, or action set to collect."}
    session_id = _session_id(context)
    agent = _sessions.get(session_id)
    if agent is None:
        try:
            agent = build_agent()
        except Exception as exc:
            return {"error": f"The agent failed to start: {exc}"}
        _sessions[session_id] = agent
    try:
        result = agent(prompt.strip())
    except Exception as exc:
        return {"error": f"The model call failed: {exc}"}
    return {"result": answer_text(result) or "(The model returned no text.)"}


if __name__ == "__main__":
    app.run()
