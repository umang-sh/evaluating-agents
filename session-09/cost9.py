"""
Session 9 — what an execution trajectory actually costs, with intervals.

    python cost9.py                 # the whole financial picture
    python cost9.py --json deck_numbers9.json

WHERE THE MONEY COMES FROM, AND WHERE IT DOES NOT
--------------------------------------------------
ONLY the live `comparison` phase of `runs7.json`: 12 rows x 3 reps x 2 arms = 72 runs,
claude-sonnet-5, 13 Sep 2026. Those records carry all eight metrics:

    latency_s . n_agent_calls . n_tool_calls . answer_chars
    tokens_out . tokens_in_uncached . tokens_billed . cost_usd

The seeded `matrix` phase carries FOUR metrics and no token or cost figure whatsoever.
Every seeded trajectory in this session is free by construction, and any slide that
prices a seeded failure is quoting a number that does not exist. `traj9.assert_no_cost()`
raises if anyone tries.

THREE THINGS THE SESSION 9 KICKOFF GOT WRONG, ALL FIXED HERE
-------------------------------------------------------------
1. **The totals are not comparable.** `$0.985` sums THIRTY-FIVE pipeline runs against
   THIRTY-SIX single ones: `HW-003` rep 2 has no `cost_usd`. The famous "1.29x" is a
   35-vs-36 comparison. `missing_cost()` finds the hole rather than trusting that it is
   still the same one.

2. **"agent calls 2.00x" is a unit artifact.** `n_agent_calls` counts SPECIALISTS and
   excludes the planner. Agent invocations are 108 vs 36 = 3.0x. Both numbers are
   reported here, each with the definition attached, because a ratio whose denominator
   is undefined is not a measurement.

3. **"-4%" means the PIPELINE scored higher, and it is not percentage points.**
   `shared/paired.py` computes `pct = 100*(mean_cand - mean_base)/mean_base`. With
   base=pipeline and cand=single that is a RELATIVE change and it is negative because
   the SINGLE arm was lower. In percentage points the pipeline is +2.8pp ahead. Both
   forms are printed side by side by `sign_trap()` so a deck cannot pick up one and
   caption it as the other. The verdict -- TIE -- is unchanged either way.

WHY PAIRED AND NOT TOTALS
--------------------------
Both arms answer the same 12 questions. An easy question is cheap for both; a multi-hop
one is expensive for both. Subtract per question and that spread cancels. Sum into two
totals and it does not -- and the totals then hide the only interesting thing in this
data, which is that the pipeline is CHEAPER on three of the twelve rows and 2.7x dearer
on two others. `shared/paired.py` is Session 6's module and is used unchanged.

"NOT WORTH IT" IS A DIFFERENT SENTENCE FROM "WE COULD NOT TELL"
----------------------------------------------------------------
The course has spent four sessions on this. `equivalence_n()` answers it with a number:
to claim the two arms are EQUIVALENT on task outcome you must pre-declare a margin of
indifference and show the whole interval inside it. At the observed rates and a +/-10pp
margin that needs roughly 400 rows per arm. There are 12.
"""

from __future__ import annotations

import _path  # noqa: F401  -- shared/ and plant/ on sys.path; must be first

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime

import traj9
from intervals import newcombe
from paired import paired, row_pcts

__version__ = "s9-2026-09-20a"

# base=single, cand=pipeline, so a POSITIVE difference means "the pipeline costs more".
# The orientation is fixed here, once, because Session 7's -4% became unreadable
# precisely by leaving it to whoever wrote the slide.
BASE, CAND = "single", "pipeline"

METRICS = ("cost_usd", "latency_s", "tokens_billed", "n_tool_calls", "outcome_match")

# Lower is better for these, so "SEPARATED" on them is bad news for the pipeline.
# Session 6 found the LangSmith Compare view assumes higher is better per column and
# shows no intervals; this is the same trap, and naming the direction is the fix.
LOWER_IS_BETTER = {"cost_usd", "latency_s", "tokens_billed", "n_tool_calls"}


def comparison_runs() -> list[dict]:
    return traj9.runs("comparison")


def missing_cost(runs=None) -> list[dict]:
    """Runs with no `cost_usd`. Found, never assumed.

    Session 8's rule 1: recompute, do not read a comment. The kickoff says 35 of 36;
    that was true on 20 Sep and this function is what keeps it true.
    """
    runs = runs if runs is not None else comparison_runs()
    return [{"row_id": r["row_id"], "arm": r["arm"], "rep": r["rep"]}
            for r in runs
            if (r["outputs"].get("metrics") or {}).get("cost_usd") is None]


