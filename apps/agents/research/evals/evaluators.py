"""Deterministic graders. These do not call a model.

Tool choice and a few standing rules (say the price is delayed, repeat a
tool error, do not rate the stock) are checked in code. A Bedrock judge
scores whether the brief stays inside the tool results.
"""

from __future__ import annotations

import re

from strands_evals.evaluators import Evaluator
from strands_evals.types import EvaluationData, EvaluationOutput
from strands_evals.types.trace import Session, ToolExecutionSpan

from evals.trace import bare_ticker

_KNOWN = {"quote", "price_history", "headlines", "filings"}
_RATING = re.compile(
    r"\b(?:strong|moderate)\s+(?:buy|sell)\b"
    r"|\brating\s*(?:is|:)\s*(?:a\s+)?(?:strong\s+|moderate\s+)?(?:buy|sell|hold)\b"
    r"|\b(?:i|we)\s+(?:would\s+)?(?:recommend|suggest)\s+(?:buying|selling|a\s+buy|a\s+sell)\b"
    r"|\byou\s+should\s+(?:buy|sell)\b",
    re.IGNORECASE,
)


def _listed_calls(trajectory: object) -> list[dict[str, str]] | None:
    if isinstance(trajectory, Session):
        calls: list[dict[str, str]] = []
        for trace in trajectory.traces:
            for span in trace.spans:
                if isinstance(span, ToolExecutionSpan):
                    raw = span.tool_call.arguments.get("symbol", "")
                    calls.append({"name": span.tool_call.name, "symbol": str(raw)})
        return calls
    if isinstance(trajectory, list):
        calls = []
        for item in trajectory:
            if isinstance(item, str):
                calls.append({"name": item, "symbol": ""})
            elif isinstance(item, dict):
                calls.append({"name": str(item.get("name") or ""), "symbol": str(item.get("symbol") or "")})
        return calls
    return None


def calls_of(data: EvaluationData) -> list[dict[str, str]]:
    recorded = (data.metadata or {}).get("calls")
    if isinstance(recorded, list):
        return _listed_calls(recorded) or []
    found = _listed_calls(data.actual_trajectory)
    return found or []


def _fail(reason: str) -> list[EvaluationOutput]:
    return [EvaluationOutput(score=0.0, test_pass=False, reason=reason)]


def _ok(reason: str) -> list[EvaluationOutput]:
    return [EvaluationOutput(score=1.0, test_pass=True, reason=reason)]


class ToolTrajectory(Evaluator[str, str]):
    """The case's tools were called, and only for the tickers the user named."""

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        meta = evaluation_case.metadata or {}
        expected_tools = set(meta.get("tools") or [])
        expected_symbols = set(meta.get("symbols") or [])
        calls = calls_of(evaluation_case)
        problems: list[str] = []
        seen_tools: set[str] = set()
        seen_symbols: set[str] = set()
        for call in calls:
            name = call["name"]
            seen_tools.add(name)
            if name not in _KNOWN:
                problems.append(f"{name or 'a tool'} is not one of the research tools.")
                continue
            ticker = bare_ticker(call["symbol"])
            if ticker is None:
                shown = call["symbol"] or "(none)"
                problems.append(f"{name} was called with {shown}, which is not a ticker.")
                continue
            if ticker not in expected_symbols:
                problems.append(f"{name} was called for {ticker}.")
                continue
            seen_symbols.add(ticker)
        missing_tools = expected_tools - seen_tools
        if missing_tools:
            problems.append(f"{', '.join(sorted(missing_tools))} was not called.")
        missing_symbols = expected_symbols - seen_symbols
        if missing_symbols and expected_tools:
            problems.append(f"{', '.join(sorted(missing_symbols))} was never passed to a tool.")
        if problems:
            return _fail(" ".join(problems))
        if not calls:
            return _ok("No tool was called.")
        return _ok("The tools match the case.")


class BriefFacts(Evaluator[str, str]):
    """The brief says what the case requires and does not rate the stock."""

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        meta = evaluation_case.metadata or {}
        text = str(evaluation_case.actual_output or "")
        problems: list[str] = []
        if meta.get("refuse") and not text.strip():
            problems.append("The brief is empty.")
        lowered = text.lower()
        for fact in meta.get("mention") or []:
            if str(fact).lower() not in lowered:
                problems.append(f"The brief does not mention {fact}.")
        if _RATING.search(text):
            problems.append("The brief rates the stock.")
        if "<thinking" in lowered or "</thinking>" in lowered:
            problems.append("The brief includes the model's scratchpad.")
        if problems:
            return _fail(" ".join(problems))
        return _ok("The brief follows the case.")
