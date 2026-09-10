"""
Session 6 — comparing two versions of an agent, honestly.

    python paired.py runs6.json                       # every candidate vs healthy
    python paired.py runs6.json --cand concise --metric tokens_billed

THE SPINE, as code:
    Comparing two versions is flipping two coins: report the interval, not the
    winner -- and when it crosses zero, the tie goes to the cheaper agent.

WHY PAIRED, AND WHAT PAIRING DOES NOT BUY YOU
---------------------------------------------
Both versions answer the SAME 12 questions. An easy question is cheap for
both; a multi-hop one is expensive for both. Subtract per question and that
row-to-row spread cancels. Compare two overall means instead and it does not.

But pairing does NOT remove run-to-run noise -- the same question, run again,
costing a different amount. Session 5's sigma = 2,444 was exactly that noise.
Pairing is what gets you BACK to Session 5's arithmetic on a mixed benchmark.
It does not get you under it.

No scipy: the course pin set does not include it. The t table is below.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass

# Two-sided 95% critical values of Student's t. For a df between two keys we use
# the SMALLER key's value -- a slightly wider interval, never a narrower one.
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
        14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
        20: 2.086, 25: 2.060, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def t975(df: int) -> float:
    if df < 1:
        return float("inf")
    return T975[max(k for k in T975 if k <= df)]


# Which direction is worse. Used only for the words, never for the maths.
# None = neutral: a shorter answer is a CHANGE, not a regression. (First draft
# had answer_chars as higher-is-better and called "concise" a REGRESSION for
# doing exactly what its prompt said. Caught on synthetic runs, 10 Sep.)
HIGHER_IS_WORSE = {"tokens_billed": True, "n_searches": True, "n_tool_calls": True,
                   "latency_s": True, "cost_usd": True, "answer_chars": None,
                   "outcome_keyword": False, "tool_correctness": False,
                   "trajectory_no_waste": False}


def value(run: dict, metric: str):
    """A metric lives in outputs['metrics'] (numbers the target recorded) or in
    scores (evaluator verdicts, bool -> 1.0/0.0)."""
    if metric in (run.get("scores") or {}):
        s = run["scores"][metric]
        return None if s is None else float(s)
    v = ((run.get("outputs") or {}).get("metrics") or {}).get(metric)
    return None if v is None else float(v)


def by_row(runs: list[dict], version: str, metric: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in runs:
        if r["version"] != version:
            continue
        v = value(r, metric)
        if v is not None:
            out.setdefault(r["question"], []).append(v)
    return out


@dataclass
class Paired:
    metric: str
    base: str
    cand: str
    n_rows: int
    mean_base: float
    mean_cand: float
    diff: float           # cand - base, averaged over rows
    lo: float
    hi: float
    sd_diff: float

    @property
    def pct(self) -> float:
        return 100 * self.diff / self.mean_base if self.mean_base else float("nan")

    @property
    def pct_lo(self) -> float:
        return 100 * self.lo / self.mean_base if self.mean_base else float("nan")

    @property
    def pct_hi(self) -> float:
        return 100 * self.hi / self.mean_base if self.mean_base else float("nan")

    @property
    def direction(self) -> str:
        """HIGHER / LOWER / NO DETECTABLE DIFFERENCE. Pure arithmetic."""
        if self.n_rows < 2:
            return "TOO FEW ROWS"
        if self.lo > 0:
            return "HIGHER"
        if self.hi < 0:
            return "LOWER"
        return "NO DETECTABLE DIFFERENCE"

    @property
    def verdict(self) -> str:
        """REGRESSION / IMPROVEMENT / NO DETECTABLE DIFFERENCE."""
        d = self.direction
        if d not in ("HIGHER", "LOWER"):
            return d
        worse = HIGHER_IS_WORSE.get(self.metric, True)
        if worse is None:
            return d
        return "REGRESSION" if (d == "HIGHER") == worse else "IMPROVEMENT"

    def line(self) -> str:
        pct = (f"  ({self.pct:+.0f}%, CI {self.pct_lo:+.0f}% .. {self.pct_hi:+.0f}%)"
               if self.mean_base and not math.isnan(self.pct) else "")
        return (f"{self.metric:<20} {self.base} {self.mean_base:9.2f} -> {self.cand} "
                f"{self.mean_cand:9.2f}  diff {self.diff:+9.2f} "
                f"[{self.lo:+.2f}, {self.hi:+.2f}]{pct}  n={self.n_rows}  {self.verdict}")


def paired(runs: list[dict], base: str, cand: str, metric: str) -> Paired:
    """Average the repetitions WITHIN each row first, then pair rows.

    Rows are matched by QUESTION TEXT, never by position -- two experiments do
    not return their rows in the same order, and a positional zip would pair
    unrelated questions and still print a perfectly plausible interval.
    """
    b, c = by_row(runs, base, metric), by_row(runs, cand, metric)
    rows = sorted(set(b) & set(c))
    mb = [statistics.fmean(b[q]) for q in rows]
    mc = [statistics.fmean(c[q]) for q in rows]
    d = [y - x for x, y in zip(mb, mc)]
    n = len(d)
    if n == 0:
        return Paired(metric, base, cand, 0, float("nan"), float("nan"),
                      float("nan"), float("nan"), float("nan"), float("nan"))
    mean_d = statistics.fmean(d)
    sd = statistics.stdev(d) if n > 1 else float("nan")
    half = t975(n - 1) * sd / math.sqrt(n) if n > 1 else float("inf")
    return Paired(metric, base, cand, n, statistics.fmean(mb), statistics.fmean(mc),
                  mean_d, mean_d - half, mean_d + half, sd)


def within_row_sigma(runs: list[dict], version: str, metric: str) -> tuple[float, int, float]:
    """Pooled run-to-run sd: how much the SAME question varies when run again.
    Returns (sigma, degrees_of_freedom, grand_mean). This is the number Session
    5 had from four runs of one question; here it has df = rows * (reps - 1)."""
    rows = by_row(runs, version, metric)
    ss, df, allv = 0.0, 0, []
    for vals in rows.values():
        if len(vals) < 2:
            continue
        m = statistics.fmean(vals)
        ss += sum((v - m) ** 2 for v in vals)
        df += len(vals) - 1
        allv.extend(vals)
    sigma = math.sqrt(ss / df) if df else float("nan")
    return sigma, df, (statistics.fmean(allv) if allv else float("nan"))


def row_pcts(runs: list[dict], base: str, cand: str, metric: str) -> dict[str, float]:
    """Per-question % change (rep-averaged). The mean of a paired difference can
    be one row wearing eleven rows' clothes: on 10 Sep, concise's -26% tokens
    was -52% on the multi-hop row and within +/-3% on 8 of the other 10."""
    b, c = by_row(runs, base, metric), by_row(runs, cand, metric)
    out = {}
    for q in sorted(set(b) & set(c)):
        mb = statistics.fmean(b[q])
        if mb:
            out[q] = 100 * (statistics.fmean(c[q]) - mb) / mb
    return out


def variance_share(runs: list[dict], version: str, metric: str) -> list[tuple[str, float, float, float]]:
    """Which rows the run-to-run noise comes from: [(question, share_of_SS, sd,
    mean)], largest share first. A pooled sigma assumes every row is equally
    noisy. On 10 Sep one row out of eleven held 98% of it."""
    rows = by_row(runs, version, metric)
    parts = []
    for q, vals in rows.items():
        if len(vals) < 2:
            continue
        m = statistics.fmean(vals)
        parts.append((q, sum((v - m) ** 2 for v in vals), statistics.stdev(vals), m))
    total = sum(p[1] for p in parts) or 1.0
    return sorted([(q, ss / total, sd, m) for q, ss, sd, m in parts],
                  key=lambda t: -t[1])


def without(runs: list[dict], question: str) -> list[dict]:
    return [r for r in runs if r["question"] != question]


def recommend(success: Paired, cost: Paired) -> tuple[str, str]:
    """The tie rule. Returns (decision, reason).

    1. Candidate detectably WORSE on success  -> keep the incumbent.
    2. Candidate detectably BETTER on success -> ship it (and report its cost).
    3. Success tied -> the tie goes to the cheaper agent:
         cost detectably lower  -> ship the candidate
         cost detectably higher -> keep the incumbent
         cost ALSO tied         -> keep the incumbent. You cannot say which is
                                   cheaper, and a change you cannot defend is
                                   not a change worth shipping.
    """
    s, c = success.direction, cost.direction
    if s == "LOWER":
        return "KEEP " + success.base, f"{success.metric} detectably worse"
    if s == "HIGHER":
        return "SHIP " + success.cand, f"{success.metric} detectably better (cost: {c.lower()})"
    if s != "NO DETECTABLE DIFFERENCE":
        return "NO DECISION", f"{success.metric}: {s}"
    if c == "LOWER":
        return "SHIP " + cost.cand, f"success tied; {cost.metric} detectably lower"
    if c == "HIGHER":
        return "KEEP " + cost.base, f"success tied; {cost.metric} detectably higher"
    return "KEEP " + cost.base, f"success tied AND {cost.metric} tied -- nothing to defend"


def load(path: str) -> list[dict]:
    with open(path) as fh:
        blob = json.load(fh)
    return blob["runs"] if isinstance(blob, dict) else blob


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="?", default="runs6.json")
    ap.add_argument("--base", default="healthy")
    ap.add_argument("--cand", action="append")
    ap.add_argument("--metric", action="append")
    args = ap.parse_args()
    runs = load(args.runs)
    cands = args.cand or sorted({r["version"] for r in runs} - {args.base})
    metrics = args.metric or ["outcome_keyword", "tokens_billed", "n_searches", "latency_s"]
    for cand in cands:
        print(f"\n{args.base} -> {cand}")
        for m in metrics:
            print("  " + paired(runs, args.base, cand, m).line())
        dec, why = recommend(paired(runs, args.base, cand, "outcome_keyword"),
                             paired(runs, args.base, cand, "tokens_billed"))
        print(f"  ==> {dec}   ({why})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
