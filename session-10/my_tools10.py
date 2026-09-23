"""
THE ONE FILE YOU EDIT TODAY.

You are writing an ANSWER KEY for two questions: a record of which tools a correct run
would have had to call, and what it would have had to call them with.

Write it from the QUESTION. Do not run anything first and copy what happened -- a key
copied from a transcript can only ever agree with itself, and it will pass every run
including the broken ones.

HOW TO FILL A ROW IN
---------------------
    must_call    {agent: {tool names}}
                 Tools this agent HAS to call at least once. Ask yourself: what would a
                 competent engineer have to look up before they could answer this?

    forbidden    {agent: {tool names}}
                 Tools this request rules OUT. Most rows leave this empty. Use it when
                 the engineer has said, in plain English, not to do something -- "just
                 the spec, I do not need a diagnosis".

    must_cover   {argument name: [values]}
                 Values that must be passed to SOME tool, by any agent, in any call.
                 This is the one that catches a run which called all the right tools and
                 pointed them at the wrong thing.

    match_mode   "subset"  at least these tools; extra ones are allowed
                 "exact"   these tools and no others

WHICH AGENT HOLDS WHICH TOOL
-----------------------------
    diagnostics      equipment_kb · sensor_history · maintenance_history
    documentation    manual_search · equipment_kb
    maintenance      parts_inventory · maintenance_history

Naming a tool an agent does not hold is refused when you screen your answer, with the
reason. That is not a trick; it is the same check the real evaluator runs.

WHEN YOU HAVE FILLED BOTH IN
-----------------------------
    python session-10/screen_my_tools.py

It tells you, for each row, whether your key is DISCRIMINATING (it catches a broken run
AND leaves a healthy one alone), DECORATIVE (it never fires on anything, so it is not
testing anything), or WRONG (it fires on the healthy run, which means it would raise a
false alarm on every good run in production).

No model is called. It costs nothing and you can run it as many times as you like.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

# ===========================================================================
# WORKED EXAMPLE -- already filled in. Read this one before you write yours.
#
# HW-002: "The rinse-water pump is making a gravelly noise and discharge
#          pressure is down. Do we have the parts to fix it?"
#
# Reasoning, clause by clause:
#   "making a gravelly noise ... pressure is down"
#        Something is wrong NOW, so the current readings have to be read.
#                                                     -> sensor_history
#   ...and a reading on its own means nothing. 4.2 mm/s is fine on one machine and an
#        alarm on another, so you need the limits it is judged against.
#                                                     -> equipment_kb
#   "do we have the PARTS to fix it"
#        A stock question. It cannot be answered without looking in the store.
#                                                     -> parts_inventory
#   ...and you cannot look up a part until you know which part, which is what the
#        procedure names.                             -> manual_search
#   The question names one machine, the rinse-water pump, so every lookup should be
#        pointed at it.                               -> must_cover machine_id
#
# Nothing is ruled out, and an agent that looks up more than this has not failed --
# so match_mode is "subset".
# ===========================================================================
WORKED_EXAMPLE = {
    "id": "HW-002",
    "must_call": {
        "diagnostics": {"sensor_history", "equipment_kb"},
        "documentation": {"manual_search"},
        "maintenance": {"parts_inventory"},
    },
    "forbidden": {},
    "must_cover": {"machine_id": ["RINSE-PUMP"]},
    "match_mode": "subset",
}


# ===========================================================================
# YOUR TURN -- ROW ONE
#
# HW-003: "The filler drive keeps tripping on overcurrent at shift start.
#          Can it wait until the planned stop?"
#
# Read the second sentence twice. It is doing more work than the first one, and
# exactly one of the five tools can answer it.
# ===========================================================================
MY_ROW_1 = {
    "id": "HW-003",
    "must_call": {
        # "agent": {"tool", "tool"},
    },
    "forbidden": {},
    "must_cover": {
        # "machine_id": ["..."],
    },
    "match_mode": "subset",
}


# ===========================================================================
# YOUR TURN -- ROW TWO
#
# HW-006: "Doing the morning walkdown -- check the filler infeed conveyor and
#          the air-knife blower and tell me which needs attention first."
#
# Count the machines in that sentence before you write anything.
# ===========================================================================
MY_ROW_2 = {
    "id": "HW-006",
    "must_call": {
    },
    "forbidden": {},
    "must_cover": {
    },
    "match_mode": "subset",
}


ROWS = [MY_ROW_1, MY_ROW_2]

if __name__ == "__main__":
    for r in ROWS:
        filled = bool(r["must_call"]) or bool(r["must_cover"])
        print(f"{r['id']}: {'filled in' if filled else 'still empty'}")
    print("\nnow run:  python session-10/screen_my_tools.py")
