"""
Session 7 — four seeded COORDINATION failures.

WHY THESE ARE STATE INJECTORS AND NOT PROMPT EDITS
--------------------------------------------------
Session 2 broke agents by editing their prompts. That works when the failure
lives inside one agent. It does not work here: a wrong delegation, a dropped
handoff, a redundant invocation and a loop are all properties of the
COORDINATION, not of any single agent's reasoning. Injecting them into the
graph's state means the agents are untouched and provably not at fault -- so
when an evaluator fires, it is measuring coordination and nothing else.

It also means every seed reproduces exactly, every time. Session 5 spent three
attempts discovering it could not make an injection demo fire; that failure was
real and became the material, but it cost a block. A deterministic seed cannot
fail to reproduce, which is the right trade for the session whose entire
punchline is "the evaluator caught it".

THE HONEST OVERLAP, SAY IT IN CLASS
------------------------------------
A loop IS a kind of redundancy. `agent_no_redundancy` will fire on the loop
seed, and it should -- an agent invoked four times when the plan said once is
redundant whether or not it is cyclic. The seeds are not mutually exclusive and
the evaluators are not orthogonal. The gate is:

    every seed is caught by its designated evaluator,
    and no evaluator fires on the healthy pipeline.

NOT "exactly one evaluator fires", which would be a claim about a taxonomy
nobody has established. MAST (arXiv 2503.13657) is the published attempt at
that taxonomy and its categories overlap too.
"""

from __future__ import annotations

import re
from typing import Callable

SeedFn = Callable[[str, dict], dict]


# --------------------------------------------------------------------------
def wrong_delegation(stage: str, state: dict) -> dict:
    """WRONG DELEGATION — the subtask goes to an agent that cannot do it.

    Rewrites the first diagnostics step to documentation. The documentation
    agent has no sensor tools, so it will answer from the manual and produce
    something plausible and unfounded. Designated evaluator:
    `delegation_accuracy`.
    """
    if stage != "planner":
        return state
    plan = [dict(s) for s in state.get("plan", [])]
    for s in plan:
        if s["agent"] == "diagnostics":
            s["agent"] = "documentation"
            break
    return {**state, "plan": plan}


# --------------------------------------------------------------------------
def lost_handoff(stage: str, state: dict) -> dict:
    """LOST AT HANDOFF — the fault code never reaches the next agent.

    Strips the structured tail out of the diagnostics report as it is passed
    on. The report itself is untouched, so the FINAL ANSWER still contains the
    fault code and an outcome grader sees nothing wrong. Only an evaluator
    that reads what the RECEIVER was handed can catch this. Designated
    evaluator: `handoff_integrity`.

    This is the seed to put on a slide. It is the exact shape of Session 1's
    lesson, one level up: the output is right and the system is broken.
    """
    if stage != "diagnostics":
        return state
    ctx = state.get("context", "")
    stripped = re.sub(r"^\W*(FAULT_CODE|MACHINE)\s*:.*$", "", ctx, flags=re.M | re.I)
    return {**state, "context": stripped.strip()}


# --------------------------------------------------------------------------
def lost_section(stage: str, state: dict) -> dict:
    """LOST AT THE SECOND HANDOFF — the manual section never reaches maintenance.

    ADDED FOR SESSION 8. `lost_handoff` breaks the diagnostics -> documentation
    edge and ONLY that edge, so an assertion placed on documentation -> maintenance
    CANNOT FAIL and comes back DECORATIVE by construction. That is a property of the
    screener, not of the student's assertion, and it made HW-005 -- the row whose
    whole point is that the manual's balance criterion is what justifies doing
    nothing -- a partly decorative exercise.

    Same mechanism as `lost_handoff`, one edge later: the structured tail is
    stripped out of the documentation report as it is passed on. The final answer
    still contains the section id, so an outcome grader sees nothing wrong.
    Designated evaluator: `handoff_integrity`.

    DELIBERATELY NOT IN `BROKEN`. The four taught seeds are the four that were
    measured and put on slides 15 and 16 of Session 7. Adding a fifth arm to that
    matrix would change published numbers for a reason that has nothing to do with
    coordination. This seed exists for the screener, and `HANDOFF_SEEDS` is how the
    screener finds it.
    """
    if stage != "documentation":
        return state
    ctx = state.get("context", "")
    stripped = re.sub(r"^\W*(SECTION)\s*:.*$", "", ctx, flags=re.M | re.I)
    return {**state, "context": stripped.strip()}


