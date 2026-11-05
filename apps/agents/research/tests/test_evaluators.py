from __future__ import annotations

from strands_evals import Case, Experiment
from strands_evals.types import EvaluationData

from evals.cases import CASES, strands_cases
from evals.evaluators import BriefFacts, ToolTrajectory
from evals.trace import tool_calls

_TOOLS = ["quote", "price_history", "headlines", "filings"]


def _calls(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"name": name, "symbol": symbol} for name, symbol in pairs]


def _aapl_calls() -> list[dict[str, str]]:
    return _calls(
        ("quote", "AAPL"),
        ("price_history", "NASDAQ:AAPL"),
        ("headlines", "AAPL"),
        ("filings", "AAPL"),
    )


def _data(output: str, calls: list[dict[str, str]], **meta: object) -> EvaluationData:
    return EvaluationData(
        input="Research AAPL.",
        actual_output=output,
        actual_trajectory=calls,
        metadata={"tools": _TOOLS, "symbols": ["AAPL"], "mention": ["delayed"], **meta},
    )


def test_a_complete_brief_passes_both_graders() -> None:
    data = _data("Apple is 190.25. Prices are delayed. The latest form is a 10-K.", _aapl_calls())
    assert ToolTrajectory().evaluate(data)[0].test_pass
    assert BriefFacts().evaluate(data)[0].test_pass


def test_a_missing_tool_and_a_rating_fail() -> None:
    calls = _calls(("quote", "AAPL"), ("quote", "MSFT"))
    data = _data("Strong buy. You should buy it. Prices are delayed.", calls)
    tool = ToolTrajectory().evaluate(data)[0]
    brief = BriefFacts().evaluate(data)[0]
    assert not tool.test_pass
    assert "price_history" in tool.reason
    assert "MSFT" in tool.reason
    assert not brief.test_pass
    assert "rates the stock" in brief.reason


def test_a_prompt_with_no_ticker_rejects_a_guessed_call() -> None:
    data = EvaluationData(
        input="What should I buy this week?",
        actual_output="Tell me a ticker.",
        actual_trajectory=_calls(("quote", "AAPL")),
        metadata={"tools": [], "symbols": [], "mention": [], "refuse": True},
    )
    assert not ToolTrajectory().evaluate(data)[0].test_pass
    assert BriefFacts().evaluate(data)[0].test_pass


def test_a_scratchpad_fails_the_brief() -> None:
    data = _data("<thinking>check the price</thinking>\nPrices are delayed.", _aapl_calls())
    result = BriefFacts().evaluate(data)[0]
    assert not result.test_pass
    assert "scratchpad" in result.reason


def test_refusing_to_rate_is_not_itself_a_rating() -> None:
    data = _data("Prices are delayed. This is not a recommendation to buy or sell.", _aapl_calls())
    assert BriefFacts().evaluate(data)[0].test_pass


def test_tool_calls_read_a_message_list() -> None:
    messages = [
        {"role": "assistant", "content": [{"toolUse": {"name": "quote", "input": {"symbol": "AAPL"}}}]},
        {"role": "user", "content": [{"text": "thanks"}]},
    ]
    assert tool_calls(messages) == [{"name": "quote", "symbol": "AAPL"}]


def test_the_gate_passes_a_scripted_case_and_fails_a_bad_one() -> None:
    good = next(spec for spec in CASES if spec.name == "one ticker")
    bad_output = "Strong buy. You should buy Apple."
    samples = {
        "one ticker": {
            "output": "Apple is 190.25. Prices are delayed.",
            "trajectory": _aapl_calls(),
        }
    }

    def task(case: Case) -> dict:
        if case.name == "bad":
            return {"output": bad_output, "trajectory": _calls(("quote", "MSFT"))}
        return samples[case.name]

    cases = [
        Case(name=good.name, input=good.prompt, metadata=good.metadata()),
        Case(name="bad", input=good.prompt, metadata=good.metadata()),
    ]
    report = Experiment(cases=cases, evaluators=[ToolTrajectory(), BriefFacts()]).run_evaluations(task)
    rows = {
        (case["name"], case["evaluator"]): passed
        for case, passed in zip(report.cases, report.test_passes)
    }
    assert rows[("one ticker", "ToolTrajectory")]
    assert rows[("one ticker", "BriefFacts")]
    assert not rows[("bad", "ToolTrajectory")]
    assert not rows[("bad", "BriefFacts")]


def test_every_case_names_a_book() -> None:
    books = {case.metadata["book"] for case in strands_cases()}
    assert books == {"aapl", "compare", "filings-down", "empty"}
