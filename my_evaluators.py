"""
YOUR FILE. This is the one you edit today.

Open it in VS Code, fill in the TODOs, save, then in the terminal:

    python test_my_evaluators.py

The notebook imports this file. If you edit it while the notebook is running,
the notebook will still be using the OLD version -- Python caches imported
modules. Restart the kernel, or run the cell that calls importlib.reload().

That is not a quirk to work around. It is the first thing that will bite you
when your evaluators live in version control instead of in a cell, which is
where they live in production. Session 12 is about exactly that.

--------------------------------------------------------------------------
WHY THIS IS A FILE AND NOT A NOTEBOOK CELL
--------------------------------------------------------------------------
An evaluator written in a cell cannot be imported by anything, cannot be
diffed, cannot be run from a terminal, and cannot be committed. An evaluator
in a file can do all four. In production, evaluators are code under review
that runs in CI -- not a cell somebody ran once.

--------------------------------------------------------------------------
THE SIGNATURE
--------------------------------------------------------------------------
LangSmith matches evaluator parameters BY NAME. Declare only what you need:

    inputs             the dataset row's inputs      {"question": ...}
    outputs            what your agent produced      {"answer","tool_calls",...}
    reference_outputs  the row's answer key          {"must_contain",...}
    run                the full LangSmith trace      (online only)
    example            the full dataset example

Return a dict {"key","score","comment"} -- or just a bool, in which case the
function's name becomes the metric name.
"""

from __future__ import annotations

__version__ = "s4-2026-09-01a"


# ==========================================================================
# EXERCISE 1 — Tool correctness
#
# Did the agent use the tool this task needed, and avoid the one that would
# be a mistake?
#
# Two hints that are really the whole exercise:
#   1. expected_tools is a SET, not a sequence. Order is the trajectory
#      evaluator's job. Keep them apart -- one metric failing for two
#      unrelated reasons is the fastest way to make a number meaningless.
#   2. Decide what happens when the agent calls NO tools at all. That is a
#      real case and your rule will meet it within ten minutes.
# ==========================================================================

def my_tool_check(outputs: dict, reference_outputs: dict) -> dict:
    used      = {tc["name"] for tc in outputs.get("tool_calls", [])}
    expected  = set(reference_outputs.get("expected_tools", []) or [])
    forbidden = set(reference_outputs.get("forbidden_tools", []) or [])

    # TODO: set `ok` to True only when the agent used every expected tool
    #       and none of the forbidden ones.
    ok = True   # <-- REPLACE THIS

    return {"key": "my_tool_check", "score": ok,
            "comment": f"used={sorted(used)} expected={sorted(expected)} "
                       f"forbidden={sorted(forbidden)}"}


# ==========================================================================
# EXERCISE 2 (optional, do it if you finish early)
#
# Write ONE evaluator of your own that:
#   - PASSES the `healthy` seed, and
#   - FAILS at least one broken seed.
#
# If it passes all four, it is decoration. If it fails all four, it is broken.
# `test_my_evaluators.py` will tell you which.
#
# Ideas that are not already covered:
#   - did the answer cite a source at all?
#   - did any single tool call take absurdly longer than its siblings?
#   - did the agent answer without calling any tool?
# ==========================================================================

def my_own_check(outputs: dict, reference_outputs: dict) -> dict:
    # TODO: your rule. Delete this function entirely if you are not doing
    #       exercise 2 -- an evaluator that always returns None is worse
    #       than no evaluator, because a column of blanks reads as passes.
    return {"key": "my_own_check", "score": None,
            "comment": "not implemented"}


# What the test script and the notebook both run.
# Comment out my_own_check if you are skipping exercise 2.
MY_EVALUATORS = [
    my_tool_check,
    my_own_check,
]
