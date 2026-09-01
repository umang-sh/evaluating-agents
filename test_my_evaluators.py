#!/usr/bin/env python3
"""
THE FALSIFICATION RUN. Run it from your terminal:

    python test_my_evaluators.py

No API keys. No network. No waiting. It scores your evaluators against four
runs captured live in pre-flight and saved to seed_fixtures.json.

--------------------------------------------------------------------------
WHAT IT IS ASKING
--------------------------------------------------------------------------
Not "does your code run". Your code ran the moment it imported.

    CAN YOUR EVALUATOR FAIL?

An evaluator that returns the same verdict on every run has not measured
anything. It cannot distinguish a good run from a bad one, so its score
carries no information -- however much you like the number.

Session 3 shipped exactly such a metric: task success 1.00 across three
architectures whose costs differed 2x. Only a live run caught it.

--------------------------------------------------------------------------
THE ORDER OF THE CHECKS MATTERS
--------------------------------------------------------------------------
`healthy` is tested FIRST, and a failure there stops everything. Three times
in this course the harness was the broken thing rather than the agent --
Session 2's classifier tagged its own clean control as broken, the span walk
counted every tool call twice, and this session's own pre-flight printed a GO
on zero data. If your evaluator fails the control, fix your evaluator.
"""

from __future__ import annotations

import sys

import evalkit
import seeds
import my_evaluators


# The reference row every seed is graded against. Deliberately a question all
# four seeds CAN answer, so the only thing separating them is how.
INPUTS = {"question": "What is the latest released version of `langgraph` on PyPI?"}
REF = {
    "must_contain":    ["1.2"],
    "expected_tools":  ["web_search"],
    "forbidden_tools": ["calculator", "package_registry"],
    "max_tool_calls":  1,
}

# Yours first, then the shipped ones for comparison.
EVALUATORS = list(my_evaluators.MY_EVALUATORS) + list(evalkit.OFFLINE_EVALUATORS)

GREEN, RED, DIM, OFF = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def main() -> int:
    fixtures = seeds.load_fixtures()
    if not fixtures:
        print("No seed_fixtures.json found.")
        print("Ask the instructor for it, or run: python preflight4.py --save")
        return 1

    by_seed: dict[str, list[dict]] = {}
    for f in fixtures:
        by_seed.setdefault(f["seed"], []).append(f)

    print(f"\n{len(fixtures)} saved runs across {len(by_seed)} seeds "
          f"| my_evaluators {my_evaluators.__version__}\n")

    grid: dict[str, dict[str, list]] = {}
    flat: list[dict] = []
    for seed, runs in by_seed.items():
        row: dict[str, list] = {}
        for r in runs:
            for res in evalkit.run_offline_evaluators(INPUTS, r, REF, EVALUATORS):
                row.setdefault(res["key"], []).append(res["score"])
                flat.append(res)
        grid[seed] = row

    keys = sorted({k for row in grid.values() for k in row})
    w = max((len(k) for k in keys), default=10) + 3
    print(f"{'seed':<14}" + "".join(f"{k:<{w}}" for k in keys))
    print("-" * (14 + w * len(keys)))
    order = [s for s in ("healthy", "wrong_tool", "redundant", "empty_search")
             if s in grid] + [s for s in grid if s not in
                              ("healthy", "wrong_tool", "redundant", "empty_search")]
    for seed in order:
        cells = []
        for k in keys:
            v = [x for x in grid[seed].get(k, []) if x is not None]
            if not v and grid[seed].get(k):
                cells.append(f"{DIM}skip{OFF}" + " " * (w - 4))
            elif not v:
                cells.append("-" + " " * (w - 1))
            elif all(v):
                cells.append(f"{GREEN}PASS{OFF}" + " " * (w - 4))
            elif not any(v):
                cells.append(f"{RED}fail{OFF}" + " " * (w - 4))
            else:
                cells.append(f"{RED}FLAKY{OFF}" + " " * (w - 5))
        print(f"{seed:<14}" + "".join(cells))
    print()

    report = evalkit.discrimination_report(flat)
    evalkit.print_discrimination(report)

    mine = {getattr(e, "__name__", "?") for e in my_evaluators.MY_EVALUATORS}
    problems: list[str] = []

    # 1. THE CONTROL. Checked first, and a failure here stops everything.
    for k in sorted(mine):
        v = [x for x in grid.get("healthy", {}).get(k, []) if x is not None]
        if v and not all(v):
            problems.append(
                f"{k} FAILS the healthy control.\n"
                f"      Your evaluator is broken, not the agent. Nothing else in\n"
                f"      this output means anything until that is fixed.")

    if problems:
        print(f"{RED}STOP.{OFF}")
        for p in problems:
            print(f"  - {p}")
        return 1

    # 2. Can each of yours fail?
    for k in sorted(mine):
        d = report.get(k)
        if d is None or d.n == d.skipped:
            problems.append(f"{k} never applied to a single run — it scores nothing.")
        elif not d.discriminates:
            which = "passes everything" if d.failed == 0 else "fails everything"
            problems.append(
                f"{k} {which} ({d.passed} pass / {d.failed} fail).\n"
                f"      You have no evidence it can tell a broken run from a good\n"
                f"      one. Which seed SHOULD it fail? Go make it fail that one.")

    print()
    if problems:
        print(f"{RED}NOT YET.{OFF}")
        for p in problems:
            print(f"  - {p}")
        print("\n  Fix my_evaluators.py and run this again. It takes two seconds.")
        return 1

    print(f"{GREEN}GOOD.{OFF} Every evaluator you wrote passes the control and fails")
    print("  at least one broken seed. It can measure.")
    print("\n  Now look at the `redundant` row above. Correct answer, right tool,")
    print("  grounded, cites its sources — and it searched twice for one fact.")
    print("  Count how many of your evaluators caught it, and compare that to the")
    print("  number you wrote down at the start of the session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