# --------------------------------------------------------------------------
def redundant_call(stage: str, state: dict) -> dict:
    """REDUNDANT INVOCATION — the same agent is asked the same thing twice.

    Duplicates the first diagnostics step. Both calls return the same answer,
    so the output is unchanged and the bill is not. Designated evaluator:
    `agent_no_redundancy`.

    Session 6 row 8 is the precedent: the redundant version issued the same
    query twice, so a count-based regression rule passed it and only a waste
    evaluator caught it.
    """
    if stage != "planner":
        return state
    plan = [dict(s) for s in state.get("plan", [])]
    for i, s in enumerate(plan):
        if s["agent"] == "diagnostics":
            plan.insert(i + 1, dict(s))
            break
    return {**state, "plan": plan}


# --------------------------------------------------------------------------
def delegation_loop(stage: str, state: dict) -> dict:
    """LOOP — two agents hand work back and forth until the cap stops them.

    After documentation or maintenance runs, appends the other one to the plan
    again. The graph's MAX_STEPS seatbelt ends it; without the seatbelt this is
    the runaway-agent bill Session 9 will cost out. Designated evaluator:
    `no_delegation_loop`.
    """
    if stage not in ("documentation", "maintenance"):
        return state
    plan = [dict(s) for s in state.get("plan", [])]
    nxt = "maintenance" if stage == "documentation" else "documentation"
    plan.append({"agent": nxt, "subtask": f"follow up with {nxt}"})
    return {**state, "plan": plan}


# --------------------------------------------------------------------------
SEEDS: dict[str, dict] = {
    "healthy": {
        "fn": None,
        "designated": None,
        "one_line": "the control — nothing injected",
    },
    "wrong_delegation": {
        "fn": wrong_delegation,
        "designated": "delegation_accuracy",
        "one_line": "diagnostics work sent to the documentation agent",
    },
    "lost_handoff": {
        "fn": lost_handoff,
        "designated": "handoff_integrity",
        "one_line": "the fault code is dropped on the way to the next agent",
    },
    "redundant_call": {
        "fn": redundant_call,
        "designated": "agent_no_redundancy",
        "one_line": "diagnostics runs twice on the same subtask",
    },
    "lost_section": {
        "fn": lost_section,
        "designated": "handoff_integrity",
        "one_line": "the manual section is dropped on the way to maintenance",
        # Screener-only: not one of the four taught arms, so it never enters the
        # seed matrix and never changes a Session 7 number.
        "screener_only": True,
    },
    "delegation_loop": {
        "fn": delegation_loop,
        "designated": "no_delegation_loop",
        "one_line": "documentation and maintenance ping-pong until the cap",
    },
}

BROKEN = tuple(k for k in SEEDS if k != "healthy" and not SEEDS[k].get("screener_only"))

# Which seed breaks which handoff edge. `screen_my_handoffs.py` uses this to pick
# the right seed for the edge a student actually asserted on, instead of always
# using lost_handoff and returning DECORATIVE for the other edge.
HANDOFF_SEEDS: dict[str, str] = {
    "diagnostics->documentation": "lost_handoff",
    "documentation->maintenance": "lost_section",
}


def get(name: str) -> SeedFn | None:
    if name not in SEEDS:
        raise KeyError(f"unknown seed {name!r}; known: {list(SEEDS)}")
    return SEEDS[name]["fn"]


if __name__ == "__main__":
    from delegation_rows7 import BY_ID
    from plant_agents7 import run_pipeline

    row = BY_ID["HW-001"]
    print("HW-001:", row["request"][:60], "...\n")
    for name, meta in SEEDS.items():
        out = run_pipeline(row["request"], impl="stub", seed=get(name))
        path = " -> ".join(out["agent_calls"])
        print(f"{name:18s} {path}")
        if name == "lost_handoff":
            for h in out["handoffs"]:
                if h["to"] == "documentation":
                    got = "BEARING-WEAR" in h["payload"]
                    print(f"{'':18s}   documentation was handed BEARING-WEAR: {got}")
