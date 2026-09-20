"""
Session 9 — mark your own hands-on. Free, offline, instant.

    python screen_my_path.py
    python screen_my_path.py --explain      also say WHY each case is what it is

COST: ZERO MODEL CALLS. Everything here is `coord_eval7` (code, deterministic) and a
dictionary comparison. Session 8's `screen_my_attack.py` cost eight live calls per run
and four files said it cost one; this one costs nothing and says so in a line the run
sheet quotes from `traj_bench9.calls_for()` rather than typing.

It refuses to run until `my_path9.py` is filled in, and exits 2 when it does -- the same
contract Session 8 used, so the sweep can check it.
"""

from __future__ import annotations

import _path  # noqa: F401

import argparse
import sys

import cases9
import coord_eval7
import my_path9
import traj9
from delegation_rows7 import BY_ID

__version__ = "s9-2026-09-20a"


def _part1(explain: bool) -> tuple[int, int, int]:
    """Your verdicts against the answer key. Returns (verdict_right, fault_right, n)."""
    print("PART 1 — you judged six paths with no key\n")
    v_right = f_right = 0
    for c in my_path9.CASES:
        got_v, got_f = my_path9.PREDICT[c]
        want_v, want_f = cases9.expected(c)
        row, arm = cases9.CASES[c]
        v_ok = got_v == want_v
        f_ok = (got_f == want_f)
        v_right += v_ok
        f_right += f_ok
        mark = "." if (v_ok and f_ok) else ("~" if v_ok else "X")
        got = f"{got_v}{'/' + got_f if got_f else ''}"
        want = f"{want_v}{'/' + want_f if want_f else ''}"
        print(f"  {mark} {c}  you said {got:22s} key says {want:22s} ({row} {arm})")
        if explain:
            print(f"        {EXPLAIN[arm]}")
    n = len(my_path9.CASES)
    print(f"\n  verdict right {v_right}/{n}   verdict AND fault right {f_right}/{n}")
    return v_right, f_right, n


EXPLAIN = {
    "healthy": "nothing wrong. A three-agent path for a three-part request.",
    "wrong_delegation": "the planner handed a 'diagnose' subtask to documentation, "
                        "whose job is manual lookup.",
    "lost_handoff": "agent_calls is IDENTICAL to healthy and so is the final answer. "
                    "The diagnostics -> documentation payload lost its "
                    "MACHINE:/FAULT_CODE: tail, so documentation was asked to find a "
                    "procedure for a fault it was never told.",
    "redundant_call": "an agent ran twice for the SAME subtask. Compare HW-006 healthy, "
                      "which runs diagnostics twice for two DIFFERENT machines and is "
                      "correct.",
    "delegation_loop": "the path revisits agents with nothing new each time.",
}


def _part2() -> int:
    """Your key, run against the live trajectory, then compared with the shipped row."""
    print("\n\nPART 2 — the key nobody wrote\n")
    agreed = 0
    for row_id in my_path9.KEY_ROWS:
        mine = list(my_path9.MY_KEY[row_id])
        shipped = BY_ID[row_id]
        live = traj9.trajectory(row_id, "healthy", phase="comparison")
        actual = list(live.get("agent_calls") or [])

        my_ref = {"expected_agents": mine, "expected_order": "strict",
                  "forbidden_agents": []}
        my_verdict = coord_eval7.delegation_accuracy(live, my_ref)
        shipped_verdict = coord_eval7.delegation_accuracy(live, shipped)
        same = (my_verdict["score"] == shipped_verdict["score"])
        agreed += same

        print(f"  {row_id}   the live run actually ran:")
        print(f"      {' -> '.join(actual)}")
        print(f"    your key:    {' -> '.join(mine)}")
        print(f"    shipped key: {' -> '.join(shipped['expected_agents'])}"
              + (f"   forbidden: {', '.join(shipped['forbidden_agents'])}"
                 if shipped.get("forbidden_agents") else ""))
        print(f"    with YOUR key this run    {'PASSES' if my_verdict['score'] else 'FAILS'}"
              f"  — {my_verdict['comment']}")
        print(f"    with the SHIPPED key it   "
              f"{'PASSES' if shipped_verdict['score'] else 'FAILS'}"
              f"  — {shipped_verdict['comment']}")
        print(f"    -> same verdict: {'YES' if same else 'NO'}")
        if mine != list(shipped["expected_agents"]):
            print(f"    (your key differs from the shipped one. That is allowed, and it "
                  f"is the point:\n     the verdict on this run was decided by whoever "
                  f"wrote the row.)")
        print()
    return agreed


def main() -> int:
    ap = argparse.ArgumentParser(description="Session 9 — mark your hands-on")
    ap.add_argument("--explain", action="store_true")
    a = ap.parse_args()

    left = my_path9.unfilled()
    if left:
        print("screen_my_path: my_path9.py is not filled in yet.\n")
        print("  still blank: " + ", ".join(left))
        print("\n  PREDICT holds your six verdicts; MY_KEY holds the two agent lists.")
        print("  Read the cases first:  python my_path9.py --show")
        return 2
    bad = my_path9.complaints()
    if bad:
        print("screen_my_path: PREDICT or MY_KEY is filled in but malformed.\n")
        for b in bad:
            print("  !!", b)
        return 2

    print(f"screen_my_path {__version__}   0 model calls\n")
    v_right, f_right, n = _part1(a.explain)
    agreed = _part2()

    print("=" * 74)
    print(f"  code found every one of these with a delegation row in hand.")
    print(f"  you found {f_right}/{n} without one.")
    print(f"  your two keys agreed with the shipped rows on {agreed}/"
          f"{len(my_path9.KEY_ROWS)} verdicts.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
