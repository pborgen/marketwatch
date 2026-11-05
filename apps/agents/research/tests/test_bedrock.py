"""Live evaluation. Skipped unless RESEARCH_EVAL=1, because it calls Bedrock."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.bedrock


@pytest.mark.skipif(os.environ.get("RESEARCH_EVAL") != "1", reason="Set RESEARCH_EVAL=1 to call Bedrock.")
def test_research_cases_on_bedrock() -> None:
    from evals.run import run_live

    report = run_live()
    failed = [
        f"{case.get('evaluator')} / {case.get('name')}: {reason}"
        for case, passed, reason in zip(report.cases, report.test_passes, report.reasons)
        if not passed
    ]
    assert not failed, "\n".join(failed)
