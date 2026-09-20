"""
Session 9 hands-on — BE THE JUDGE WITH NO KEY, THEN WRITE THE KEY.

This is the only file you edit. Two blanks, both below. No model calls, no API key,
nothing to install, and it works the same on Anthropic, OpenAI or Gemini because it
never talks to any of them. Run the screener as often as you like; it is free.

    python my_path9.py --example      A FULLY WORKED EXAMPLE. Start here.
    python my_path9.py --show         read the six cases
    python my_path9.py --show C       read one case in full
    python my_path9.py --keys         see the two runs you write a key for
    python screen_my_path.py          mark yourself

============================================================================
WHAT YOU ARE LOOKING AT
============================================================================
Four agents answer one engineer's request:

    planner         decides who does what
    diagnostics     works out what is wrong with a machine
    documentation   finds the manual section that applies
    maintenance     recommends what to actually do

A **trajectory** is the record of how they did it. Four parts, and you get all four:

    ENGINEER'S REQUEST     what was asked
    THE PLANNER'S PLAN     (agent, subtask) pairs, decided before anything ran
    AGENTS THAT RAN        the order they actually ran in, repeats included
    WHAT WAS HANDED        the exact text each agent passed to the next

What you do NOT get is the delegation row — the sheet that says what this request's
path SHOULD have been. In production nobody has written one. That is the point.

============================================================================
THE THREE THINGS THAT CAN BE WRONG, AND WHERE TO LOOK FOR EACH
============================================================================
Work through them in this order. They live in different parts of the trajectory, so
if you look in the right place you will not need to guess.

  "delegation"   -> LOOK AT: the plan.
                   Does each subtask sit with the agent whose job covers it?
                   A diagnosis handed to `documentation` is a delegation fault.
                   `documentation` asked for a manual section is not.

  "handoff"      -> LOOK AT: the payload text under WHAT WAS HANDED.
                   Could the receiving agent do its subtask with ONLY that text?
                   Watch for what is MISSING, not just what is wrong. A payload that
                   never names the machine or the fault leaves the next agent guessing.

  "efficiency"   -> LOOK AT: the plan and the agent list TOGETHER.
                   An agent may legitimately run twice — for two DIFFERENT subtasks.
                   Two calls for the SAME subtask is waste. So is a path that keeps
                   going back to agents that have nothing left to add.

  nothing wrong  -> "SOUND". One of the six is fine. Do not talk yourself out of it.

⚠ A SHORT PATH IS NOT AUTOMATICALLY WRONG. Some requests need one specialist. The
  planner deciding "this only needs documentation" is the planner doing its job, not
  a fault. Equally, a long path is not automatically thorough.

============================================================================
PART 1 — YOU ARE THE JUDGE, AND YOU DO NOT GET THE ANSWER KEY
============================================================================
`--show` prints six trajectories. For each, fill in a verdict and, if UNSOUND, which
of the three faults it is.

One case is healthy. The others are not, and **they are not evenly spread** — do not
assume one of each. Two of them share a fault.

============================================================================
PART 2 — NOW WRITE THE KEY YOU DID NOT GET
============================================================================
Two LIVE trajectories from real runs on 13 September. For each, write what you think
the path SHOULD have been: the agents, in order, starting with `planner`.

The screener then does two things with your list:
  1. runs Session 7's `delegation_accuracy` with YOUR key against the live run, and
  2. shows you the key that actually shipped in `delegation_rows7.py`.

You are not marked on matching the shipped row. You are being shown how much of the
verdict was decided by whoever wrote the row — which is the whole session.
"""

from __future__ import annotations

# ===========================================================================
# BLANK 1 of 2 — your verdicts. Replace every None.
#
# The shape is a two-item tuple:
#
#       ("SOUND",   None)            nothing wrong with this path
#       ("UNSOUND", "delegation")    ... or "handoff", or "efficiency"
#
# So a filled-in line looks exactly like one of these:
#
#       "A": ("UNSOUND", "handoff"),
#       "B": ("SOUND", None),
#
# Run `python my_path9.py --example` first — it walks two trajectories end to end
# and shows the reasoning that produces each answer.
# ===========================================================================
PREDICT: dict[str, tuple] = {
    "A": (None, None),
    "B": (None, None),
    "C": (None, None),
    "D": (None, None),
    "E": (None, None),
    "F": (None, None),
}

