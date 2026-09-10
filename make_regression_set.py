"""
Session 6 — Hands-on 4. Turn the benchmark into a REGRESSION set.

    python make_regression_set.py --dry     # print what would be pushed
    python make_regression_set.py           # create it in YOUR LangSmith and tag it

WHAT MAKES A BENCHMARK A REGRESSION SET
---------------------------------------
A benchmark row says what a RIGHT answer looks like (`must_contain`, the tools).
A regression row also says what the INCUMBENT did on it: how many tokens,
how many searches, how slow. The reference is no longer only "correct" -- it
is "correct, and no worse than what is in production today".

So this script takes the 12 `v1` rows and adds a `baseline` block to each
row's reference outputs, measured from healthy's 5 runs of that question. Then
it tags the result `baseline-healthy`. The next candidate is scored against
the baseline row by row, by `within_baseline` below -- a rule, no model.

WHY THE MEDIAN, NOT THE MEAN: the multi-hop question ran 15k to 33k tokens
across five identical runs. A mean baseline moves with one unlucky run; a
median does not.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import textwrap
from collections import Counter, defaultdict

REG_DATASET = "s6-regression-baseline"
REG_TAG = "baseline-healthy"
BASELINE_VERSION = "healthy"
TOLERANCE = 0.25        # a run may exceed its row's baseline by 25% before it fails


def baselines(runs: list[dict], version: str = BASELINE_VERSION) -> dict[str, dict]:
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r["version"] == version and r.get("outputs"):
            by_q[r["question"]].append(r["outputs"]["metrics"])
    return {q: {"version": version, "n_runs": len(ms),
                "tokens_billed": statistics.median(m["tokens_billed"] for m in ms),
                "n_searches": statistics.median(m["n_searches"] for m in ms),
                "latency_s": statistics.median(m["latency_s"] for m in ms)}
            for q, ms in by_q.items()}


def within_baseline(outputs: dict, reference_outputs: dict) -> list[dict]:
    """Rule-based regression evaluator. One verdict per metric: did this run stay
    within TOLERANCE of what the incumbent did on the SAME question?"""
    base = (reference_outputs or {}).get("baseline") or {}
    m = (outputs or {}).get("metrics") or {}
    out = []
    for k in ("tokens_billed", "n_searches"):
        if k in base and k in m:
            limit = base[k] * (1 + TOLERANCE)
            out.append({"key": f"within_baseline_{k}", "score": m[k] <= limit,
                        "comment": f"{m[k]:.0f} vs baseline {base[k]:.0f} (limit {limit:.0f})"})
    return out


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs6.json")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    with open(args.runs) as fh:
        runs = json.load(fh)["runs"]
    base = baselines(runs)

    import instructor_pool
    rows = instructor_pool.rows_for_pool()
    payload = []
    for r in rows:
        q = r["inputs"]["question"]
        ref = dict(r["outputs"])
        ref["baseline"] = base[q]
        payload.append({"inputs": r["inputs"], "outputs": ref,
                        "metadata": dict(r.get("metadata", {}), baseline_of=BASELINE_VERSION)})

    print(f"  {len(payload)} rows. Each row's baseline = the median of {BASELINE_VERSION.upper()}'s runs on that row.")
    print(f"  {BASELINE_VERSION} is the incumbent: the baseline is what production does today.")
    print(f"  redundant and concise are NOT in the baseline -- they are the candidates scored against it.")
    print(f"  A candidate run FAILS a row if it goes more than {TOLERANCE:.0%} over that row's baseline.\n")
    spread: dict[str, list[float]] = defaultdict(list)       # healthy's tokens, per question
    for r in runs:
        if r["version"] == BASELINE_VERSION and r.get("outputs"):
            spread[r["question"]].append(r["outputs"]["metrics"]["tokens_billed"])
    twice = Counter(p["inputs"]["question"] for p in payload)
    for i, p in enumerate(payload, 1):
        q, b = p["inputs"]["question"], p["outputs"]["baseline"]
        t = spread[q]
        print(textwrap.fill(f"{i:>2}. {q}", width=100, subsequent_indent="    "))
        print(f"    baseline:  tokens {b['tokens_billed']:>7,.0f}   searches {b['n_searches']:.0f}"
              f"      <- median of {BASELINE_VERSION}'s {b['n_runs']} runs")
        print(f"    {BASELINE_VERSION}'s runs: cheapest {min(t):>7,.0f}   priciest {max(t):>7,.0f}   "
              f"mean {statistics.fmean(t):>7,.0f}")
        if twice[q] > 1:
            print("    (this question is in the dataset twice: both rows share one baseline)")
        print()
    if args.dry:
        print("  --dry: nothing pushed.")
        return 0

    from langsmith import Client
    client = Client()
    if client.has_dataset(dataset_name=REG_DATASET):
        n = len(list(client.list_examples(dataset_name=REG_DATASET)))
        print(f"  {REG_DATASET!r} already exists ({n} examples). Not pushing twice — "
              "delete it in the UI to rebuild.")
        return 0
    ds = client.create_dataset(dataset_name=REG_DATASET,
                               description="v1 rows + healthy's per-question baseline. "
                                           "Session 6 regression set.")
    client.create_examples(dataset_id=ds.id, examples=payload)
    versions = list(client.list_dataset_versions(dataset_name=REG_DATASET, limit=1))
    exact = client.read_dataset_version(dataset_name=REG_DATASET, as_of=versions[0].as_of)
    client.update_dataset_tag(dataset_name=REG_DATASET, as_of=exact.as_of, tag=REG_TAG)
    print(f"  created {REG_DATASET!r}, tagged {exact.as_of} as {REG_TAG!r}")
    print("  A candidate is now scored against the incumbent ROW BY ROW, by a rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
