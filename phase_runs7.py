#!/usr/bin/env python
"""
ONE-TIME REPAIR -- label the runs in runs7.json with the phase that produced them.

WHY THIS EXISTS
    runs7.json is three different measurements concatenated: the stub seed
    matrix, the live tail-contract probe (check 7), and the live comparison
    (check 8). They were saved with no field distinguishing them. slide 20
    was built from the comparison batch alone; the notebook's COMPARE cell
    read the whole file, so `pipeline` got 6-7 reps per row (two batches)
    while `single` got 3. The deck said -4% on task outcome, the notebook
    said -25%, and both were correct on the runs they were handed.

    bench7.run_matrix now stamps `phase` at creation and bench7.save refuses
    untagged records, so this cannot recur. This script backfills the file we
    already paid for, rather than re-running $1.98 of live agents.

HOW THE BOUNDARY IS ESTABLISHED -- and it is checked, not assumed
    The comparison batch is the tail of the file. This script finds it by
    recomputing the four paired intervals on the candidate slice and
    requiring them to reproduce deck/deck7_data.json to 1e-6. If they do not,
    it writes nothing.

NOT TOUCHED: every score, metric, output and comment is copied verbatim.
    Same discipline as relabel_runs7.py.
"""
from __future__ import annotations

import json
import sys

import paired

SRC = "runs7.json"
DECK = "deck/deck7_data.json"
METRICS = ("outcome_match", "tokens_billed", "latency_s", "n_tool_calls")
TOL = 1e-6


def main() -> int:
    d = json.load(open(SRC, encoding="utf-8"))
    runs = d["runs"]
    if all(r.get("phase") for r in runs):
        print(f"{SRC}: already phased. Nothing to do."); return 0

    want = json.load(open(DECK, encoding="utf-8")).get("comparison") or {}
    if not want:
        print(f"{DECK} has no comparison block. Cannot verify a boundary."); return 1

    # The comparison batch is a suffix of the file. Find the shortest suffix
    # that reproduces the deck.
    hit = None
    for start in range(len(runs) - 1, -1, -1):
        sub = runs[start:]
        if sum(1 for r in sub if r.get("version") == "single") < 12:
            continue
        try:
            got = {m: paired.paired(sub, "pipeline", "single", m) for m in METRICS}
        except Exception:
            continue
        if any(p.n_rows != want[m]["n_rows"] for m, p in got.items()):
            continue
        if all(abs(got[m].pct - want[m]["est"]) < TOL
               and abs(got[m].pct_lo - want[m]["lo"]) < TOL
               and abs(got[m].pct_hi - want[m]["hi"]) < TOL for m in METRICS):
            hit = start
            break

    if hit is None:
        print("No suffix of runs7.json reproduces the deck's comparison. "
              "Refusing to guess a boundary. Nothing written."); return 1

    for i, r in enumerate(runs):
        if i >= hit:
            r["phase"] = "comparison"
        elif r.get("impl") == "llm" or r.get("seed") == "healthy" and False:
            r["phase"] = "matrix"
        else:
            r["phase"] = "matrix"
    # the three check-7 probes sit immediately before the comparison batch and
    # are live pipeline runs on the live rows; they are not stub matrix runs.
    live_rows = set(json.load(open(DECK, encoding="utf-8")).get("live_rows") or [])
    for r in runs[max(0, hit - len(live_rows)):hit]:
        if r.get("row_id") in live_rows and r.get("version") == "pipeline":
            r["phase"] = "tail_contract"

    n = {}
    for r in runs:
        n[r["phase"]] = n.get(r["phase"], 0) + 1
    d["phased"] = {"on": "2026-09-13", "boundary_index": hit, "counts": n,
                   "note": "labels only; no score, metric, output or comment changed"}
    with open(SRC, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, default=str)
    print(f"{SRC}: phased at index {hit}.  " +
          "  ".join(f"{k}={v}" for k, v in sorted(n.items())))
    print("verified: the comparison slice reproduces deck/deck7_data.json to 1e-6.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
