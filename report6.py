"""
Session 6 — Hands-on 6. The evaluation report, and your recommendation.

    python report6.py                   # writes report6_<author>.md from criteria6.py + runs6.json

The report is generated; the RECOMMENDATION is not. The last section of the
file is a blank you fill in by hand, in one sentence, and it must quote an
interval. "concise is 26% cheaper" is not allowed. "concise's token change is
-26%, 95% interval -75% to +23%, so we keep healthy" is.

This is the shape of the mid-term deliverable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time

import paired as P
from consistency6 import QUALITY, reliability
from make_regression_set import baselines, within_baseline
from regress6 import METRICS, RATES, against_bar, load_criteria, size


def build(runs: list[dict], blob: dict, C) -> str:
    base = baselines(runs)
    L = [f"# Regression report — {C.AUTHOR}",
         "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `report6.py`. "
         f"Runs: `{blob.get('dataset')}@{blob.get('tag')}`, {blob.get('reps')} repetitions per "
         f"question, made {blob.get('generated')}. Incumbent: **healthy**.",
         "",
         "**Token definition:** tokens_billed = output + uncached input. Cached reads "
         "excluded; reasoning tokens in their own column.",
         "",
         f"**Sample:** {len({r.get('example_id') for r in runs})} rows, "
         f"{len({r['question'] for r in runs})} distinct questions (identical inputs are "
         "paired once).",
         "",
         "## 1. Criteria (written before the numbers)",
         "",
         "| metric | success bar | smallest change we act on |",
         "|---|---|---|"]
    for m in sorted(set(C.SUCCESS_BAR) | set(C.ACT_IF)):
        unit = "pt" if m in RATES else "%"
        L.append(f"| {m} | {C.SUCCESS_BAR.get(m, '—')} | "
                 f"{C.ACT_IF.get(m, '—')}{unit if m in C.ACT_IF else ''} |")

    L += ["", "## 2. Reliability — pass@1 / pass^5", "",
          "| version | " + " | ".join(QUALITY) + " | tokens/run | searches/run |",
          "|---|" + "---|" * (len(QUALITY) + 2)]
    for v in ("healthy", "redundant", "concise"):
        cells = []
        for m in QUALITY:
            p1, pk, _ = reliability(runs, v, m)
            cells.append(f"{p1:.2f} / {pk:.2f}")
        mine = [r["outputs"]["metrics"] for r in runs if r["version"] == v and r.get("outputs")]
        tok = sum(m["tokens_billed"] for m in mine) / len(mine)
        se = sum(m["n_searches"] for m in mine) / len(mine)
        L.append(f"| {v} | " + " | ".join(cells) + f" | {tok:,.0f} | {se:.2f} |")

    for cand in ("redundant", "concise"):
        L += ["", f"## 3. healthy → {cand}", "",
              "| metric | change | 95% interval | our bar | verdict |",
              "|---|---|---|---|---|"]
        for m in METRICS:
            p = P.paired(runs, "healthy", cand, m)
            est, lo, hi = size(p)
            unit = "pt" if m in RATES else "%"
            L.append(f"| {m} | {est:+.0f}{unit} | [{lo:+.0f}, {hi:+.0f}]{unit} | "
                     f"{C.ACT_IF[m]}{unit} | {against_bar(p, C.ACT_IF[m])} |")
        pcts = P.row_pcts(runs, "healthy", cand, "tokens_billed")
        med = sorted(pcts.values())[len(pcts) // 2]
        mine = [r for r in runs if r["version"] == cand and r.get("outputs")]
        ok = sum(all(x["score"] for x in within_baseline(
            r["outputs"], {"baseline": base[r["question"]]})) for r in mine)
        dec, why = P.recommend(P.paired(runs, "healthy", cand, "outcome_keyword"),
                               P.paired(runs, "healthy", cand, "tokens_billed"))
        L += ["",
              f"- Median question's token change: **{med:+.0f}%** (the mean above can be "
              "one question).",
              f"- Regression-set rule: {ok}/{len(mine)} runs within 25% of healthy's median "
              "on the same question.",
              f"- Tie rule: **{dec}** — {why}."]

    # Caveats are COMPUTED, not typed: a hard-coded caveat is a claim about last
    # night's data that will still be printed after the data changes.
    L += ["", "## 4. Caveats we are required to state", ""]
    for m in QUALITY:
        vals = [(r.get("scores") or {}).get(m) for r in runs if r.get("outputs")]
        if vals and all(bool(v) for v in vals):
            L.append(f"- `{m}` passed all {len(vals)} runs of every version. A tie on it is "
                     "not evidence of equal quality — it cannot fail on these rows.")
    shares = P.variance_share(runs, "healthy", "tokens_billed")
    if shares and shares[0][1] >= 0.5:
        L.append(f"- {shares[0][1]:.0%} of healthy's run-to-run token noise comes from ONE "
                 f"question ({shares[0][0][:60]}…). The intervals are wide because of it.")
    L += ["- Latency was measured with 4 runs in parallel. Compare versions to each other, "
          "not to a latency measured alone.",
          f"- One provider, one night, {blob.get('reps')} repetitions per question.",
          "", "## 5. Our recommendation (write ONE sentence; it must quote an interval)", "",
          "> TODO", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs6.json")
    ap.add_argument("--criteria", default="criteria6.py")
    args = ap.parse_args()
    C = load_criteria(args.criteria)
    with open(args.runs) as fh:
        blob = json.load(fh)
    md = build(blob["runs"], blob, C)
    slug = re.sub(r"[^a-z0-9]+", "_", str(C.AUTHOR).lower()).strip("_") or "pair"
    path = f"report6_{slug}.md"
    with open(path, "w") as fh:
        fh.write(md)
    print(f"  wrote {path}. Open it, and replace the TODO in section 5 with one sentence "
          "that quotes an interval.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
