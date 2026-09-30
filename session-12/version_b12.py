"""
Session 12 -- VERSION B of the maintenance assistant. Read this file; do not edit it.

WHAT VERSION A DID WRONG
------------------------
One real question, run twice, went wrong the same way both times:

    HW-012  "Compressor discharge is sitting at 88 C. Is that within limits or do I
             need to act?"

    what the question needs   planner -> diagnostics -> documentation
    what version A did        planner -> documentation -> diagnostics -> maintenance

Two mistakes: documentation ran BEFORE diagnostics, and a maintenance agent ran that
nobody asked for. Read the planner's rule 1a in plant/plant_agents7.py and you can see
where both came from. It says: "whether something is within limits ... call
documentation BEFORE maintenance." The planner did exactly what it was told.

WHAT VERSION B CHANGES -- ONE THING
-----------------------------------
Rule 1a of the planner's instructions is replaced, and one rule is added. Nothing else
changes: same model, same three specialists, same tools, same 12 questions.

    rule 1a (new)  a "within limits?" question needs diagnostics then documentation,
                   and no maintenance
    rule 5  (new)  when both diagnostics and documentation run, diagnostics goes first

A prompt change is the cheapest kind of change there is. It is also the kind that
fixes one question and quietly breaks another. That is what the regression suite is for.

HOW VERSION B IS RUN (instructor only -- it calls a model)
-----------------------------------------------------------
    python session-12/capture12.py          # 12 questions x 2 repeats, about $0.70

The capture swaps the planner's instructions IN MEMORY for the length of the run, with
`use_version_b()` below. plant/plant_agents7.py is never edited, so version A is
still exactly what is on disk.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first
from contextlib import contextmanager

import plant_agents7

__version__ = "s12-2026-09-29a"

OLD_RULE_1A = """  1a. But do not skip documentation when the answer depends on it. If the
     request asks what to DO about a fault, or whether something is within
     limits, or how long a job takes, the manual is what settles it -- call
     documentation BEFORE maintenance. A repair recommended without the
     procedure behind it is a guess with a work order attached."""

NEW_RULE_1A = """  1a. But do not skip documentation when the answer depends on it. If the
     request asks what to DO about a fault, or how long a job takes, the
     manual is what settles it -- call documentation BEFORE maintenance. A
     repair recommended without the procedure behind it is a guess with a
     work order attached. If the request only asks whether a reading is
     within limits, call diagnostics and then documentation, and do NOT call
     maintenance: nobody has asked what to do."""

OLD_RULE_4_END = """  4. Resolve the machine id yourself and put it in every subtask. A specialist
     cannot see the original request."""

NEW_RULE_5 = OLD_RULE_4_END + """
  5. When both diagnostics and documentation run, diagnostics goes first.
     Documentation looks up what diagnostics found; it cannot look up a fault
     that has not been found yet."""

PROMPT_A = plant_agents7.PLANNER_PROMPT
assert OLD_RULE_1A in PROMPT_A, "plant_agents7's rule 1a changed -- version B no longer applies"
assert OLD_RULE_4_END in PROMPT_A, "plant_agents7's rule 4 changed -- version B no longer applies"
PROMPT_B = PROMPT_A.replace(OLD_RULE_1A, NEW_RULE_1A).replace(OLD_RULE_4_END, NEW_RULE_5)


@contextmanager
def use_version_b():
    """Run the planner with version B's instructions inside this block, and put
    version A's back afterwards -- even if the block raises."""
    plant_agents7.PLANNER_PROMPT = PROMPT_B
    try:
        yield
    finally:
        plant_agents7.PLANNER_PROMPT = PROMPT_A


def diff() -> str:
    """The change, as lines removed (-) and added (+)."""
    import difflib
    return "\n".join(l for l in difflib.unified_diff(PROMPT_A.splitlines(), PROMPT_B.splitlines(),
                                                     "version A", "version B", lineterm="", n=0)
                     if not l.startswith("@@"))


if __name__ == "__main__":
    print(diff())
