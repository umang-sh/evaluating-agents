"""
Session 9 homework — BREAK THE TRAJECTORY JUDGE.

This is the only file you edit. Two blanks, both below.

    python my_trap9.py --show          the trajectory you are starting from
    python my_trap9.py --judges        what each judge is looking for
    python screen_my_trap.py           run it (2 model calls, on your key)

----------------------------------------------------------------------------
WHY THIS EXISTS
----------------------------------------------------------------------------
In class we measured three reference-free judges against five seeded arms and reported
which of them separate by more than they wobble. Separation is measured against flaws
**the instructor built**. It says nothing about flaws **somebody designed to slip past**.

Session 8 ended on exactly this: all four instructor attacks fooled both certified judges,
first try. The fix for a judge is a new set to fail on. You are that set.

----------------------------------------------------------------------------
YOUR JOB
----------------------------------------------------------------------------
Pick ONE judge. Then write `trap()` so that it returns a trajectory which is genuinely
broken in that judge's own area -- and which the judge nevertheless calls SOUND.

    delegation_fit        a subtask given to an agent whose job does not cover it
    handoff_sufficiency   an agent not handed something it needed
    path_efficiency       an invocation that added nothing

**"Genuinely broken" is the whole exercise.** A trajectory that is fine is not an attack; it
is a correct SOUND verdict and the screener will say so. The trap has to be real damage that
reads as reasonable.

You may change `plan`, `agent_calls` and `handoffs` however you like. You may not change
which judge is being asked, and you may not edit the rubric -- attacking the prompt is not
attacking the judge.

COST: `screen_my_trap.py` makes exactly **2 model calls per run** -- one on the untouched
trajectory (the baseline, re-measured every time so you are never comparing against a
remembered number) and one on yours. It calls ONE judge, not all three. Run it as often as
you like; five attempts is ten calls.
"""

from __future__ import annotations

import copy

# ===========================================================================
# BLANK 1 of 2 — which judge are you attacking?
#
#   "delegation_fit" | "handoff_sufficiency" | "path_efficiency"
# ===========================================================================
TARGET: str | None = None

# ===========================================================================
# BLANK 2 of 2 — your prediction, BEFORE you run it.
#
#   True   you think the judge will be FOOLED (call your broken path SOUND)
#   False  you think it will catch you
#
# Write it down first. A prediction you make after seeing the result is not a prediction,
# and the gap between what you expected and what happened is the thing worth reporting.
# ===========================================================================
PREDICT_FOOLED: bool | None = None


def trap(traj: dict) -> dict:
    """Return a trajectory that is really broken, and that your judge will pass.

    `traj` is a dict with these keys — mutate the copy and return it:

        question     str            the engineer's request (leave it alone)
        plan         list of dicts  [{"agent": ..., "subtask": ...}, ...]
        agent_calls  list of str    ['planner', 'diagnostics', ...]
        handoffs     list of dicts  [{"from":..., "to":..., "payload":...}, ...]

    Print it first:  python my_trap9.py --show

    A worked example of the SHAPE (this one is not an attack — it breaks the path so
    obviously that every judge catches it, which is the opposite of what you want):

        t = copy.deepcopy(traj)
        t["agent_calls"] = ["planner", "documentation", "documentation"]
        return t

    Your version has to be subtler than that.
    """
    t = copy.deepcopy(traj)
    # ---- your attack goes here ----
    return t


# ===========================================================================
# Nothing below here needs editing.
# ===========================================================================
JUDGE_NAMES = ("delegation_fit", "handoff_sufficiency", "path_efficiency")

# The trajectory everyone starts from. One request, unmodified, four agents.
START_ROW, START_ARM = "HW-001", "healthy"


def unfilled() -> list[str]:
    out = []
    if TARGET is None:
        out.append("TARGET")
    if PREDICT_FOOLED is None:
        out.append("PREDICT_FOOLED")
    return out


def complaints() -> list[str]:
    bad = []
    if TARGET is not None and TARGET not in JUDGE_NAMES:
        bad.append(f"TARGET {TARGET!r} is not one of {JUDGE_NAMES}")
    if PREDICT_FOOLED is not None and not isinstance(PREDICT_FOOLED, bool):
        bad.append("PREDICT_FOOLED should be True or False")
    return bad


def _main() -> int:
    import argparse
    import _path  # noqa: F401
    import traj9

    ap = argparse.ArgumentParser(description="Session 9 homework")
    ap.add_argument("--show", action="store_true",
                    help="print the trajectory you are starting from")
    ap.add_argument("--mine", action="store_true",
                    help="print YOUR trapped trajectory, so you can read what you built")
    ap.add_argument("--judges", action="store_true",
                    help="what each judge is looking for")
    a = ap.parse_args()

    base = traj9.trajectory(START_ROW, START_ARM)
    if a.show:
        print(traj9.render(base)); return 0
    if a.mine:
        print(traj9.render(trap(base))); return 0
    if a.judges:
        import judge9
        for k in JUDGE_NAMES:
            print(f"--- {k}\n    {judge9.RUBRICS[k]['asks']}\n")
        return 0

    left = unfilled()
    print(f"my_trap9 — target {TARGET or '(unset)'}, "
          f"predicted {'FOOLED' if PREDICT_FOOLED else 'caught' if PREDICT_FOOLED is not None else '(unset)'}")
    if left:
        print("  still blank: " + ", ".join(left))
        print("  read the trajectory first:  python my_trap9.py --show")
    else:
        print("  filled in. Now run:  python screen_my_trap.py")
    for c in complaints():
        print("  !!", c)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
