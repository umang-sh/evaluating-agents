"""
Screen the rubric you wrote in `my_judge10.py`.

    python session-10/screen_my_judge.py --offline   free. plumbing only, no key.
    python session-10/screen_my_judge.py --show      print the exact prompt, then stop.
    python session-10/screen_my_judge.py --live      20 model calls on YOUR key.

WHAT IT MEASURES, AND WHY BOTH NUMBERS MATTER
----------------------------------------------
Your rubric is run over the same twenty runs the class saw: four questions, five
versions of each. One version has nothing wrong with it. Four have one specific thing
broken.

    FALSE ALARMS   how many of the 4 clean runs your judge calls UNSOUND.
                   In class this was 4 of 4. Lower is better. Zero is the target.

    CATCHES        how many of the 4 dropped_lookup runs it calls UNSOUND.
                   That is the arm this judge is FOR: the agent stopped one lookup
                   short. Higher is better. Four is the target.

**You are being scored on both at once, and that is the exercise.** Making a judge
stop false-alarming is easy -- tell it to only complain when it is certain and it
will never complain again. It will also never catch anything. Both numbers go on the
form and we are going to plot the class on two axes.

A judge with 0 false alarms and 0 catches has not been fixed. It has been silenced.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

import argparse
import json
import re
import sys

import judge10
import my_judge10
import seeds10
import stub_tools10 as st

GATE_ROWS = ("HW-001", "HW-002", "HW-003", "HW-007")
TARGET_ARM = "dropped_lookup"


# ---------------------------------------------------------------------------
# The one rule: no answer key in the prompt.
# ---------------------------------------------------------------------------
_BANNED = [
    (re.compile(r"HW-\d{3}"), "names a specific question by its row id"),
    (re.compile(r"must_call|must_cover|expected_tools|match_mode", re.I),
     "names a field of the answer key"),
    (re.compile(r"answer key|the key says|the row says", re.I),
     "refers to the answer key"),
]


def check_no_key(rubric: str) -> list[str]:
    """A judge handed the key is a lookup table with a latency problem."""
    problems = []
    for i, line in enumerate(rubric.splitlines(), 1):
        for pat, why in _BANNED:
            m = pat.search(line)
            if m:
                problems.append(f"line {i}: {why} -- {m.group(0)!r}\n"
                                f"         {line.strip()[:90]}")
    return problems


def load(row_id: str) -> dict:
    runs = json.loads((_path.session(7) / "runs7.json").read_text())["runs"]
    rec = next(r for r in runs if r.get("phase") == "matrix"
               and r.get("seed") == "healthy" and r.get("row_id") == row_id)
    out = st.with_tools(rec["outputs"])
    out["question"] = rec["question"]
    return out


def build(question: str, calls: list[dict]) -> str:
    """judge10's own preamble and roster, with YOUR rubric in place of ours."""
    return (judge10._PREAMBLE.format(roster=judge10.roster())
            + "\n" + my_judge10.RUBRIC
            + "\n" + judge10.render(question, calls))


def main() -> int:
    ap = argparse.ArgumentParser(description="Screen your rubric.")
    ap.add_argument("--offline", action="store_true",
                    help="checks and plumbing only. No key, no spend.")
    ap.add_argument("--show", action="store_true",
                    help="print the exact prompt one judge would get, then stop")
    ap.add_argument("--live", action="store_true",
                    help="run it for real: 20 model calls on your own key")
    a = ap.parse_args()

    rubric = my_judge10.RUBRIC
    print("screen_my_judge\n")

    if rubric.strip() == my_judge10.RUBRIC_AS_TAUGHT.strip():
        print("  NOTE: your rubric is still the class version, character for character.")
        print("        Running it will reproduce the class result. That is a fine")
        print("        baseline, but it is not the homework.\n")

    problems = check_no_key(rubric)
    if problems:
        print("  REFUSED -- your rubric shows the judge the answer key:\n")
        for p in problems:
            print("   ", p)
        print("\n  Take it out. The judge has to work from the request and the calls.")
        return 1
    print("  [ok] no answer key in the prompt\n")

    base = {r: load(r) for r in GATE_ROWS}

    if a.show:
        o = base["HW-003"]
        print(build(o["question"], o["tool_calls"]))
        return 0

    if not a.live:
        # Offline: prove the arms differ and the plumbing works, with no model.
        print("  offline check -- the runs your rubric will be scored on:\n")
        for arm in ("healthy", TARGET_ARM):
            n = sum(len(seeds10.apply(arm, base[r]["tool_calls"], {})) for r in GATE_ROWS)
            print(f"    {arm:16} {len(GATE_ROWS)} runs, {n} tool calls in total")
        o = base["HW-003"]
        short = seeds10.apply(TARGET_ARM, o["tool_calls"], {})
        print(f"\n    HW-003 clean            {len(o['tool_calls'])} calls, "
              f"last one is {o['tool_calls'][-1]['name']}")
        print(f"    HW-003 {TARGET_ARM}   {len(short)} calls, that last one is gone")
        print(f"\n  words in your rubric: {len(rubric.split())} "
              f"(the class version had {len(my_judge10.RUBRIC_AS_TAUGHT.split())})")
        print("\n  Looks runnable. When you are ready:")
        print("    python session-10/screen_my_judge.py --live")
        return 0

    # ----- live -----
    calls_to_make = len(GATE_ROWS) * 2          # healthy + the target arm
    print(f"  This will make {calls_to_make} model calls on your key "
          f"({len(GATE_ROWS)} questions x 2 versions).")
    if input("  type yes to continue: ").strip().lower() != "yes":
        print("  nothing spent.")
        return 0

    import evalkit
    chat = evalkit.get_chat()
    result = {"healthy": [], TARGET_ARM: []}
    for arm in ("healthy", TARGET_ARM):
        for rid in GATE_ROWS:
            o = base[rid]
            calls = seeds10.apply(arm, o["tool_calls"], {})
            msg = chat.invoke(build(o["question"], calls))
            word, evidence = judge10.parse_verdict(msg.text)
            fired = judge10.VERDICTS[word] == 0
            result[arm].append((rid, fired, f"{word} — {evidence}"))
            print(f"    {arm:16} {rid}  {'FIRED' if fired else 'quiet'}   {evidence[:64]}")
        print()

    false_alarms = sum(1 for _, f, _ in result["healthy"] if f)
    catches = sum(1 for _, f, _ in result[TARGET_ARM] if f)
    n = len(GATE_ROWS)

    print("=" * 64)
    print(f"  FALSE ALARMS   {false_alarms} of {n} clean runs      (class version: 4 of 4)")
    print(f"  CATCHES        {catches} of {n} broken runs     (the arm this judge is for)")
    print("=" * 64)
    if false_alarms == 0 and catches == 0:
        print("  Both zero. You did not fix it, you silenced it. It now agrees with")
        print("  everything, which is the same as saying nothing.")
    elif false_alarms < 4 and catches > 0:
        print("  Fewer false alarms AND it still catches something. That is the result.")
    elif false_alarms >= 4:
        print("  Still crying wolf. Look for the sentence that tells it to imagine what")
        print("  a competent engineer WOULD have looked up, rather than what was ASKED.")
    print("\n  Put both numbers on the form. Do not round them and do not pick the")
    print("  better of two runs -- report the last one you ran.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