def totals(runs=None) -> dict:
    """The unpaired totals -- computed ONLY so the deck can show why they are unusable."""
    runs = runs if runs is not None else comparison_runs()
    out = {}
    for arm in (BASE, CAND):
        vals = [(r["outputs"]["metrics"] or {}).get("cost_usd")
                for r in runs if r["arm"] == arm]
        have = [v for v in vals if v is not None]
        out[arm] = {"summed": sum(have), "n_with_cost": len(have), "n_runs": len(vals)}
    # What the pipeline total would be if the one missing rep cost what its row's other
    # reps did. Reported as a RANGE against the raw sum, never as "the" number.
    by_row = defaultdict(list)
    for r in runs:
        if r["arm"] == CAND:
            c = (r["outputs"]["metrics"] or {}).get("cost_usd")
            if c is not None:
                by_row[r["row_id"]].append(c)
    reps = max((len([1 for r in runs if r["arm"] == CAND and r["row_id"] == k])
                for k in by_row), default=3)
    out[CAND]["imputed"] = sum(statistics.mean(v) * reps for v in by_row.values())
    return out


def agent_call_counts(runs=None) -> dict:
    """Both definitions, each labelled. The kickoff's '2.00x' is the first one."""
    runs = runs if runs is not None else comparison_runs()
    spec = {a: sum((r["outputs"]["metrics"] or {}).get("n_agent_calls", 0)
                   for r in runs if r["arm"] == a) for a in (BASE, CAND)}
    invo = {a: sum(len(r["outputs"].get("agent_calls") or [])
                   for r in runs if r["arm"] == a) for a in (BASE, CAND)}
    return {
        "specialists_only": {**spec, "ratio": spec[CAND] / spec[BASE] if spec[BASE] else None,
                             "note": "n_agent_calls — EXCLUDES the planner"},
        "all_invocations": {**invo, "ratio": invo[CAND] / invo[BASE] if invo[BASE] else None,
                            "note": "len(agent_calls) — INCLUDES the planner"},
    }


def table(runs=None) -> dict:
    """The paired interval for every metric. base=single, cand=pipeline."""
    runs = runs if runs is not None else comparison_runs()
    out = {}
    for m in METRICS:
        p = paired(runs, BASE, CAND, m)
        out[m] = {
            "n_rows": p.n_rows,
            "mean_single": p.mean_base, "mean_pipeline": p.mean_cand,
            "diff": p.diff, "lo": p.lo, "hi": p.hi,
            "direction": p.direction,
            "separated": p.direction in ("HIGHER", "LOWER"),
            "lower_is_better": m in LOWER_IS_BETTER,
        }
    return out


def per_row_cost(runs=None) -> list[dict]:
    """Per-row cost change, pipeline vs single, with each row's path.

    This is the slide. The mean says +36%; the rows run from -42% to +166%, and three
    of them are NEGATIVE -- the planner routing a narrow question to one specialist is
    cheaper than one agent doing everything. A total hides all of that.
    """
    runs = runs if runs is not None else comparison_runs()
    pcts = row_pcts(runs, BASE, CAND, "cost_usd")
    paths, qrow = {}, {}
    for r in runs:
        if r["arm"] == CAND:
            paths[r["question"]] = " -> ".join(r["outputs"].get("agent_calls") or [])
            qrow[r["question"]] = r["row_id"]
    rows = [{"row_id": qrow.get(q, "?"), "question": q, "pct": v, "path": paths.get(q, "")}
            for q, v in pcts.items()]
    return sorted(rows, key=lambda d: d["pct"])


def sign_trap(runs=None) -> dict:
    """outcome_match stated both ways, so nobody can caption one as the other."""
    runs = runs if runs is not None else comparison_runs()
    p = paired(runs, BASE, CAND, "outcome_match")
    # Session 7's orientation, RECOMPUTED rather than negated. Flipping base and cand
    # is not the same as flipping the sign: `pct` divides by mean_base, so the two
    # orientations have DIFFERENT DENOMINATORS. Negating this one gives -4.5%; Session 7
    # printed -4.3%, and chasing that 0.2% is how the sign confusion gets found.
    s7 = paired(runs, CAND, BASE, "outcome_match")
    return {
        "percentage_points": {"diff": 100 * p.diff, "lo": 100 * p.lo, "hi": 100 * p.hi,
                              "reads": "the pipeline scored this many POINTS higher"},
        "relative_as_session7_printed_it": {
            "pct": s7.pct, "lo": s7.pct_lo, "hi": s7.pct_hi,
            "base": CAND, "cand": BASE,
            "reads": "Session 7 printed base=pipeline cand=single, so its -4.3% is a "
                     "RELATIVE change and is negative because the SINGLE arm was lower"},
        "verdict": p.direction,
    }


# What Session 7's deck actually shipped. Asserted, not remembered: if a future edit to
# paired.py or to runs7.json moves this number, the deck and the slide it explains have
# silently stopped agreeing, and preflight9 check [3] fails rather than the room finding out.
SESSION7_DECK_PCT = -4.3478260869565215
SESSION7_DECK_CI = (-52.19565217391304, 43.49999999999999)


def reproduces_session7(runs=None, tol: float = 1e-9) -> bool:
    runs = runs if runs is not None else comparison_runs()
    s7 = paired(runs, CAND, BASE, "outcome_match")
    return (abs(s7.pct - SESSION7_DECK_PCT) < tol
            and abs(s7.pct_lo - SESSION7_DECK_CI[0]) < tol
            and abs(s7.pct_hi - SESSION7_DECK_CI[1]) < tol)


