"""
Session 8 — the judge harness. One record shape, one phase field, no pooling.

    python judge_bench8.py                 # stub, free, 24 verdicts
    python judge_bench8.py --live          # real model, 24 verdicts
    python judge_bench8.py --live --wobble 10

WHAT A RECORD IS
----------------
One VERDICT: one judge, one report, once.

    phase     "seeded" | "wobble" | "attack"   -- which measurement this belongs to
    arm       which seeded report (healthy, wrong_evidence, ...)
    judge     which of the four judges
    rep       1..n
    verdict   SOUND | UNSOUND | INSUFFICIENT-EVIDENCE
    score     1 | 0 | None
    expected  what the answer key says this judge should have returned, or None
    correct   score == expected, or None when there is no key
    chars     length of the report the judge read (the verbosity column)

`phase` is stamped AT CREATION and `save()` raises on a record without one. This is
not defensive programming for its own sake: Session 7 shipped a runs file that was
three measurements concatenated with no field telling them apart, and it put two
different wrong numbers on two different screens before anything caught it. The fix is
not "be careful", it is a field and an exception.

THE THREE PHASES ARE NOT POOLABLE, EVER
---------------------------------------
    seeded   six arms x four judges. Measures SEPARATION: does the judge fire on the
             broken report and stay quiet on the two controls?
    wobble   the same judge, the same report, n times. Measures the judge's
             disagreement with ITSELF. This is the denominator of the whole session.
    attack   student-written reports from the hands-on. No answer key beyond the
             attacker's own claim, which is why it is a separate phase and never
             averaged into either of the others.

A separation of 60% means nothing until you know whether the judge wobbles by 10% or
by 70%. Pool the phases and you can compute a number that answers neither question.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

try:                                   # bench7's reasoning: every entry point imports this
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import judge8
import judge_seeds8 as seeds8

__version__ = "s8-2026-09-15a"

PROJECT = "session-8-llm-judges"

# The three reports the wobble measurement uses. Chosen on purpose:
#   healthy         a report every judge should wave through
#   wrong_evidence  a report one judge should stop
#   padded          the same content as healthy, four times longer
# If a judge is stable on the first two and unstable on the third, the instability is
# length, not difficulty -- and that is a finding, not noise.
WOBBLE_ARMS = ("healthy", "wrong_evidence", "padded")

_VERDICT_OF = {1: "SOUND", 0: "UNSOUND", None: "INSUFFICIENT-EVIDENCE"}


def _record(phase: str, arm: str, judge_key: str, rep: int, result: dict,
            chars: int, expected=None, latency_s: float | None = None,
            stub: bool = False) -> dict:
    score = result["score"]
    return {
        "phase": phase,
        "arm": arm,
        "judge": judge_key,
        "rep": rep,
        "verdict": _VERDICT_OF[score],
        "score": score,
        "expected": expected,
        "correct": None if expected is None else (score == expected),
        "comment": result["comment"],
        "chars": chars,
        "latency_s": latency_s,
        "stub": stub,
    }


def score_arms(arms: dict[str, dict] | None = None, stub: bool = True, reps: int = 1,
               phase: str = "seeded", verbose: bool = True) -> list[dict]:
    """Every judge against every seeded arm. 6 x 4 x reps verdicts."""
    arms = arms if arms is not None else seeds8.build()
    js = judge8.judges(stub=stub)
    recs: list[dict] = []
    for rep in range(1, reps + 1):
        for arm, outputs in arms.items():
            for j in js:
                t0 = time.perf_counter()
                res = j(outputs, None)
                dt = round(time.perf_counter() - t0, 3)
                exp = seeds8.EXPECT.get(arm, {}).get(j.judge_key)
                rec = _record(phase, arm, j.judge_key, rep, res,
                              len(outputs.get("answer", "")), exp, dt, stub)
                recs.append(rec)
                if verbose:
                    mark = "." if rec["correct"] else ("X" if rec["correct"] is False else "-")
                    print(f"  {mark} rep{rep} {arm:16s} {j.judge_key:22s} "
                          f"{rec['verdict']:22s} {dt:5.1f}s", flush=True)
    return recs


def wobble(arms: dict[str, dict] | None = None, stub: bool = True, n: int = 10,
           which=WOBBLE_ARMS, verbose: bool = True) -> list[dict]:
    """The same judge, the same report, n times.

    Session 5 did this once, on one binary judge, n=5: unanimous, spread 1.16x, and
    the rule of three still only bounded the flip rate below 60%. n=10 takes that
    bound to 30%. The bound is the number that matters, not the flips you happened
    to see.
    """
    arms = arms if arms is not None else seeds8.build()
    js = judge8.judges(stub=stub)
    recs: list[dict] = []
    for arm in which:
        outputs = arms[arm]
        for j in js:
            for rep in range(1, n + 1):
                t0 = time.perf_counter()
                res = j(outputs, None)
                dt = round(time.perf_counter() - t0, 3)
                recs.append(_record("wobble", arm, j.judge_key, rep, res,
                                    len(outputs.get("answer", "")),
                                    seeds8.EXPECT.get(arm, {}).get(j.judge_key), dt, stub))
            if verbose:
                got = [r["verdict"] for r in recs[-n:]]
                uniq = sorted(set(got))
                print(f"  {arm:16s} {j.judge_key:22s} "
                      f"{'UNANIMOUS ' + uniq[0] if len(uniq) == 1 else 'SPLIT ' + '/'.join(uniq)}",
                      flush=True)
    return recs


def save(recs: list[dict], path: str = "judge_runs8.json", **meta) -> str:
    missing = [r for r in recs if not r.get("phase")]
    if missing:
        raise ValueError(
            f"{len(missing)} verdict(s) have no `phase`. An untagged runs file is the "
            "Session 7 bug that put -4% on a slide and -25% in the notebook.")
    stubbed = sum(1 for r in recs if r.get("stub"))
    payload = {
        "version": __version__,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "project": PROJECT,
        "judge_version": judge8.__version__,
        "seeds_version": seeds8.__version__,
        # Stamped so nothing downstream can mistake plumbing for a measurement.
        "stub_verdicts": stubbed,
        "all_stub": stubbed == len(recs),
        **meta,
        "verdicts": recs,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=str)
    return path


def load(path: str = "judge_runs8.json") -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["verdicts"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Session 8 judge harness")
    ap.add_argument("--live", action="store_true",
                    help="use the real model. Without it everything is the stub, "
                         "which tests our plumbing and nothing about judges.")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--wobble", type=int, default=0, metavar="N",
                    help="also run the self-agreement measurement, N repeats")
    ap.add_argument("--save", metavar="PATH", nargs="?", const="judge_runs8.json")
    args = ap.parse_args()
    stub = not args.live

    arms = seeds8.build()
    print(f"judge_bench8 {__version__} — {'STUB (plumbing only)' if stub else 'LIVE'}\n")
    print("SEPARATION — 6 arms x 4 judges"
          f"{' x ' + str(args.reps) + ' reps' if args.reps > 1 else ''}")
    recs = score_arms(arms, stub=stub, reps=args.reps)

    if args.wobble:
        print(f"\nSELF-AGREEMENT — {len(WOBBLE_ARMS)} reports x 4 judges x {args.wobble}")
        recs += wobble(arms, stub=stub, n=args.wobble)

    keyed = [r for r in recs if r["correct"] is not None]
    right = sum(1 for r in keyed if r["correct"])
    print(f"\n  agreement with the answer key: {right}/{len(keyed)}")
    print(f"  model calls made: {0 if stub else len(recs)}")

    if args.save:
        print("  saved ->", save(recs, args.save, live=not stub))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
