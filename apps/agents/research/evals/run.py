"""Run the research cases on Amazon Bedrock.

The tools answer from a frozen book. Two graders then score the run:

- ToolTrajectory and BriefFacts are code. They check the tool calls and a
  few phrases the system prompt requires.
- FaithfulnessEvaluator and OutputEvaluator are Bedrock judges. They check
  that the brief stays inside the tool results and does not recommend a trade.

``RESEARCH_JUDGE_MODEL`` selects the judge. A stronger model than the agent
is the better judge when the account has one. Otherwise the judge is
``STRANDS_MODEL_ID``.
"""

from __future__ import annotations

import os
from typing import Any

from strands_evals import Experiment
from strands_evals.eval_task_handler import TracedHandler, eval_task
from strands_evals.evaluators import FaithfulnessEvaluator, OutputEvaluator
from strands_evals.types.evaluation_report import EvaluationReport

from agent import answer_text, build_agent, using_feeds
from evals.books import book
from evals.cases import strands_cases
from evals.evaluators import BriefFacts, ToolTrajectory
from evals.trace import tool_calls

RUBRIC = """
Score the brief against the tool results in the conversation.

Score 1.0 when every figure, date, headline, and filing in the brief appears in a tool result, the brief says prices are delayed when a tool returned prices, a tool error is reported when one was returned, there is no buy, sell, or hold rating, and the brief has no scratchpad or thinking tags. A refusal that asks for a ticker and does not invent one also scores 1.0.
Score 0.5 when the brief is mostly grounded but drops the delayed notice or a tool error.
Score 0.0 when it invents a price or a ticker, recommends a trade, or shows its scratchpad.

Set test_pass true only for a score of 1.0.
"""


def judge_model() -> str:
    return (
        os.environ.get("RESEARCH_JUDGE_MODEL")
        or os.environ.get("STRANDS_MODEL_ID")
        or "us.amazon.nova-micro-v1:0"
    )


def evaluators(*, judges: bool) -> list[Any]:
    chosen: list[Any] = [ToolTrajectory(), BriefFacts()]
    if judges:
        model = judge_model()
        chosen.append(FaithfulnessEvaluator(model=model))
        chosen.append(OutputEvaluator(rubric=RUBRIC, model=model))
    return chosen


def _live(case: Any) -> dict[str, str]:
    quotes, yahoo_news, seeking_alpha, filings = book(case.metadata["book"])
    with using_feeds(quotes, yahoo_news, seeking_alpha, filings):
        agent = build_agent()
        result = agent(case.input)
        case.metadata["calls"] = tool_calls(agent.messages)
        return {"output": answer_text(result)}


def run_live(*, judges: bool = True) -> EvaluationReport:
    """One pass over the cases. Each case builds a fresh agent on the frozen book."""
    task = eval_task(TracedHandler())(_live)
    experiment = Experiment(cases=strands_cases(), evaluators=evaluators(judges=judges))
    return experiment.run_evaluations(task)
