"""
Session 9 — the trajectory-judge harness. One record shape, one phase field, no pooling.

    python traj_bench9.py                      # stub, free, 60 verdicts
    python traj_bench9.py --live               # real model, 60 verdicts
    python traj_bench9.py --live --wobble 10   # + 90 more

WHAT A RECORD IS
----------------
One VERDICT: one judge, one trajectory, once.

    phase     "gate" | "wobble" | "attack"  -- which measurement this belongs to
    row_id    which engineer's request
    arm       which seeded trajectory (healthy, wrong_delegation, ...)
    judge     which of the three judges
    rep       1..n
    verdict   SOUND | UNSOUND | INSUFFICIENT-EVIDENCE
    score     1 | 0 | None
    expected  what judge9.EXPECT says this judge should have returned
    correct   score == expected, or None when there is no key
    n_calls   how many agents ran -- Session 9's bias column, see below
    chars     length of the rendered trajectory the judge read

`phase` is stamped AT CREATION and `save()` RAISES on a record without one. Session 7
shipped a runs file that was three measurements concatenated with no field telling them
apart, and it put two different wrong numbers on two different screens. The fix is not
"be careful", it is a field and an exception. Session 8 kept it. So does this.

THE PHASES ARE NOT POOLABLE
---------------------------
    gate     4 rows x 5 arms x 3 judges. Measures SEPARATION: does the judge fire on
             the broken trajectory and stay quiet on the ones it should pass?
    wobble   the same judge, the same trajectory, n times. Disagreement with ITSELF.
             The denominator: a separation of 60% means nothing until you know whether
             the judge wobbles by 10% or by 70%.
    attack   student-written trajectories from the homework. No answer key beyond the
             attacker's own claim, which is why it is separate and never averaged in.

WHY FOUR ROWS AND NOT ONE
--------------------------
Session 8 used ONE report per arm and took its separation from 3 reps of it. Three reps
of one report tells you the judge is consistent; it does not tell you the judge
generalises. The same budget spent on 4 DIFFERENT requests per arm buys strictly more
information for the same number of calls, and it is the reason `traj9.GATE_ROWS` has
four entries rather than one. See `traj9.GATE_ROWS` for why those four.

`n_calls` IS SESSION 9's VERBOSITY COLUMN
------------------------------------------
Session 8 found its judges responded to LENGTH: `healthy` and `padded` are the same
report, and `workflow_coherence` fired 0/3 and 3/3. The trajectory analogue is path
length -- `healthy` runs 3 agents, `delegation_loop` runs 8. A judge that fires more as
the path gets longer may be detecting inefficiency, or may be detecting size. Recording
`n_calls` on every verdict is what lets `agree9.path_length_bias()` tell those apart
without spending a single extra call.
"""

from __future__ import annotations

import _path  # noqa: F401  -- shared/ and plant/ on sys.path; must be first

import argparse
import json
import time
from datetime import datetime

try:                                   # every entry point in this course loads .env
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import judge9
import traj9

__version__ = "s9-2026-09-20a"

PROJECT = "session-9-trajectories"

# The trajectories the wobble measurement repeats. Chosen so the answer is informative
# whichever way it comes out:
#   HW-001/healthy         a path every judge should wave through
#   HW-001/lost_handoff    the arm this session predicts will be missed
#   HW-001/delegation_loop the longest path in the set (8 invocations)
# If a judge is stable on the first two and unstable on the third, the instability is
# path LENGTH, not difficulty -- and that is a finding, not noise.
WOBBLE_TRAJECTORIES = (("HW-001", "healthy"),
                       ("HW-001", "lost_handoff"),
                       ("HW-001", "delegation_loop"))

_VERDICT_OF = {1: "SOUND", 0: "UNSOUND", None: "INSUFFICIENT-EVIDENCE"}


def _record(phase: str, row_id: str, arm: str, judge_key: str, rep: int,
            result: dict, outputs: dict, latency_s: float | None = None,
            stub: bool = False, expected=None) -> dict:
    score = result["score"]
    calls = [a for a in (outputs.get("agent_calls") or []) if a != "planner"]
    return {
        "phase": phase,
        "row_id": row_id,
        "arm": arm,
        "judge": judge_key,
        "rep": rep,
        "verdict": _VERDICT_OF[score],
        "score": score,
        "expected": expected,
        "correct": None if expected is None else (score == expected),
        "comment": result["comment"],
        "n_calls": len(calls),
        "chars": len(traj9.render(outputs)),
        "latency_s": latency_s,
        "stub": stub,
    }


def _score_one(phase, row_id, arm, rep, stub, verbose, expected_from_key=True):
    outputs = traj9.trajectory(row_id, arm)
    recs = []
    for j in judge9.judges(stub=stub):
        t0 = time.perf_counter()
        res = j(outputs, None)
        dt = round(time.perf_counter() - t0, 3)
        exp = judge9.EXPECT.get(arm, {}).get(j.judge_key) if expected_from_key else None
        rec = _record(phase, row_id, arm, j.judge_key, rep, res, outputs, dt, stub, exp)
        recs.append(rec)
        if verbose:
            mark = "." if rec["correct"] else ("X" if rec["correct"] is False else "-")
            print(f"  {mark} {row_id} {arm:17s} {j.judge_key:20s} "
                  f"{rec['verdict']:22s} {dt:5.1f}s", flush=True)
    return recs


