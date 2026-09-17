"""
Session 6 — Hands-on 5. The regression test. Your criteria against the runs.

    python regress6.py                          # criteria6.py vs runs6.json
    python regress6.py --criteria partner.py    # someone else's criteria, same runs

No network. Everything here is arithmetic on runs6.json.

FOR EACH CANDIDATE, AGAINST healthy, IT PRINTS
  1. the paired interval per metric (paired.py), and what it means FOR YOU:
       TIE               the interval crosses zero -- no detectable difference
       REAL, BELOW BAR   detectable, but smaller than your ACT_IF
       REAL, MAYBE BAR   detectable; the interval straddles your ACT_IF
       CLEARS BAR        detectable, and even the cautious end beats your ACT_IF
  2. your PREDICT, scored HIT / MISS
  3. the regression-set rule: share of runs within 25% of the incumbent's
     median on the SAME question (make_regression_set.within_baseline)
  4. SUCCESS_BAR: does it clear the pass rate you set?
  5. the decision, by the tie rule

THE TIE RULE (the spine): report the interval, not the winner -- and when it
crosses zero, the tie goes to the cheaper agent. If cost ties too, keep the
incumbent: a change you cannot defend is not a change worth shipping.
"""

from __future__ import annotations


import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first
import argparse
import importlib.util
import sys

import paired as P
from make_regression_set import baselines, within_baseline

METRICS = ["outcome_keyword", "tokens_billed", "n_searches", "latency_s"]
RATES = {"outcome_keyword", "tool_correctness", "trajectory_no_waste"}


def load_criteria(path: str):
    spec = importlib.util.spec_from_file_location("criteria_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)            # type: ignore[union-attr]
    errs, _ = mod.problems()
    if errs:
        print(f"  {path} is not filled in ({len(errs)} problems). Run: python {path}")
        raise SystemExit(1)
    return mod


def size(p: P.Paired) -> tuple[float, float, float]:
    """(estimate, lo, hi) in % of incumbent -- or in POINTS for pass rates."""
    if p.metric in RATES:
        return 100 * p.diff, 100 * p.lo, 100 * p.hi
    return p.pct, p.pct_lo, p.pct_hi


def against_bar(p: P.Paired, act_if: float) -> str:
    if p.direction == "NO DETECTABLE DIFFERENCE":
        return "TIE"
    est, lo, hi = size(p)
    near = min(abs(lo), abs(hi))            # the cautious end of the interval
    if near >= act_if:
        return "CLEARS BAR"
    if abs(est) < act_if:
        return "REAL, BELOW BAR"
    return "REAL, MAYBE BAR"


def predicted(p: P.Paired) -> str:
    return {"HIGHER": "HIGHER", "LOWER": "LOWER"}.get(p.direction, "TIE")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs6.json")
    ap.add_argument("--criteria", default="criteria6.py")
    args = ap.parse_args()
    C = load_criteria(args.criteria)
    runs = P.load(args.runs)
    base = baselines(runs)
    print(f"  criteria: {C.AUTHOR}   runs: {args.runs}   incumbent: healthy")

    hits = total = 0
    for cand in ("redundant", "concise"):
        print(f"\n=== healthy -> {cand} " + "=" * (58 - len(cand)))
        print(f"  {'metric':<16}{'change':>9}   {'95% interval':<18}{'your bar':>9}  "
              f"{'verdict':<17}predicted")
        for m in METRICS:
            p = P.paired(runs, "healthy", cand, m)
            est, lo, hi = size(p)
            unit = "pt" if m in RATES else "%"
            guess = C.PREDICT.get(cand, {}).get(m)
            got = predicted(p)
            mark = "HIT " if guess == got else "MISS"
            hits += guess == got
            total += 1
            ci = f"[{lo:+.0f}, {hi:+.0f}]{unit}"
            bar = f"{C.ACT_IF[m]}{unit}"
            print(f"  {m:<16}{f'{est:+.0f}{unit}':>9}   {ci:<18}{bar:>9}  "
                  f"{against_bar(p, C.ACT_IF[m]):<17}{mark} (you: {guess}, runs: {got})")
            if m in RATES and p.mean_base == 1.0 and p.mean_cand == 1.0:
                print(f"  {'':<16}^ ALL-PASS on both versions: this evaluator cannot fail "
                      "on these rows, so TIE here is not evidence of equal quality.")

        mine = [r for r in runs if r["version"] == cand and r.get("outputs")]
        ok = sum(all(v["score"] for v in within_baseline(
                 r["outputs"], {"baseline": base[r["question"]]})) for r in mine)
        print(f"\n  regression-set rule: {ok}/{len(mine)} runs within 25% of healthy's "
              "median on the same question")

        bar_fail = []
        for m, need in C.SUCCESS_BAR.items():
            vals = [bool((r.get("scores") or {}).get(m)) for r in mine]
            rate = sum(vals) / len(vals)
            if rate < need:
                bar_fail.append(f"{m} {rate:.2f} < {need}")
        print("  success bar: " + ("CLEARS" if not bar_fail else "FAILS — " + "; ".join(bar_fail)))

        dec, why = P.recommend(P.paired(runs, "healthy", cand, "outcome_keyword"),
                               P.paired(runs, "healthy", cand, "tokens_billed"))
        if bar_fail:
            dec, why = "KEEP healthy", f"{cand} misses your success bar"
        print(f"  ==> {dec}   ({why})")

    print(f"\n  your predictions: {hits}/{total} HIT. The MISSes are the useful lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
