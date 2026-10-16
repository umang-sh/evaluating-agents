"""
THE ONE FILE YOU EDIT.  Copy it, rename it with your group number, fill in the blanks.

    cp endterm/my_release_TEMPLATE.py endterm/my_release_G7.py

Four functions. Three are marked. Write them, then run:

    python endterm/run_endterm.py <your case id> endterm/my_release_G7.py > scorecard.txt

Submit THREE files: this file, scorecard.txt, and decision.md (one page).

A WORD ON WHAT IS BEING MARKED
------------------------------
Not whether your verdict matches mine. Whether the measurement under it holds up when
I ask you where the number came from. A supported REJECT beats an unsupported SHIP, and
"the evidence does not separate the two versions" is a full-marks answer where it is true.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first

# Anything whose ACTION field is one of these means "nothing needs doing".
NO_ACTION = ("", "none", "monitor", "no action")


# ==========================================================================
# 1. resolved(run) -> bool        "was this maintenance request actually resolved?"
# ==========================================================================
# A run gives you:
#   run["scores"]["outcome_match"]        1, 0 or None -- was the answer right?
#   run["outputs"]["tail"]["ACTION"]      what the agents said to do (may be missing)
#   run["workflow"]["work_order"]         truthy if a work order was issued
#   run["workflow"]["status_log"]         e.g. [... "AWAITING_APPROVAL", "APPROVED" ...]
#
# WRONG SHAPE, and why:
#
#     def resolved(run):
#         return run["scores"]["outcome_match"] == 1
#
# That counts a request as resolved when the agents named the right fault and the right
# part -- and the engineer then refused it because the part was not on the shelf. Nobody
# went to the machine. It is still broken. A right answer is not a resolved request.
def resolved(run) -> bool:
    raise NotImplementedError("write resolved()")


# ==========================================================================
# 2. must_hold(run) -> (bool, str)      one regression test, run on every run
# ==========================================================================
# Return (True, why) if this run is acceptable, (False, evidence) if it is not. The second
# value is printed as the evidence for a regression, so make it say what went wrong.
#
# You have:
#   run["outputs"]["agent_calls"]            ["planner", "diagnostics", ...] in order
#   run["row"]["expected_agents"]            who should have run, in order
#   run["row"]["forbidden_agents"]           who must not have run at all
#   run["scores"]["outcome_match"]           was the answer right?
#
# WRONG SHAPE, and why:
#
#     def must_hold(run):
#         return set(run["outputs"]["agent_calls"]) == set(run["row"]["expected_agents"]), ""
#
# A set has no order and no repeats. One of the twelve requests needs diagnostics twice,
# and one of them ran documentation BEFORE diagnostics -- wrote the report before it knew
# what was wrong. Both pass a set comparison. Order is the thing you are testing.
def must_hold(run) -> tuple[bool, str]:
    raise NotImplementedError("write must_hold()")


# ==========================================================================
# 3. decide(cmp) -> (verdict, reason)        the deployment decision
# ==========================================================================
# verdict is one of "SHIP", "HOLD", "REJECT", "NOT MEASURABLE".
#
# cmp gives you:
#   cmp["regressions"]      questions that passed must_hold on A and fail on the candidate
#   cmp["fixed"]            questions that failed on A and pass on the candidate
#   cmp["still_failing"]    failed on both
#   cmp["metrics"][name]["direction"]   "better" | "worse" | "no detectable difference"
#   cmp["metrics"][name]["diff"], ["lo"], ["hi"]    the paired difference and its interval
#   cmp["seeded"]           True if the candidate was built, not re-run
#
# WRONG SHAPE, and why:
#
#     def decide(cmp):
#         if cmp["metrics"]["task success"]["cand"] >= cmp["metrics"]["task success"]["base"]:
#             return "SHIP", "task success did not drop"
#
# Two faults. It compares two point estimates with no interval, so noise reads as a
# result. And a version can hold its aggregate task success while breaking a specific
# question that used to work -- an average has room to hide one broken request inside it.
# Decide which of the things in `cmp` you are willing to ship on, and say so.
def decide(cmp) -> tuple[str, str]:
    raise NotImplementedError("write decide()")


# ==========================================================================
# 4. alert(today, usual) -> list[str]        NOT MARKED. Do it if you have time.
# ==========================================================================
# After it ships you watch it. `today` and `usual` are day summaries with keys
# "task_success", "approval", "work_orders", "completion", "cost_usd", "p90_latency_s"
# -- the rate ones are (k, n) pairs. Return a list of strings, one per thing worth waking
# someone for, and an empty list on a normal day.
#
# The hard part is not the threshold. It is that a drop in approval rate can mean the
# agents got worse OR that the store ran out of a part. One of those is your problem.
def alert(today, usual) -> list[str]:
    return []
