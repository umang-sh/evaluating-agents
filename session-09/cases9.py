"""
Session 9 — the six hands-on cases, with their arms hidden.

WHY THIS FILE IS SEPARATE FROM THE ANSWER KEY
----------------------------------------------
Session 8's sweep check [4] caught an `import judge_seeds8` being added to
`my_attack8.py` -- the student file reaching into the answer key. The rule that came out
of it: a student file imports nothing that knows the answer.

So the mapping from case letter to (row, arm) lives HERE, and `my_path9.py` imports only
`case_outputs()`, which hands back a trajectory with no arm label on it. The arm names
are in `CASES` below, which the SCREENER imports and the student file does not.

That is a soft boundary -- a student can open this file. So could they open
`judge_seeds8.py`. The point is that nothing they are asked to run does it for them, and
that reading the answer is a decision rather than an accident.

THE SPREAD IS DELIBERATELY UNEVEN
----------------------------------
One healthy, two efficiency, two handoff, one delegation. Session 7's hands-on put one
trap per row and most pairs solved it by counting. A student who assumes one of each
here gets two wrong, and the run sheet says to expect that.

`lost_handoff` gets two of the six because it is the arm this session predicts the MODEL
judge will miss -- so the interesting comparison at the end of the hands-on is the
room's hit rate on B and E against the judge's.
"""

from __future__ import annotations

import _path  # noqa: F401

import traj9

__version__ = "s9-2026-09-20a"

# letter -> (row_id, arm). The screener reads this; my_path9.py must not.
CASES: dict[str, tuple[str, str]] = {
    "A": ("HW-002", "redundant_call"),
    "B": ("HW-007", "lost_handoff"),
    "C": ("HW-005", "healthy"),
    "D": ("HW-003", "wrong_delegation"),
    "E": ("HW-002", "lost_handoff"),
    "F": ("HW-012", "delegation_loop"),
}

# Which of the three words the student should have written, per arm.
FAULT_OF = {
    "healthy": None,
    "wrong_delegation": "delegation",
    "lost_handoff": "handoff",
    "redundant_call": "efficiency",
    "delegation_loop": "efficiency",
}


def case_outputs(letter: str) -> dict:
    """The trajectory for one case, with no arm label attached."""
    row, arm = CASES[letter.upper()]
    out = dict(traj9.trajectory(row, arm))
    out.pop("arm", None)          # the label is the answer; do not ship it
    out.pop("row_id", None)
    return out


def expected(letter: str) -> tuple[str, str | None]:
    """(verdict, fault) the answer key says for this case."""
    _, arm = CASES[letter.upper()]
    fault = FAULT_OF[arm]
    return ("SOUND", None) if fault is None else ("UNSOUND", fault)


if __name__ == "__main__":
    print(f"cases9 {__version__} — {len(CASES)} cases")
    for c, (row, arm) in CASES.items():
        v, f = expected(c)
        print(f"  {c}  {row} {arm:17s} -> {v}{'/' + f if f else ''}")