def gate(rows=traj9.GATE_ROWS, arms=traj9.ARMS, stub: bool = True, reps: int = 1,
         verbose: bool = True) -> list[dict]:
    """Every judge against every arm of every gate row."""
    recs: list[dict] = []
    for rep in range(1, reps + 1):
        for row_id in rows:
            for arm in arms:
                recs += _score_one("gate", row_id, arm, rep, stub, verbose)
    return recs


def wobble(which=WOBBLE_TRAJECTORIES, stub: bool = True, n: int = 10,
           verbose: bool = True) -> list[dict]:
    """The same judge, the same trajectory, n times."""
    recs: list[dict] = []
    for row_id, arm in which:
        before = len(recs)
        for rep in range(1, n + 1):
            recs += _score_one("wobble", row_id, arm, rep, stub, verbose=False)
        if verbose:
            for key in judge9.JUDGE_KEYS:
                got = [r["verdict"] for r in recs[before:] if r["judge"] == key]
                uniq = sorted(set(got))
                shape = ("UNANIMOUS " + uniq[0]) if len(uniq) == 1 else "SPLIT " + "/".join(uniq)
                print(f"  {row_id}/{arm:17s} {key:20s} {shape}", flush=True)
    return recs


def calls_for(rows=traj9.GATE_ROWS, arms=traj9.ARMS, reps: int = 1,
              wobble_n: int = 0, which=WOBBLE_TRAJECTORIES) -> dict:
    """What a live run will COST, derived from the same tuples the run iterates.

    Session 8's correction 8 is why this function exists rather than a number in a
    docstring: four files claimed `screen_my_attack.py` made one model call when it made
    eight, the run sheet budgeted a fifth of the truth, and nobody noticed until the
    night before class. Anything that quotes a call count -- the run sheet, the notebook,
    the homework email -- calls this. Nothing types one.
    """
    per = judge9.LIVE_CALLS_PER_TRAJECTORY
    g = len(rows) * len(arms) * reps * per
    w = len(which) * wobble_n * per
    return {"gate": g, "wobble": w, "total": g + w, "per_trajectory": per}


def save(recs: list[dict], path: str = "traj_runs9.json", **meta) -> str:
    missing = [r for r in recs if not r.get("phase")]
    if missing:
        raise ValueError(
            f"{len(missing)} verdict(s) have no `phase`. An untagged runs file is the "
            "Session 7 bug that put -4% on a slide and -25% in the notebook.")
    stubbed = sum(1 for r in recs if r.get("stub"))
    payload = {
        "version": __version__,
        # Stamped, because preflight8 did not and every data slide on the projector
        # read "measured ?" in grey -- worse than no stamp, because it looks like a
        # measurement whose date nobody can produce.
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "project": PROJECT,
        "judge_version": judge9.__version__,
        "traj_version": traj9.__version__,
        "stub_verdicts": stubbed,
        "all_stub": stubbed == len(recs),
        **meta,
        "verdicts": recs,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=str)
    return path


def load(path: str = "traj_runs9.json") -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["verdicts"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Session 9 trajectory-judge harness")
    ap.add_argument("--live", action="store_true",
                    help="use the real model. Without it everything is the stub, which "
                         "tests our plumbing and nothing about judges.")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--wobble", type=int, default=0, metavar="N")
    ap.add_argument("--save", metavar="PATH", nargs="?", const="traj_runs9.json")
    a = ap.parse_args()
    stub = not a.live

    budget = calls_for(reps=a.reps, wobble_n=a.wobble)
    print(f"traj_bench9 {__version__} — {'STUB (plumbing only)' if stub else 'LIVE'}")
    print(f"  model calls this run: {0 if stub else budget['total']} "
          f"(gate {budget['gate']}, wobble {budget['wobble']})\n")

    print(f"SEPARATION — {len(traj9.GATE_ROWS)} rows x {len(traj9.ARMS)} arms x "
          f"{len(judge9.JUDGE_KEYS)} judges"
          + (f" x {a.reps} reps" if a.reps > 1 else ""))
    recs = gate(stub=stub, reps=a.reps)

    if a.wobble:
        print(f"\nSELF-AGREEMENT — {len(WOBBLE_TRAJECTORIES)} trajectories x "
              f"{len(judge9.JUDGE_KEYS)} judges x {a.wobble}")
        recs += wobble(stub=stub, n=a.wobble)

    keyed = [r for r in recs if r["correct"] is not None]
    print(f"\n  agreement with the answer key: {sum(1 for r in keyed if r['correct'])}"
          f"/{len(keyed)}")
    print(f"  model calls made: {0 if stub else len(recs)}")
    if a.save:
        print("  saved ->", save(recs, a.save, live=not stub))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
