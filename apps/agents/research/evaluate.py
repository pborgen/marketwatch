"""Score the research agent on Amazon Bedrock.

    .venv/bin/python apps/agents/research/evaluate.py --gate
    .venv/bin/python apps/agents/research/evaluate.py
    .venv/bin/python apps/agents/research/evaluate.py --trials 5

``--gate`` skips the Bedrock judges and keeps the tool and brief checks.
``--trials`` repeats the run. The process fails unless every trial passes,
which is the check that matters for a model that does not answer the same
way twice.
"""

from __future__ import annotations

import sys

from evals.run import run_live


def _trials(argv: list[str]) -> int:
    if "--trials" not in argv:
        return 1
    index = argv.index("--trials") + 1
    if index >= len(argv):
        raise SystemExit("--trials needs a number.")
    try:
        count = int(argv[index])
    except ValueError:
        raise SystemExit("--trials needs a number.") from None
    if count < 1:
        raise SystemExit("--trials needs a number of at least 1.")
    return count


def main(argv: list[str]) -> None:
    judges = "--gate" not in argv
    ok = True
    for trial in range(_trials(argv)):
        if trial:
            print()
        report = run_live(judges=judges)
        print(f"trial {trial + 1}")
        for case, passed, reason in zip(report.cases, report.test_passes, report.reasons, strict=False):
            state = "pass" if passed else "FAIL"
            name = case.get("name") or case.get("input")
            print(f"{state}  {case.get('evaluator')}  {name}: {reason}")
            if passed:
                continue
            ok = False
            output = case.get("actual_output")
            if not output:
                continue
            text = str(output).strip()
            if len(text) > 500:
                text = text[:497] + "..."
            print(text)
            print()
        print(f"score {report.overall_score:.2f}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
