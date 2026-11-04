"""The demo agent behind the AgentCore HTTP contract.

Amazon Bedrock AgentCore calls ``POST /invocations`` with a JSON body and
``GET /ping`` for health. ``BedrockAgentCoreApp`` serves both on port 8080.
One agent is kept per session, so the conversation and the watchlist last
across turns in that session.

Run it from the repo root, after the installs in ``agent.py``:

    .venv/bin/python apps/agents/demo/serve.py

Then:

    curl -s -X POST http://127.0.0.1:8080/invocations \\
      -H 'Content-Type: application/json' \\
      -d '{"prompt": "Quote AAPL"}'
"""

from __future__ import annotations

from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp

from agent import answer_text, build_agent

app = BedrockAgentCoreApp()
_sessions: dict[str, Any] = {}


def _session_id(context: Any) -> str:
    session_id = getattr(context, "session_id", None)
    if isinstance(session_id, str) and session_id:
        return session_id
    return "local"


@app.entrypoint
def invoke(payload: dict[str, Any], context: Any) -> dict[str, str]:
    """Handle one prompt. The body is ``{"prompt": "..."}``."""
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return {"error": "Send JSON with a non-empty prompt."}
    session_id = _session_id(context)
    agent = _sessions.get(session_id)
    if agent is None:
        agent = build_agent()
        _sessions[session_id] = agent
    try:
        result = agent(prompt.strip())
    except Exception as exc:
        return {"error": f"The model call failed: {exc}"}
    return {"result": answer_text(result) or "(The model returned no text.)"}


if __name__ == "__main__":
    app.run()
