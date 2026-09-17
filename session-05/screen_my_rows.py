#!/usr/bin/env python3
"""
Screen the rows in benchmark_rows.py.  Two seconds, no API key, no cost.

    python screen_my_rows.py                    # your two rows
    python screen_my_rows.py --worked           # the three worked examples too
    python screen_my_rows.py --pool             # what would be pushed, with author stamps
    python screen_my_rows.py --file rows.py     # SOMEONE ELSE'S rows (Hands-on 2)

Exit 0 = every row ships.  Exit 1 = at least one row is RETIRE or BROKEN, and
the output names which bet it failed to make.

SCREENING A ROW YOU DID NOT WRITE
---------------------------------
`--file` points the screener at another pair's `benchmark_rows.py`. That is
Hands-on 2, and it is a different exercise from Hands-on 1 on purpose.

Predicting your OWN row is contaminated: you know what you meant it to catch, so
a HIT proves you can remember your own intent. Predicting a STRANGER'S row is the
real skill -- you have to read the fields and work out what bet they actually made,
which is not always the bet they thought they were making. That is what reviewing
a colleague's benchmark is, and it is where most of the surprises live.

Edit the `predict` list on their rows to YOUR guess before you run it. Their rows
are not modified on disk; you are working on a copy.

WHAT "SHIPS" DOES NOT MEAN
--------------------------
It means your row's own expectations catch at least one failure shape this
course has already measured.  It does NOT mean the row is good, and it does not
check your ground truth -- a `must_contain` that is simply wrong passes this
screen by construction and only a live run will catch it.  The screen raises the
floor.  It does not prove the row is right.
"""

from __future__ import annotations


import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first
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


def report(screens, label: str, whose: str = "your") -> bool:
    print(BANNER.replace("your row", "this row" if whose != "your" else "your row"))
    print(f"  {label}\n")
    ok = row_screen.print_screen(screens, verbose=False, whose=whose)

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
    if todo and whose == "your":
        print(f"\n  {len(todo)} row(s) still say TODO. Those are placeholders, not rows.")
        ok = False

    print("\n" + "=" * 78)
    print("  ALL ROWS SHIP" if ok else "  NOT READY -- see above")
    print("=" * 78 + "\n")
    return ok


def load_rows_from(path: str):
    """Load MY_ROWS out of another pair's file. Returns None (having said why) if
    the file is unusable -- at minute 35 an explanation beats a traceback."""
    import importlib.util
    import os

    if not os.path.exists(path):
        print(f"\nNo such file: {path}")
        print("Ask them for their benchmark_rows.py, or drop it in this folder as")
        print("partner_rows.py and run:  python screen_my_rows.py --file partner_rows.py")
        return None
    try:
        spec = importlib.util.spec_from_file_location("_partner", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)            # type: ignore[union-attr]
    except Exception as exc:
        print(f"\nCould not load {path}: {type(exc).__name__}: {exc}")
        print("Their file has a syntax error. Tell them -- that is a finding too.")
        return None

    rows = [r for r in getattr(mod, "MY_ROWS", [])
            if "TODO" not in str(r["inputs"]["question"])]
    if not rows:
        print(f"\n{path} has no finished rows yet. Swap with a different pair.")
        return None

    author = getattr(mod, "AUTHOR", "unknown")
    print(f"\n  screening {len(rows)} row(s) by: {author}")
    if any(r.get("predict") for r in rows):
        print("  NOTE: their `predict` lists are still in the file. Overwrite them")
        print("  with YOUR guess before you run this, or you are grading their bet,")
        print("  not making your own.")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worked", action="store_true", help="include the worked examples")
    ap.add_argument("--pool", action="store_true", help="screen the author-stamped rows")
    ap.add_argument("--file", metavar="PATH",
                    help="screen ANOTHER pair's benchmark_rows.py (Hands-on 2)")
    args = ap.parse_args()

    if args.file:
        rows, label = load_rows_from(args.file), f"rows from {args.file}"
        if rows is None:
            return 1
    elif args.pool:
        rows, label = benchmark_rows.rows_for_pool(), "your rows, as they would be pushed"
    elif args.worked:
        rows = list(benchmark_rows.WORKED) + list(benchmark_rows.MY_ROWS)
        label = "the three worked examples, then your two"
    else:
        rows, label = list(benchmark_rows.MY_ROWS), "your two rows"

    if not rows:
        print("benchmark_rows.MY_ROWS is empty. Write a row first.")
        return 1
    whose = "their" if args.file else "your"
    return 0 if report(row_screen.screen_all(rows), label, whose) else 1


if __name__ == "__main__":
    sys.exit(main())