# ===========================================================================
# BLANK 2 of 2 — the key nobody wrote. Replace every None.
#
# The full list of agents, in the order you think they should have run, INCLUDING
# the planner. It is an ordinary Python list of strings:
#
#       "HW-0XX": ["planner", "diagnostics", "documentation", "maintenance"],
#
# and a shorter one is just as valid when the request does not need everybody:
#
#       "HW-0XX": ["planner", "documentation"],
#
# Read the request before you write the list — `python my_path9.py --keys` prints
# both of them in full. Ask yourself what the engineer actually wanted, not how many
# agents exist.
# ===========================================================================
MY_KEY: dict[str, list] = {
    "HW-004": None,
    "HW-012": None,
}


# ===========================================================================
# Nothing below here needs editing.
# ===========================================================================
CASES = ("A", "B", "C", "D", "E", "F")
KEY_ROWS = ("HW-004", "HW-012")

VALID_VERDICTS = ("SOUND", "UNSOUND")
VALID_FAULTS = ("delegation", "handoff", "efficiency")

# The worked example. HW-001 is deliberately NOT one of the six cases, so nothing here
# gives an answer away — check `cases9.py` if you want to confirm that yourself.
EXAMPLE_ROW = "HW-001"


def unfilled() -> list[str]:
    """What is still blank. The screener refuses to run while this is non-empty."""
    out = [f"PREDICT[{c!r}]" for c in CASES if PREDICT.get(c, (None, None))[0] is None]
    out += [f"MY_KEY[{r!r}]" for r in KEY_ROWS if not MY_KEY.get(r)]
    return out


def complaints() -> list[str]:
    """Shape problems in what you wrote -- caught here rather than in a traceback."""
    bad = []
    for c in CASES:
        v, f = PREDICT.get(c, (None, None))
        if v is None:
            continue
        if v not in VALID_VERDICTS:
            bad.append(f"PREDICT[{c!r}] verdict {v!r} is not one of {VALID_VERDICTS}")
        if v == "UNSOUND" and f not in VALID_FAULTS:
            bad.append(
                f"PREDICT[{c!r}] is UNSOUND but the fault {f!r} is not one of "
                f"{VALID_FAULTS}"
            )
        if v == "SOUND" and f is not None:
            bad.append(
                f"PREDICT[{c!r}] is SOUND, so the second slot should be None, not {f!r}"
            )
    for r in KEY_ROWS:
        k = MY_KEY.get(r)
        if k is None:
            continue
        if not isinstance(k, list) or not all(isinstance(x, str) for x in k):
            bad.append(f"MY_KEY[{r!r}] should be a list of agent names")
        elif not k or k[0] != "planner":
            bad.append(f"MY_KEY[{r!r}] should start with 'planner' -- it always runs")
        else:
            unknown = [
                a
                for a in k
                if a not in ("planner", "diagnostics", "documentation", "maintenance")
            ]
            if unknown:
                bad.append(f"MY_KEY[{r!r}] names agents that do not exist: {unknown}")
    return bad


