"""
Session 6 — Hands-on 3. The same question, five times. What moved?

    python consistency6.py                    # all three versions
    python consistency6.py --version healthy  # one

No network. Reads runs6.json.

WHAT IT PRINTS
--------------
  reliability  pass@1 = share of runs that pass.
               pass^5 = chance that ALL FIVE runs of a question pass.
               pass@1 tells you how good the agent is on average. pass^5 tells
               you whether you can rely on it: a question that passes 4 times
               in 5 has pass@1 = 0.8 and pass^5 = 0.
  cost         tokens_billed per run, and tool utilisation (searches per run).
  latency      mean and slowest run (measured under concurrency 4 — compare
               versions to each other, never to a number measured alone).
  noise        which QUESTIONS the run-to-run variation comes from.

pass^k is estimated per question as C(c, k) / C(n, k) -- c passes out of n
runs -- then averaged over questions. With n = 5 that is the exact fraction of
5-run sets that all pass, and it is 0 unless every run passed.
"""

from __future__ import annotations


import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first
import argparse
import math
import statistics
import sys
from collections import defaultdict

import paired as P

QUALITY = ["outcome_keyword", "tool_correctness", "trajectory_no_waste"]


def pass_hat_k(c: int, n: int, k: int) -> float:
    return math.comb(c, k) / math.comb(n, k) if n >= k else float("nan")


def reliability(runs: list[dict], version: str, metric: str) -> tuple[float, float, list[str]]:
    rows: dict[str, list[bool]] = defaultdict(list)
    for r in runs:
        if r["version"] == version:
            s = (r.get("scores") or {}).get(metric)
            if s is not None:
                rows[r["question"]].append(bool(s))
    if not rows:
        return float("nan"), float("nan"), []
    n_all = sum(len(v) for v in rows.values())
    p1 = sum(sum(v) for v in rows.values()) / n_all
    k = min(len(v) for v in rows.values())
    pk = statistics.fmean(pass_hat_k(sum(v), len(v), k) for v in rows.values())
    flaky = [q for q, v in rows.items() if 0 < sum(v) < len(v)]
    return p1, pk, flaky


def report(runs: list[dict], version: str) -> None:
    print(f"\n=== {version} " + "=" * (70 - len(version)))
    print("  reliability         pass@1   pass^5   flaky questions (pass some, fail some)")
    for m in QUALITY:
        p1, pk, flaky = reliability(runs, version, m)
        print(f"  {m:<20} {p1:6.2f}   {pk:6.2f}   {len(flaky)}"
              + (f"  e.g. {flaky[0][:38]}..." if flaky else ""))

    mine = [r for r in runs if r["version"] == version and r.get("outputs")]
    tok = [r["outputs"]["metrics"]["tokens_billed"] for r in mine]
    srch = [r["outputs"]["metrics"]["n_searches"] for r in mine]
    lat = [r["outputs"]["metrics"]["latency_s"] for r in mine]
    cost = [r["outputs"]["metrics"].get("cost_usd") for r in mine]
    print(f"\n  tokens_billed / run  mean {statistics.fmean(tok):7.0f}   "
          f"min {min(tok):6.0f}   max {max(tok):6.0f}")
    print(f"  searches / run       mean {statistics.fmean(srch):7.2f}   "
          f"min {min(srch):6.0f}   max {max(srch):6.0f}")
    print(f"  latency (s)          mean {statistics.fmean(lat):7.2f}   "
          f"slowest {max(lat):6.2f}")
    if all(c is not None for c in cost):
        print(f"  cost USD / run       mean {statistics.fmean(cost):7.4f}   "
              f"per 1,000 questions ${1000 * statistics.fmean(cost):,.2f}")
    else:
        print("  cost USD / run       not recorded in this file — tokens_billed is the "
              "cost column today")

    shares = P.variance_share(runs, version, "tokens_billed")
    if shares:
        q, share, sd, m = shares[0]
        s2, df2, m2 = P.within_row_sigma(P.without(runs, q), version, "tokens_billed")
        s1, df1, m1 = P.within_row_sigma(runs, version, "tokens_billed")
        rows = P.by_row(runs, version, "tokens_billed")
        cvs = sorted(statistics.stdev(v) / statistics.fmean(v) for v in rows.values()
                     if len(v) > 1 and statistics.fmean(v))
        print("\n  noise   per question, CV = sd / mean of ITS OWN five runs:")
        print(f"          median question {statistics.median(cvs):.2f}   "
              f"noisiest {cvs[-1]:.2f}   quietest {cvs[0]:.2f}")
        print(f"          pooled over all questions: CV {s1 / m1:.2f}  (sd {s1:.0f} on "
              f"{m1:.0f}, df {df1})  <- no single question has this number")
        print(f"          {share:.0%} of it is ONE question:\n            {q[:100]}")
        print(f"            that question alone: sd {sd:.0f} on mean {m:.0f}")
        print(f"          every other question: CV {s2 / m2:.2f}  (sd {s2:.0f} on {m2:.0f})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="?", default="runs6.json")
    ap.add_argument("--version", action="append")
    args = ap.parse_args()
    runs = P.load(args.runs)
    versions = args.version or ["healthy", "redundant", "concise"]
    for v in versions:
        report(runs, v)
    print("\n  Two questions to answer with your partner, each with a number:\n"
          "   1. Which metric has the biggest gap between pass@1 and pass^5?\n"
          "   2. Session 5 said sigma/mean is about 40%. For which questions is that true?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
