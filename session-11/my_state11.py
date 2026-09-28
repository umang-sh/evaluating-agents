"""
THE ONE FILE YOU EDIT TODAY.

You are writing STATE CHECKS: small functions that look at what a workflow remembered
while it ran, and say whether that memory was still true.

WHAT A CHECK LOOKS LIKE
-----------------------
Every check gets ONE finished run and returns two things:

    return ok, evidence

    ok        True  -> this run looks fine by your check
              False -> your check FIRED: something is wrong
    evidence  one short sentence saying what you saw. A person will read it and
              decide whether to believe you, so put the numbers in it.

TOOLS YOU CAN USE (all in workflow11.py -- open it, it is short)
-----------------------------------------------------------------
    final(run)            the agents' last state: a dict with
                          "cursor"   how many planned steps were done
                          "steps"    how many steps were taken in total (planner counts as 1)
                          "plan_len" how many steps the plan had
    snapshots(run)        the agents' state after EVERY node, as a list of those dicts
    agent_steps(run)      one entry per agent step: {"agent", "subtask", "report", ...}
    machines_named(text)  machine ids that appear in a piece of text, e.g. ["BLOWER"]
    machine_worked_on(step)   the machine that step actually worked on (or None)
    run["status_log"]     every status the workflow passed through, in order

WHEN YOU HAVE WRITTEN A CHECK
-----------------------------
    python session-11/screen_my_state.py

It runs every check against clean runs AND broken runs and tells you, per check:
    CATCHES IT   fires on the broken run it is meant for, quiet on every clean run
    MISSES IT    never fires on that broken run -- it is not testing what you think
    FALSE ALARM  fires on a CLEAN run -- in production people would stop reading it
    NOT WRITTEN  you have not written it yet

No model is called. It is free and you can run it as often as you like.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first
from workflow11 import agent_steps, final, machine_worked_on, machines_named, snapshots  # noqa: F401


# ===========================================================================
# WORKED EXAMPLE -- already written. Read it before you write your own.
#
# Question: did the approval workflow ever get an engineer's decision at all?
#   A run that reached AWAITING_APPROVAL must, at some point, be APPROVED or
#   REJECTED. If AWAITING_APPROVAL is in the log and neither decision is, the
#   workflow is stuck waiting for someone.
# ===========================================================================
def check_decided(run):
    log = run["status_log"]
    if "AWAITING_APPROVAL" in log and not ({"APPROVED", "REJECTED"} & set(log)):
        return False, f"waited for approval and never got a decision: {' -> '.join(log)}"
    return True, "every approval request got a decision"


# ===========================================================================
# PART 1 (Four work orders) -- TWO CHECKS
# ===========================================================================

def check_finished(run):
    """Did the agents do EVERY step in their plan?

    final(run) gives you "cursor" (steps done) and "plan_len" (steps planned).
    A run that stopped early still writes an answer -- so the answer cannot tell you.
    """
    raise NotImplementedError("write check_finished")


def check_machine(run):
    """Did every agent work on the machine its subtask asked about?

    Loop over agent_steps(run). For each step:
        asked  = machines_named(step["subtask"])
        worked = machine_worked_on(step)
    If both are known and `worked` is not in `asked`, the check fires.
    Put the step number, the agent, `asked` and `worked` in the evidence.
    """
    raise NotImplementedError("write check_machine")


# ===========================================================================
# PART 2 (Approvals and work orders) -- A TABLE AND TWO CHECKS
# ===========================================================================

# LEGAL[a] = the set of statuses allowed to come straight after status a.
# The top four rows are done for you. Fill in the FIVE rows marked TODO.
# Think like the plant: what is allowed to happen after an engineer says no?
LEGAL = {
    "REQUESTED":         {"DIAGNOSED", "DOCUMENTED", "RECOMMENDED", "STALLED", "CLOSED"},
    "DIAGNOSED":         {"DIAGNOSED", "DOCUMENTED", "RECOMMENDED", "STALLED", "CLOSED"},
    "DOCUMENTED":        {"RECOMMENDED", "STALLED", "CLOSED"},
    "RECOMMENDED":       {"AWAITING_APPROVAL", "STALLED", "CLOSED"},
    "AWAITING_APPROVAL": set(),   # TODO
    "APPROVED":          set(),   # TODO
    "REJECTED":          set(),   # TODO
    "WORK_ORDER_ISSUED": set(),   # TODO
    "STALLED":           set(),   # nothing comes after a stall
    "CLOSED":            set(),   # nothing comes after closed
}


def check_transitions(run):
    """Is every move in run["status_log"] allowed by LEGAL?

    Walk the log in pairs:  for a, b in zip(log, log[1:]):
    If b is not in LEGAL[a], the check fires. Say which move in the evidence.
    """
    raise NotImplementedError("write check_transitions")


def check_counters(run):
    """In this graph `steps` should always be exactly `cursor + 1` -- the planner is
    step 1 and every agent step adds one to both. That is an INVARIANT: something
    that must be true after every single node.

    Loop over snapshots(run) and fire on the first snapshot where it is not true.
    """
    raise NotImplementedError("write check_counters")


# ===========================================================================
# PART 3 (Fail loudly) -- REDESIGN, NOT A CHECK
# ===========================================================================

def finish_status(plant_final):
    """The workflow asks this BEFORE sending anything to an engineer.

    Return "COMPLETE" if the agents finished their plan, or "STALLED" if they did not.
    A STALLED run stops there: no approval, no work order.

    plant_final is the same dict final(run) returns.
    Right now it says every run is complete. That is the bug.
    """
    return "COMPLETE"


if __name__ == "__main__":
    print("now run:  python session-11/screen_my_state.py")