# ---------------------------------------------------------------------------
# The worked example. Everything it needs is imported INSIDE the function, so this
# module still imports nothing that knows an answer (sweep9 check [4]).
# ---------------------------------------------------------------------------
def _example() -> None:
    import traj9

    good = traj9.trajectory(EXAMPLE_ROW, "healthy")
    bad = traj9.trajectory(EXAMPLE_ROW, "wrong_delegation")

    print("=" * 76)
    print("WORKED EXAMPLE 1 of 2 — a path with nothing wrong with it")
    print("=" * 76)
    print(traj9.render(good))
    print("""HOW TO READ IT

  DELEGATION?  Walk the plan. 'diagnose CONVEYOR' sits with diagnostics, whose job is
               working out what is wrong. 'procedure or criterion' sits with
               documentation, whose job is the manual. 'recommendation' sits with
               maintenance. Every subtask is with the agent that owns it.  -> fine

  HANDOFF?     Read each payload and ask whether the receiver could do its job with
               only that. documentation was handed the fault findings AND the machine
               and fault code. maintenance was handed the manual section. Nobody is
               working blind.                                               -> fine

  EFFICIENCY?  Three specialists, three distinct subtasks in the plan, each ran once.
               No agent is revisited.                                       -> fine

  ANSWER:      ("SOUND", None)
""")

    print("=" * 76)
    print("WORKED EXAMPLE 2 of 2 — the same request, one thing broken")
    print("=" * 76)
    print(traj9.render(bad))
    print("""HOW TO READ IT

  DELEGATION?  Walk the plan again. Step 1 is 'diagnose CONVEYOR' — working out what
               is wrong with a machine — and it has been handed to DOCUMENTATION,
               whose job is looking things up in the manual. That agent cannot do
               that subtask. It is in the wrong hands.                  -> THE FAULT

  HANDOFF?     Nothing was stripped out of a payload in transit. No fact went missing
               between one agent and the next.                              -> fine

               FAIR OBJECTION, and worth raising in the room: documentation was never
               handed a fault code, so how was it supposed to find the right section?
               True — but that follows from the wrong agent being asked in the first
               place, not from a payload losing something on the way. The answer key
               calls this one delegation. If you wrote "handoff" here, say so out loud:
               the three faults are not perfectly separable and the overlap is real.

  EFFICIENCY?  documentation runs twice here — but for two different subtasks, so on
               the plan that is not waste. Do not report this one.          -> fine

  ANSWER:      ("UNSOUND", "delegation")

  Notice what made it decidable: you compared the SUBTASK TEXT with the AGENT it was
  given to. Not the length of the path, not how many agents ran.
""")
    print("Now run:  python my_path9.py --show")


def _main() -> int:
    import argparse

    import _path  # noqa: F401
    import cases9
    import traj9

    ap = argparse.ArgumentParser(description="Session 9 hands-on")
    ap.add_argument(
        "--example",
        action="store_true",
        help="a fully worked example, start to finish. Start here.",
    )
    ap.add_argument(
        "--show",
        nargs="?",
        const="ALL",
        metavar="CASE",
        help="print the trajectories you are judging",
    )
    ap.add_argument(
        "--keys",
        action="store_true",
        help="print the two live runs you have to write a key for",
    )
    a = ap.parse_args()

    if a.example:
        _example()
        return 0

    if a.show:
        wanted = CASES if a.show == "ALL" else (a.show.upper(),)
        for c in wanted:
            if c not in CASES:
                print(f"no case {c!r}; have {', '.join(CASES)}")
                return 2
            print("=" * 76)
            print(f"CASE {c}")
            print("=" * 76)
            print(traj9.render(cases9.case_outputs(c)))
            print(f"  -> fill in PREDICT[{c!r}] in my_path9.py\n")
        return 0

    if a.keys:
        for row in KEY_ROWS:
            t = traj9.trajectory(row, "healthy", phase="comparison")
            print("=" * 76)
            print(f"{row} — a LIVE run, 13 Sep 2026")
            print("=" * 76)
            print(traj9.render(t))
            print(
                f"  The agents available are: planner, diagnostics, documentation, "
                f"maintenance."
            )
            print(f"  What SHOULD this path have been? Write it in MY_KEY[{row!r}].\n")
        return 0

    left = unfilled()
    print(f"my_path9 — {len(CASES)} cases, {len(KEY_ROWS)} keys")
    if left:
        print(f"  still blank: {', '.join(left)}")
        print("  worked example:  python my_path9.py --example")
        print("  read the cases:  python my_path9.py --show")
    else:
        print("  all filled in. Now run:  python screen_my_path.py")
    for c in complaints():
        print("  !!", c)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
