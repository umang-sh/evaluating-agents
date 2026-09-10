"""
Session 6 — automating the regression test. INSTRUCTOR DEMO (sacrificial block).

    python regress_gate.py --cand redundant                 # from runs6.json -> exit 1
    python regress_gate.py --cand concise                   # -> exit 0
    python regress_gate.py --experiments s6-replay-healthy-xxxx s6-replay-redundant-yyyy

A regression test that a person has to remember to run is a regression test
that stops being run. This is the same arithmetic as regress6.py, reduced to
the one thing a CI pipeline understands: an EXIT CODE.
    exit 0  no gated metric regressed past its threshold  -> merge allowed
    exit 1  at least one did                               -> merge blocked

Wiring it into CI is one step after the agent-eval step, e.g. in GitHub Actions:
    - run: python regress_gate.py --experiments $BASE_EXP $CAND_EXP

WHY NOT LangSmith's evaluate_comparative FOR THIS -- measured 10 Sep: with
num_repetitions=5 its comparator receives TEN runs per example (both versions'
five, one after the other), while the docs describe a two-item list. A
comparator written as runs[0] vs runs[1] silently compares the baseline with
ITSELF. And it returns a per-example preference, not an interval. So the gate
pairs the runs itself.

--experiments reads root runs from LangSmith and gates on the COST metrics the
target recorded. It does not re-grade answers (that needs the reference rows);
use runs6.json mode for the full set.
"""

from __future__ import annotations

import argparse
import sys

import paired as P

# metric -> smallest regression (in % of incumbent) that blocks a merge.
GATES = {"tokens_billed": 10, "n_searches": 20}
SUCCESS = "outcome_keyword"     # any detectable drop blocks


def runs_from_langsmith(base_exp: str, cand_exp: str) -> list[dict]:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    import warnings
    from langsmith import Client
    client = Client()
    out = []
    for label, exp in (("base", base_exp), ("cand", cand_exp)):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")          # list_runs deprecation
            roots = list(client.list_runs(project_name=exp, is_root=True))
        for r in roots:
            outs = r.outputs or {}
            if outs.get("metrics"):
                out.append({"version": label, "question": (r.inputs or {}).get("question"),
                            "outputs": outs, "scores": {}})
        print(f"  {exp}: {sum(1 for x in out if x['version'] == label)} runs with metrics")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs6.json")
    ap.add_argument("--base", default="healthy")
    ap.add_argument("--cand")
    ap.add_argument("--experiments", nargs=2, metavar=("BASE_EXP", "CAND_EXP"))
    args = ap.parse_args()

    if args.experiments:
        runs, base, cand = runs_from_langsmith(*args.experiments), "base", "cand"
    else:
        if not args.cand:
            ap.error("--cand or --experiments is required")
        runs, base, cand = P.load(args.runs), args.base, args.cand

    blocked = []
    for m, pct in GATES.items():
        p = P.paired(runs, base, cand, m)
        if p.n_rows < 2:
            print(f"  {m:<16} not enough paired rows ({p.n_rows}) — cannot gate")
            blocked.append(f"{m}: no data")
            continue
        hit = p.verdict == "REGRESSION" and p.pct_lo >= pct
        print(f"  {m:<16} {p.pct:+.0f}% [{p.pct_lo:+.0f}, {p.pct_hi:+.0f}]  "
              f"gate +{pct}%  {'BLOCK' if hit else 'pass'}")
        if hit:
            blocked.append(f"{m} +{p.pct_lo:.0f}% or more")
    if not args.experiments:
        s = P.paired(runs, base, cand, SUCCESS)
        hit = s.direction == "LOWER"
        print(f"  {SUCCESS:<16} {100 * s.diff:+.0f}pt [{100 * s.lo:+.0f}, {100 * s.hi:+.0f}]  "
              f"gate: any drop  {'BLOCK' if hit else 'pass'}")
        if hit:
            blocked.append(f"{SUCCESS} dropped")

    if blocked:
        print(f"\n  REGRESSION GATE: FAIL ({cand}) — " + "; ".join(blocked))
        return 1
    print(f"\n  REGRESSION GATE: PASS ({cand}) — nothing regressed past its threshold. "
          "PASS is not 'better': see regress6.py for ties.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