def equivalence_n(runs=None, margin: float = 0.10, ns=(36, 72, 120, 200, 300, 400,
                                                       600, 800, 1200)) -> dict:
    """How many rows per arm before 'we could not tell' becomes 'they are the same'.

    Holds the observed rates fixed and scales n, asking when the whole Newcombe interval
    sits inside +/- margin. This is the arithmetic behind the sentence the course keeps
    insisting on, and it is why Session 9 does NOT say the pipeline is not worth it.
    """
    runs = runs if runs is not None else comparison_runs()
    p = paired(runs, BASE, CAND, "outcome_match")
    p1, p2 = p.mean_cand, p.mean_base
    ladder = []
    for n in ns:
        d, lo, hi = newcombe(round(p1 * n), n, round(p2 * n), n)
        ladder.append({"n_per_arm": n, "diff": d, "lo": lo, "hi": hi,
                       "equivalent": lo > -margin and hi < margin})
    first = next((r["n_per_arm"] for r in ladder if r["equivalent"]), None)
    return {"margin": margin, "rows_available": p.n_rows,
            "first_n_that_clears": first, "ladder": ladder}


def deck_numbers(runs=None) -> dict:
    runs = runs if runs is not None else comparison_runs()
    return {
        # Stamped. preflight8 forgot and every data slide read "measured ?" in grey.
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "runs7.json phase=comparison (live, 12 rows x 3 reps x 2 arms)",
        "cost_version": __version__,
        "n_runs": len(runs),
        "missing_cost": missing_cost(runs),
        "totals_DO_NOT_QUOTE": totals(runs),
        "agent_calls": agent_call_counts(runs),
        "paired": table(runs),
        "per_row_cost": per_row_cost(runs),
        "sign_trap": sign_trap(runs),
        "equivalence": equivalence_n(runs),
        "reproduces_session7_deck": reproduces_session7(runs),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Session 9 — the cost of a trajectory")
    ap.add_argument("--json", metavar="OUT")
    a = ap.parse_args()
    runs = comparison_runs()
    d = deck_numbers(runs)

    print(f"cost9 {__version__}   {len(runs)} live runs, {d['source']}\n")

    miss = d["missing_cost"]
    print(f"THE HOLE — runs with no cost_usd: {len(miss)}")
    for m in miss:
        print(f"    {m['row_id']} {m['arm']} rep{m['rep']}")
    t = d["totals_DO_NOT_QUOTE"]
    print(f"  so the raw totals compare {t[CAND]['n_with_cost']} pipeline runs with "
          f"{t[BASE]['n_with_cost']} single ones:")
    print(f"    pipeline ${t[CAND]['summed']:.4f} (imputed ${t[CAND]['imputed']:.4f})  "
          f"single ${t[BASE]['summed']:.4f}")
    print("  NEITHER RATIO GOES ON A SLIDE. Use the paired interval below.\n")

    print("PAIRED, per request, base=single cand=pipeline "
          "(positive = the pipeline costs/takes more)")
    for m, v in d["paired"].items():
        unit = "$" if m == "cost_usd" else ""
        print(f"  {m:16s} {unit}{v['diff']:+9.5f}  [{unit}{v['lo']:+.5f}, "
              f"{unit}{v['hi']:+.5f}]  n={v['n_rows']}  {v['direction']}")

    print("\nTHE SPREAD THE TOTALS HIDE — cost change per row")
    for r in d["per_row_cost"]:
        print(f"  {r['pct']:+8.1f}%  {r['row_id']}  {r['path']}")

    s = d["sign_trap"]
    pp, rel = s["percentage_points"], s["relative_as_session7_printed_it"]
    print(f"\noutcome_match, BOTH WAYS — verdict {s['verdict']}")
    print(f"  {pp['diff']:+.1f} percentage points [{pp['lo']:+.1f}, {pp['hi']:+.1f}]  "
          f"— {pp['reads']}")
    print(f"  {rel['pct']:+.4f}% relative [{rel['lo']:+.1f}, {rel['hi']:+.1f}] — {rel['reads']}")
    print(f"  reproduces the Session 7 deck exactly: {reproduces_session7(runs)}")

    e = d["equivalence"]
    print(f"\n'NOT WORTH IT' vs 'COULD NOT TELL' — margin +/-{e['margin']:.0%}, "
          f"rows available {e['rows_available']}")
    for r in e["ladder"]:
        if r["equivalent"] or r["n_per_arm"] in (36, 72, 200):
            print(f"  n={r['n_per_arm']:5d}/arm  [{r['lo']:+.1%}, {r['hi']:+.1%}]"
                  f"{'   EQUIVALENT' if r['equivalent'] else ''}")
    print(f"  first n that clears the margin: {e['first_n_that_clears']} rows per arm")

    ac = d["agent_calls"]
    print(f"\nAGENT CALLS, both definitions")
    for k, v in ac.items():
        print(f"  {k:18s} {v[CAND]:4d} vs {v[BASE]:4d} = {v['ratio']:.2f}x   ({v['note']})")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=1, default=str)
        print("\n  wrote", a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
