#!/usr/bin/env python3
"""
Screen the rows in benchmark_rows.py.  Two seconds, no API key, no cost.

    python screen_my_rows.py            # your two rows
    python screen_my_rows.py --worked   # the three worked examples too
    python screen_my_rows.py --pool     # what would be pushed, with author stamps

Exit 0 = every row ships.  Exit 1 = at least one row is RETIRE or BROKEN, and
the output names which bet it failed to make.

WHAT "SHIPS" DOES NOT MEAN
--------------------------
It means your row's own expectations catch at least one failure shape this
course has already measured.  It does NOT mean the row is good, and it does not
check your ground truth -- a `must_contain` that is simply wrong passes this
screen by construction and only a live run will catch it.  The screen raises the
floor.  It does not prove the row is right.
"""

from __future__ import annotations

import argparse
import sys

import row_screen
import benchmark_rows


BANNER = """
==============================================================================
  ROW SCREEN -- can anything fail your row?
==============================================================================
"""

ADVICE = {
    "no_catch": (
        "Nothing fails it. Ask the concrete question, not the abstract one:\n"
        "      what would a BROKEN agent do differently on this question?\n"
        "      - answers from memory without searching  -> tighten must_contain\n"
        "      - reaches for a plausible wrong tool     -> fill forbidden_tools\n"
        "      - searches five times for one fact       -> lower max_tool_calls\n"
        "      - gets talked into a tool by a document  -> forbidden_tools again"),
    "broken": (
        "The healthy agent FAILS this row. That is a bug in the ROW, not a\n"
        "      discovery about the agent. Your reference output is wrong, or\n"
        "      your budget is below what the task honestly costs."),
}


def report(screens, label: str) -> bool:
    print(BANNER)
    print(f"  {label}\n")
    ok = row_screen.print_screen(screens, verbose=False)

    for s in screens:
        if s.verdict == "SHIPS":
            free = f"   (free: {sorted(s.free)})" if s.free else ""
            print(f"\n  SHIPS   {s.question[:66]}")
            print(f"      bets that pay off: {sorted(s.caught)}{free}")
            for w in s.warnings:
                print(f"      note: {w}")
        elif s.verdict == "RETIRE":
            print(f"\n  RETIRE  {s.question[:66]}")
            for w in s.warnings:
                print(f"      - {w}")
            print(f"      {ADVICE['no_catch']}")
        else:
            print(f"\n  BROKEN  {s.question[:66]}")
            print(f"      healthy fails: {s.healthy_failures}")
            print(f"      {ADVICE['broken']}")

    todo = [s for s in screens if "TODO" in s.question or s.category == "TODO"]
    if todo:
        print(f"\n  {len(todo)} row(s) still say TODO. Those are placeholders, not rows.")
        ok = False

    print("\n" + "=" * 78)
    print("  ALL ROWS SHIP" if ok else "  NOT READY -- see above")
    print("=" * 78 + "\n")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worked", action="store_true", help="include the worked examples")
    ap.add_argument("--pool", action="store_true", help="screen the author-stamped rows")
    args = ap.parse_args()

    if args.pool:
        rows, label = benchmark_rows.rows_for_pool(), "your rows, as they would be pushed"
    elif args.worked:
        rows = list(benchmark_rows.WORKED) + list(benchmark_rows.MY_ROWS)
        label = "the three worked examples, then your two"
    else:
        rows, label = list(benchmark_rows.MY_ROWS), "your two rows"

    if not rows:
        print("benchmark_rows.MY_ROWS is empty. Write a row first.")
        return 1
    return 0 if report(row_screen.screen_all(rows), label) else 1


if __name__ == "__main__":
    sys.exit(main())
