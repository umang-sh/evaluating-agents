#!/usr/bin/env python3
"""
test_my_tool.py — instructor prep for Session 3, Hands-on A.

Write a candidate `@tool`, then run this. It checks three things, in increasing
cost, and stops at the first that fails:

  1. STRUCTURE  — does @tool even accept it? (no API calls, instant)
  2. VISIBILITY — what does the MODEL see? name, description, arg schema.
                  The docstring IS the description. A vague one means the tool
                  is never chosen, and your hands-on demonstrates nothing.
  3. BEHAVIOUR  — run the agent on a question that should need it. Was it
                  actually called? Did the architecture change? (costs a few
                  cents and ~20s per run)

    python test_my_tool.py                 # all three levels
    python test_my_tool.py --dry           # levels 1-2 only, no API calls

Run from the course-repo directory.
"""

from __future__ import annotations

import argparse
import sys

from langchain_core.tools import tool


# ===========================================================================
# YOUR CANDIDATE TOOLS — edit these. Three worked examples are provided.
# ===========================================================================

@tool
def today_date() -> str:
    """Return today's date in YYYY-MM-DD format. Use this whenever the answer
    depends on what today's date is."""
    from datetime import date
    return date.today().isoformat()


@tool
def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    """Convert a number between units. Supports km/miles, kg/pounds and c/f.
    Use for any question that needs a unit conversion."""
    v, f, t = float(value), from_unit.lower(), to_unit.lower()
    table = {("km", "miles"): 0.621371, ("miles", "km"): 1.60934,
             ("kg", "pounds"): 2.20462, ("pounds", "kg"): 0.453592}
    if (f, t) in table:
        return f"{v * table[(f, t)]:.4g} {t}"
    if (f, t) == ("c", "f"):
        return f"{v * 9 / 5 + 32:.4g} f"
    if (f, t) == ("f", "c"):
        return f"{(v - 32) * 5 / 9:.4g} c"
    return f"error: no conversion from {f} to {t}"


@tool
def word_count(text: str) -> str:
    """Count the words in a piece of text. Use when asked how long something is."""
    return str(len(text.split()))


# The one you will actually assign, and a question that SHOULD trigger it.
CANDIDATE = today_date
TRIGGER_QUESTION = "What is today's date, and how many days until 1 January 2027?"

# A control: a question the new tool is irrelevant to. Used to show that an
# unused tool still does not change the architecture.
CONTROL_QUESTION = "What is the latest released version of the langgraph package on PyPI?"


# ===========================================================================
# LEVEL 1 — structure
# ===========================================================================

def level1(t) -> bool:
    print("\n" + "=" * 70)
    print("1. STRUCTURE — does @tool accept it at all?")
    print("=" * 70)
    ok = True

    # If you got here, @tool did not raise, which means a docstring or an
    # explicit description= was present. Demonstrate the failure students WILL
    # hit, so you can describe it accurately rather than from memory.
    try:
        @tool
        def _no_docstring(x: str) -> str:
            # a '#' comment is NOT a docstring
            return x
        print("  [WARN ] a tool with no docstring was ACCEPTED — the ValueError")
        print("          your notebook relies on may not fire on this version.")
        ok = False
    except Exception as exc:
        print(f"  [ok   ] no-docstring tool rejected at decoration time: "
              f"{type(exc).__name__}")
        print(f"          -> this is the error students hit in Hands-on A. "
              f"Let it happen; do not warn them.")

    print(f"  [ok   ] {t.name} decorated cleanly")
    return ok


# ===========================================================================
# LEVEL 2 — what the model actually sees
# ===========================================================================

def level2(t) -> bool:
    print("\n" + "=" * 70)
    print("2. VISIBILITY — what the MODEL sees when it decides")
    print("=" * 70)
    print(f"  name        : {t.name}")
    print(f"  description : {t.description}")
    print(f"  args        : {t.args}")
    print()

    ok = True
    d = (t.description or "").strip()

    if len(d) < 25:
        print("  [WARN ] description under 25 chars. The model chooses tools by "
              "this text\n          alone — a terse one will simply never be picked.")
        ok = False
    else:
        print("  [ok   ] description has enough substance to be selectable")

    if not any(w in d.lower() for w in ("use ", "when ", "whenever ")):
        print("  [WARN ] description says what the tool DOES but not WHEN to use it.")
        print("          Tool descriptions are prompts. 'Use this when…' measurably")
        print("          improves selection. (Session 10 is this, formalised.)")
        ok = False
    else:
        print("  [ok   ] description tells the model WHEN to reach for it")

    print("\n  TEACHING NOTE: this panel is the whole reason the docstring is")
    print("  mandatory. It is not documentation — it is the only thing the model")
    print("  reads when deciding whether to call your function.")
    return ok


# ===========================================================================
# LEVEL 3 — does it actually get used, and does the architecture move?
# ===========================================================================

def level3(t) -> bool:
    print("\n" + "=" * 70)
    print("3. BEHAVIOUR — is it called, and does anything structural change?")
    print("=" * 70)

    import arch_bench
    from arch_bench import BASE_TOOLS, Probe, run_one, walk_tool_spans

    arch_bench.env_setup()
    extended = BASE_TOOLS + [t]

    def go(label, question, tools):
        probe = Probe(question=question, must_contain=[], difficulty="easy")
        kw = {"tools": tools} if tools is not None else None
        r = run_one("react", probe, kw)
        names = []
        if arch_bench.LAST_SERVER_ROOT is not None:
            names = [s.name for s in walk_tool_spans(arch_bench.LAST_SERVER_ROOT)]
        print(f"  {label:22s} {len(tools or BASE_TOOLS)} avail  "
              f"{r.tool_calls} used  {r.tokens_billed:6d} tok   {names}")
        return r, names

    print("\n  -- the question your tool is FOR --")
    _, before = go("2 tools (baseline)", TRIGGER_QUESTION, BASE_TOOLS)
    _, after = go("3 tools (yours)", TRIGGER_QUESTION, extended)

    used = t.name in after
    if used:
        print(f"\n  [ok   ] '{t.name}' WAS called. Your hands-on has a live example of")
        print("          the model choosing a tool it has never seen before.")
    else:
        print(f"\n  [WARN ] '{t.name}' was NOT called on its own trigger question.")
        print("          Either the description is not selling it, or the model can")
        print("          answer without it. Fix the description first (level 2), then")
        print("          make the question genuinely require the tool.")

    print("\n  -- a question your tool is irrelevant to (the control) --")
    go("3 tools, unrelated Q", CONTROL_QUESTION, extended)
    print("\n  Expect: tool available, not used, and NOTHING structural different.")
    print("  That is the Hands-on A point — capabilities grew, the architecture")
    print("  did not. Open both traces and look for a new node. There is none.")
    return used


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true",
                    help="levels 1-2 only; no API calls, no cost")
    args = ap.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    t = CANDIDATE
    l1 = level1(t)
    l2 = level2(t)
    if args.dry:
        print("\n--dry: stopping before any API call.\n")
        return 0 if (l1 and l2) else 1

    l3 = level3(t)
    print("\n" + "=" * 70)
    print(f"structure {'ok' if l1 else 'CHECK'} | "
          f"description {'ok' if l2 else 'CHECK'} | "
          f"actually used {'yes' if l3 else 'NO'}")
    print("=" * 70 + "\n")
    return 0 if (l1 and l2 and l3) else 1


if __name__ == "__main__":
    sys.exit(main())
