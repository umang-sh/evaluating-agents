"""
Session 11 -- the state capture. INSTRUCTOR_ONLY.

Runs the HEALTHY four-agent pipeline (no seed) on every Session 7 row, `--reps`
times, and saves each run WITH its per-node state history (`state_history`,
`final_state` -- added to bench7 for Session 11).

Every record is tagged phase="state_capture" (or "state_capture_stub" with
--stub), so it can never pool with Session 7's `matrix` / `comparison` runs.
bench7.save() raises on a record with no phase.

The file is re-saved after EVERY run (runs11.partial.json), so a crash at run 20
keeps 19. The final file is written only when every run finished.

    python session-11/capture11.py                 # live, 12 rows x 2 reps = 24
    python session-11/capture11.py --stub          # free, deterministic, seconds
    python session-11/capture11.py --no-trace      # live, but log nothing to LangSmith
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first
import argparse
import os
import sys
import traceback

from dotenv import load_dotenv
load_dotenv(_path.ROOT / ".env")   # explicitly, BEFORE anything reads os.environ

import bench7
from delegation_rows7 import ROWS

HERE = _path.ROOT / "session-11"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stub", action="store_true")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--no-trace", action="store_true")
    a = ap.parse_args()

    impl = "stub" if a.stub else "llm"
    phase = "state_capture_stub" if a.stub else "state_capture"
    trace = (not a.stub) and (not a.no_trace)
    out = HERE / ("runs11_STUB.json" if a.stub else "runs11.json")
    partial = out.with_suffix(".partial.json")

    if impl == "llm" and not any(os.environ.get(k) for k in
                                 ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")):
        print("HARD STOP: no provider key after loading", _path.ROOT / ".env")
        return 2

    recs, errors = [], []
    total = len(ROWS) * a.reps
    with bench7.tracing_off(not trace):
        for rep in range(1, a.reps + 1):
            for row in ROWS:
                try:
                    rec = bench7.measure(row, "pipeline", impl=impl, seed="healthy",
                                         rep=rep, trace=trace)
                    rec["phase"] = phase
                    recs.append(rec)
                    fs = rec["outputs"]["final_state"]
                    print(f"  [{len(recs):2d}/{total}] rep{rep} {row['id']:8s} "
                          f"nodes={len(rec['outputs']['state_history'])} "
                          f"steps={fs.get('steps')} truncated={fs.get('truncated')}",
                          flush=True)
                except Exception as e:  # keep going; a lost run is reported, not hidden
                    errors.append({"row_id": row["id"], "rep": rep, "error": repr(e),
                                   "tb": traceback.format_exc()[-1500:]})
                    print(f"  ERROR rep{rep} {row['id']}: {e!r}", flush=True)
                bench7.save(recs, str(partial), phase=phase, impl=impl,
                            errors=errors, complete=False)

    if errors or len(recs) != total:
        print(f"INCOMPLETE: {len(recs)}/{total} runs, {len(errors)} errors. "
              f"Kept in {partial.name}; {out.name} NOT written.")
        return 1
    bench7.save(recs, str(out), phase=phase, impl=impl, errors=[], complete=True)
    try:
        partial.unlink(missing_ok=True)
    except OSError:      # a sandbox that forbids deletes; the partial is now redundant
        print(f"(could not delete {partial.name}; it is a duplicate, safe to remove)")
    print(f"saved {len(recs)} runs -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
