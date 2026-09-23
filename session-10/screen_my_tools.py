"""
Screen the answer key you wrote in `my_tools10.py`. No model, no key, no spend.

WHAT THIS ASKS, AND WHY IT IS NOT "IS YOUR ANSWER RIGHT"
---------------------------------------------------------
There is no single right answer key. Two engineers will write two different ones for the
same question and both can be defensible. So this does not compare your key to ours.

It asks the only question that matters about any check you write:

    DOES IT TELL THE TWO APART?

A key is worth having when it fires on a run where something is genuinely wrong and
stays quiet on a run where nothing is. So your key is run against BOTH:

    the healthy run          nothing deliberately broken   -> your key should stay quiet
    four broken runs         one specific thing damaged    -> your key should fire on
                                                              at least one

and you get one of three verdicts per row:

    DISCRIMINATING   fires on at least one broken run, quiet on the healthy one.
                     This is the one you want.

    DECORATIVE       never fires on anything. It is not wrong, it is just not testing
                     anything -- usually because it asks for less than the question
                     needs. Add a must_call or a must_cover the question actually
                     demands.

    WRONG            fires on the healthy run. In production this is a check that cries
                     wolf on every good run, and people stop reading it within a week.
                     Usually it asks for a tool the question did not actually need.

A row you left empty comes back EMPTY rather than DECORATIVE, because those are
different problems and telling you the wrong one wastes your time.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

import argparse
import json

import my_tools10
import seeds10
import stub_tools10 as st
import tool_eval10 as te
import tool_rows10

GATE_KEYS = ("tool_selection", "tool_arguments")


def healthy_run(row_id: str) -> dict:
    runs = json.loads((_path.session(7) / "runs7.json").read_text())["runs"]
    rec = next(r for r in runs if r.get("phase") == "matrix"
               and r.get("seed") == "healthy" and r.get("row_id") == row_id)
    out = st.with_tools(rec["outputs"])
    out["question"] = rec["question"]
    return out


def validate(row: dict) -> list[str]:
    """The same load-time checks the real rows get. A row that cannot pass is not a
    hard row, it is a broken one, and you deserve to be told which."""
    problems = []
    if row["match_mode"] not in tool_rows10.MATCH_MODES:
        problems.append(f"match_mode must be one of {tool_rows10.MATCH_MODES}")
    for field in ("must_call", "forbidden"):
        for agent, tools in (row.get(field) or {}).items():
            if agent not in st.GRANTS:
                problems.append(f"{field}: {agent!r} is not one of "
                                f"{sorted(k for k in st.GRANTS if k != 'single')}")
                continue
            unknown = sorted(set(tools) - st.TOOL_NAMES)
            if unknown:
                problems.append(f"{field}[{agent}]: no such tool {unknown}")
            ungranted = sorted(set(tools) - st.GRANTS[agent] - set(unknown))
            if ungranted:
                problems.append(
                    f"{field}[{agent}]: {agent} does not hold {ungranted}. It holds "
                    f"{sorted(st.GRANTS[agent])}. A key that asks for a tool the agent "
                    f"was never given can never pass.")
    return problems


def fires(out: dict, row: dict) -> list[str]:
    res = te.run_all(out, row)
    return [k for k in GATE_KEYS if res[k]["score"] == 0]


def screen(row: dict, show: bool = False) -> None:
    rid = row["id"]
    print(f"\n{'=' * 70}\n{rid}")
    base = healthy_run(rid)
    print(f'  "{base["question"]}"')

    if not row.get("must_call") and not row.get("must_cover"):
        print("\n  EMPTY — nothing to screen yet. Fill in must_call and/or must_cover.")
        return

    problems = validate(row)
    if problems:
        print("\n  THIS ROW CANNOT BE SCREENED:")
        for p in problems:
            print(f"    - {p}")
        return

    if show:
        print("\n  the healthy run's tool calls:")
        print(st.render(base["tool_calls"]))

    on_healthy = fires(base, row)
    caught = {}
    for arm in seeds10.BROKEN:
        out = dict(base)
        out["tool_calls"] = seeds10.apply(arm, base["tool_calls"], row)
        f = fires(out, row)
        if f:
            caught[arm] = f

    print()
    if on_healthy:
        print(f"  WRONG — your key fires on the HEALTHY run: {on_healthy}")
        res = te.run_all(base, row)
        for k in on_healthy:
            print(f"    {k}: {res[k]['comment']}")
        print("\n  In production this fires on every good run. Look at what you asked")
        print("  for that this particular question did not actually need.")
        return

    if not caught:
        print("  DECORATIVE — quiet on the healthy run, and quiet on all four broken")
        print("  ones too. It is not testing anything yet.")
        print(f"\n  The four broken runs are:")
        for arm in seeds10.BROKEN:
            print(f"    {arm:18} {seeds10.SEEDS[arm]['one_line']}")
        print("\n  Ask what this question NEEDS looked up, and require that.")
        return

    print(f"  DISCRIMINATING — quiet on the healthy run, fires on "
          f"{len(caught)} of {len(seeds10.BROKEN)} broken ones:")
    for arm, keys in caught.items():
        out = dict(base)
        out["tool_calls"] = seeds10.apply(arm, base["tool_calls"], row)
        res = te.run_all(out, row)
        for k in keys:
            print(f"    {arm:18} {k}")
            print(f"      {res[k]['comment']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Screen your answer key. No model calls.")
    ap.add_argument("--show", action="store_true",
                    help="also print the tool calls your key is being screened against")
    ap.add_argument("--example", action="store_true",
                    help="screen the worked example instead, to see what good looks like")
    a = ap.parse_args()

    print("screen_my_tools — 0 model calls, works on any provider")
    rows = [my_tools10.WORKED_EXAMPLE] if a.example else my_tools10.ROWS
    for row in rows:
        screen(row, show=a.show)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
