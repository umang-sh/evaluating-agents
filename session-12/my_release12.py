"""
THE ONE FILE YOU EDIT TODAY.

You are the last line before a new version of the maintenance assistant goes live at the
plant. Four functions, one per hands-on. Each one is a decision a real release team
writes down so that nobody has to make it up on the day.

    Part 1  resolved(run)          what counts as a resolved maintenance request?
    Part 2  must_hold(run)         the regression suite: what must stay true on every question?
    Part 3  decide(cmp)            ship the new version, hold it, or reject it?
    Part 4  alert(today, usual)    in production, when should someone be woken up?

Every part has a WORKED EXAMPLE just above it: a real, working function that answers a
DIFFERENT question in the same shape. Read it first, then write yours. The examples are
deliberately not good answers -- each one says what is wrong with it.

To see every example run on the real data:

    python session-12/my_release12.py

To check YOUR functions (free, no model, run it as often as you like):

    python session-12/screen_my_release.py --part 1        (or 2, 3, 4)


WHAT ONE RUN LOOKS LIKE (Parts 1 and 2)
---------------------------------------
A run is one answer to one question, as a dictionary. Here is a real one, trimmed:
version A, question HW-012, repeat 1.

    run["row_id"]                     "HW-012"
    run["question"]                   "Compressor discharge is sitting at 88 C. Is that
                                       within limits or do I need to act?"
    run["outputs"]["agent_calls"]     ["planner", "documentation", "diagnostics", "maintenance"]
                                       <- who actually ran, in order
    run["row"]["expected_agents"]     ["planner", "diagnostics", "documentation"]
                                       <- who SHOULD have run, in order
    run["row"]["forbidden_agents"]    ["maintenance"]      <- who must NOT run
    run["scores"]["outcome_match"]    1                    <- 1 = right fault, part and action
                                                              0 = wrong
    run["outputs"]["tail"]            {"MACHINE": "AIR-COMP", "FAULT_CODE": "NO-FAULT",
                                       "PART": "", "ACTION": "monitor", ...}
                                       <- the agents' final recommendation
    run["workflow"]["status_log"]     ["REQUESTED", "DOCUMENTED", "DIAGNOSED",
                                       "RECOMMENDED", "CLOSED"]
                                       <- every stage the request went through
    run["workflow"]["work_order"]     None                 <- no technician was sent

And one where a technician WAS sent (HW-001, repeat 1):

    run["workflow"]["status_log"]     [..., "AWAITING_APPROVAL", "APPROVED",
                                       "WORK_ORDER_ISSUED", "CLOSED"]
    run["workflow"]["work_order"]     {"id": "WO-HW-001", "machine": "CONVEYOR",
                                       "part": "SKF-6208", "action": "replace", ...}
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first

NO_ACTION = ("", "none", "monitor", "no action")   # recommendations that need no technician


# ===========================================================================
# PART 1 -- WHAT COUNTS AS RESOLVED?                         (hands-on 1, 12 min)
#
# The plant manager wants one number: "maintenance resolution rate". Nobody has said
# what "resolved" means. You decide, and you write it down as code.
#
# resolved(run) returns True or False for ONE run. The screener counts the Trues.
# ===========================================================================

# ---- WORKED EXAMPLE -------------------------------------------------------
def example_resolved_if_closed(run) -> bool:
    """'Resolved' = the workflow reached CLOSED.

    How it reads the run:  the LAST entry of the status log.
    What is wrong with it: every one of version A's 24 runs ends CLOSED -- including the
    ones where the diagnosis was wrong. A definition that is true for everything
    measures nothing.
    """
    return run["workflow"]["status_log"][-1] == "CLOSED"


# ---- YOURS ----------------------------------------------------------------
# Decide these three cases, then write the code:
#
#   1. HW-002: the agents got the diagnosis WRONG, but a work order went out anyway.
#      Resolved?              (hint: run["scores"]["outcome_match"] == 0)
#   2. HW-004: the machine is fine, the agents said so, nothing was sent.
#      Resolved?              (hint: ACTION is in NO_ACTION, work_order is None)
#   3. HW-003: the agents were right, but the engineer said NO because the part is not
#      in stock.              (hint: "REJECTED" is in the status log)
#
# Useful pieces:
#   right  = run["scores"]["outcome_match"] == 1
#   action = (run["outputs"]["tail"].get("ACTION") or "").lower()
#   sent   = run["workflow"]["work_order"] is not None
#   needs_work = action not in NO_ACTION
def resolved(run) -> bool:
    raise NotImplementedError("write resolved")


# ===========================================================================
# PART 2 -- THE REGRESSION SUITE                             (hands-on 2, 20 min)
#
# must_hold(run) is asked about EVERY run of EVERY version. A question "holds" for a
# version only if must_hold passes on ALL of its repeats.
#
# A regression is a question that held on version A and does not hold on the new
# version. A suite that never fails is not testing anything, so the screener checks
# that yours FAILS on the one bug everybody knows about (HW-012 on version A).
#
# must_hold returns TWO things:   return ok, evidence
#     ok        True = this run is fine;  False = this run BREAKS the suite
#     evidence  one short sentence saying what you saw. A person reads it and decides
#               whether to believe you, so put the actual values in it.
# ===========================================================================

# ---- WORKED EXAMPLE -------------------------------------------------------
def example_no_repeats(run):
    """'No agent runs more than twice.'

    How it reads the run:  counts each name in agent_calls.
    Shape to copy:         build the evidence from what you saw, return (ok, evidence).
    What is wrong with it: it passes HW-012 on version A -- the agents there ran once
    each, just in the WRONG ORDER, and one of them should not have run at all. It
    cannot fail on the known bug, so as a regression suite it is useless.
    """
    calls = run["outputs"]["agent_calls"]
    too_many = sorted({a for a in calls if calls.count(a) > 2})
    if too_many:
        return False, f"{too_many} ran more than twice: {calls}"
    return True, f"no agent ran more than twice: {calls}"


# ---- YOURS ----------------------------------------------------------------
# Two promises, in this order:
#
#   1. The right agents ran, in the right order, and none of the forbidden ones.
#        got  = run["outputs"]["agent_calls"]      (includes "planner")
#        want = run["row"]["expected_agents"]      (includes "planner" too)
#        bad  = agents in got that are also in run["row"]["forbidden_agents"]
#      Careful: compare the LISTS, not sets -- order matters. On HW-012 a set of
#      {diagnostics, documentation} looks right while the order is wrong.
#
#   2. The answer was right:  run["scores"]["outcome_match"] == 1
#
# Example evidence for a failure:  "ran ['documentation', 'diagnostics', 'maintenance'],
#                                   expected ['diagnostics', 'documentation']"
def must_hold(run):
    """Return (ok, evidence).  ok=False means this run BREAKS the suite."""
    raise NotImplementedError("write must_hold")


# ===========================================================================
# PART 3 -- SHIP, HOLD OR REJECT?                            (hands-on 3, 20 min)
#
# cmp is what the pipeline hands you after comparing version A with a candidate.
# A real one, A against B (trimmed):
#
#   cmp["cand"]            "B"
#   cmp["regressions"]     ["HW-003", "HW-005"]   held on A, fail on B
#   cmp["fixed"]           ["HW-012"]             failed on A, hold on B
#   cmp["still_failing"]   ["HW-002", "HW-006", "HW-008"]
#   cmp["metrics"]["task success"]["direction"]      "no detectable difference"
#   cmp["metrics"]["cost per run ($)"]["direction"]  "no detectable difference"
#       every metric has a direction: "better", "worse" or "no detectable difference"
#       metrics: "task success", "right agents, right order", "right tools",
#                "tokens per run", "cost per run ($)", "latency (s)"
#
# "No detectable difference" does NOT mean equal. It means 12 questions were not enough
# to tell.
#
# Return ONE of "SHIP", "HOLD", "REJECT", and a reason a manager can read:
#     return "HOLD", "nothing is detectably better, so there is nothing to defend"
# ===========================================================================

# ---- WORKED EXAMPLE -------------------------------------------------------
def example_decide_on_task_success(cmp):
    """'Ship if task success went up, reject if it went down, otherwise hold.'

    How it reads cmp:      one metric's direction.
    What is wrong with it: it never looks at cmp["regressions"]. A candidate that is
    better on average but breaks a question that used to work would still SHIP. It
    also never ships a candidate that is simply cheaper.
    """
    d = cmp["metrics"]["task success"]["direction"]
    if d == "better":
        return "SHIP", "task success is detectably better"
    if d == "worse":
        return "REJECT", "task success is detectably worse"
    return "HOLD", "task success did not detectably change"


# ---- YOURS ----------------------------------------------------------------
# Questions to answer, IN THIS ORDER, before you write a line:
#   1. Did it break any question that used to work?      cmp["regressions"]
#   2. Is any quality metric detectably worse?            "task success", "right agents,
#                                                           right order", "right tools"
#   3. Did it fix something?                              cmp["fixed"]
#   4. If quality is tied: is it detectably cheaper?      "cost per run ($)"
#   5. None of the above: is there anything to defend?
def decide(cmp):
    raise NotImplementedError("write decide")


# ===========================================================================
# PART 4 -- WHEN DO YOU RAISE THE ALARM?                     (hands-on 4, 10 min)
#
# The plant runs for a week. Every morning the dashboard shows yesterday's numbers.
# Real values -- `usual` is version A's 24 runs, `today` is day 1 of the week:
#
#   usual = {"requests": 24, "task_success": (18, 24), "approval": (6, 8),
#            "work_orders": 6, "cost_usd": 0.68, "p90_latency_s": 30.3}
#   today = {"requests": 24, "task_success": (20, 24), "approval": (3, 5),
#            "work_orders": 3, "cost_usd": 0.62, "p90_latency_s": 29.6}
#
#   task_success and approval are (k, n): k passed out of n that counted.
#       k, n = today["approval"]        rate = k / n       (check n > 0 first)
#
# Return a list of alert messages. An empty list means "all fine, let people sleep".
# Every alert wakes somebody up. An alert that fires on a normal day teaches people
# to ignore it.
# ===========================================================================

# ---- WORKED EXAMPLE -------------------------------------------------------
def example_alert_on_cost(today, usual) -> list:
    """'Alert when today's cost is more than 50% above usual.'

    How it reads the day:  one number, compared with usual, with a margin for wobble.
    What is wrong with it: nothing about cost changes this week, so it stays quiet all
    seven days -- including the days something DID change. Right shape, wrong number.
    """
    if today["cost_usd"] > 1.5 * usual["cost_usd"]:
        return [f"cost ${today['cost_usd']:.2f}, usually ${usual['cost_usd']:.2f}"]
    return []


# ---- YOURS ----------------------------------------------------------------
# Before you write it, run the WEEK cell and answer on paper:
#   - Which number moved, and on which day?
#   - Which numbers jumped around on days when NOTHING changed? (Do not alert on those
#     with a tight threshold -- that is how you get a false alarm.)
#   - How many requests does a rate rest on? 1 of 3 is not the same news as 8 of 24.
def alert(today, usual) -> list:
    raise NotImplementedError("write alert")


# ===========================================================================
# Run this file to see every worked example on the real data.
# ===========================================================================
if __name__ == "__main__":
    import pipeline12 as pl
    import versions12 as vs
    from bench7 import tracing_off

    with tracing_off(True):
        A = pl.evaluate_all(vs.load("A"))
        B = pl.evaluate_all(vs.load("B"))
        C = pl.evaluate_all(vs.load("C"))
        week = [pl.day_metrics(d) for d in vs.production_week()]
    usual = pl.day_metrics([{**r, "day": 0} for r in A])

    print("PART 1  example_resolved_if_closed on version A:")
    print("   ", pl.fmt(pl.rate(A, example_resolved_if_closed)), "  <- true for everything")

    print("\nPART 2  example_no_repeats, question by question on version A:")
    held = pl.suite(A, example_no_repeats)
    print("   ", "  ".join(f"{q}:{'held' if v[0] else 'FAILS'}" for q, v in sorted(held.items())))
    print("    HW-012 evidence:", next(example_no_repeats(r)[1] for r in A if r["row_id"] == "HW-012"))
    print("    -> it holds on HW-012, the known bug. It cannot catch it.")

    print("\nPART 3  example_decide_on_task_success:")
    for name, cand in (("B", B), ("C", C)):
        d, why = example_decide_on_task_success(pl.compare(A, cand))
        print(f"    A -> {name}: {d:6s} {why}")

    print("\nPART 4  example_alert_on_cost, day by day:")
    for d in week:
        print(f"    day {d['day']}: {example_alert_on_cost(d, usual) or 'quiet'}")
    print("\nNow write yours, then:  python session-12/screen_my_release.py")
