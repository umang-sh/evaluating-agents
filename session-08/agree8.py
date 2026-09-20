"""
Session 8 — does the judge separate things by more than it disagrees with itself?

    python agree8.py judge_runs8.json

THE SPINE, AS CODE:
    You cannot measure a difference smaller than your judge's own noise.

Session 6 said a number without a spread is not a measurement. Session 8 says it again
one level up, about the instrument: a judge score is a SAMPLE, not a reading. Ask the
same judge the same question twice and it may answer differently, and every verdict it
has ever given you sits inside that spread.

So there are two numbers per judge, and the session is the comparison between them.

    SEPARATION   how much more often the judge fires on the report it should stop
                 than on the reports it should wave through.

                     separation = P(UNSOUND | its own broken arm)
                                - P(UNSOUND | the arms it should pass)

    WOBBLE       how often the same judge, on the same unchanged report, disagrees
                 with its own most common answer.

If the lower bound of SEPARATION does not clear the upper bound of WOBBLE, the judge
is decoration. It may still be right. We just cannot show it, and a slide that claims
otherwise is claiming a difference smaller than the instrument.

WHY WILSON AND NOT A NORMAL APPROXIMATION
------------------------------------------
These are proportions from small n, and several of them will be 0/10 or 10/10. The
textbook p +/- 1.96*sqrt(p(1-p)/n) gives an interval of ZERO WIDTH at 0 and at 1 --
"we saw no disagreements, therefore the disagreement rate is exactly 0%, no
uncertainty". That is the most confident wrong answer in applied statistics and it is
one line of code away at all times. Wilson does not do it, and neither does the rule
of three (3/n), which Session 5 already taught for exactly this case.

No scipy: the course pin set does not have it. z = 1.96, two-sided 95%.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field

import judge8
import judge_seeds8 as seeds8

__version__ = "s8-2026-09-15a"

# Wilson, the rule of three and Newcombe moved to shared/intervals.py on 20 Sep 2026
# so Session 9 could use them too (session-09/ cannot import from session-08/).
# Verbatim move, no formula changed. Re-exported here so every existing caller --
# preflight8, sweep8, doctor8, the notebook -- keeps working unchanged.
import _path  # noqa: F401  -- shared/ on sys.path; judge8 moved there 20 Sep
from intervals import Z, newcombe, rule_of_three, wilson   # noqa: F401  (re-export)

# ---------------------------------------------------------------------------
@dataclass
class Separation:
    judge: str
    target_arm: str
    fired_on_target: int
    n_target: int
    fired_on_controls: int
    n_controls: int
    diff: float = 0.0
    lo: float = 0.0
    hi: float = 0.0

    def line(self) -> str:
        return (f"{self.judge:22s} fires {self.fired_on_target}/{self.n_target} on "
                f"{self.target_arm:15s} {self.fired_on_controls}/{self.n_controls} "
                f"elsewhere   sep {self.diff:+.0%} [{self.lo:+.0%}, {self.hi:+.0%}]")


@dataclass
class Wobble:
    judge: str
    flips: int = 0
    n: int = 0
    per_arm: dict = field(default_factory=dict)

    @property
    def rate(self) -> float:
        return self.flips / self.n if self.n else 0.0

    @property
    def upper(self) -> float:
        """Upper 95% bound on this judge's self-disagreement rate.

        Zero flips does NOT mean zero wobble. It means the rule of three, and with
        n=10 that is still 30% -- which is Session 5's lesson restated: five quiet
        runs bounded the rate below 60% and could not say the judge was stable.
        """
        if self.n == 0:
            return 1.0
        if self.flips == 0:
            return rule_of_three(self.n)
        return wilson(self.flips, self.n)[1]

    def line(self) -> str:
        shape = "unanimous" if self.flips == 0 else f"{self.flips} flip(s)"
        return (f"{self.judge:22s} {shape:14s} over {self.n:3d} repeats   "
                f"disagreement <= {self.upper:.0%}")


# ---------------------------------------------------------------------------
def _seeded(recs: list[dict]) -> list[dict]:
    return [r for r in recs if r["phase"] == "seeded"]


def target_arms(judge_key: str) -> list[str]:
    """Every arm this judge is supposed to stop.

    Plural since 17 Sep. `workflow_coherence` now owns two: `contradiction`, which
    I built, and `real_contradiction`, which the four agents built without being
    asked. Keeping them separate would be tidier and would throw away the only arm
    in the set whose flaw is not mine.
    """
    hits = [a for a, exp in seeds8.EXPECT.items() if exp.get(judge_key) == 0]
    if not hits:
        raise ValueError(f"{judge_key} has no target arm — it cannot fail, so it "
                         f"measures nothing (Session 6's retired evaluators)")
    return sorted(hits)


def target_arm(judge_key: str) -> str:
    """Back-compat: the first target. Prefer target_arms()."""
    return target_arms(judge_key)[0]


def separation(recs: list[dict], judge_key: str) -> Separation:
    rows = [r for r in _seeded(recs) if r["judge"] == judge_key]
    tgts = set(target_arms(judge_key))
    tgt = ", ".join(sorted(tgts))
    on_t = [r for r in rows if r["arm"] in tgts]
    off_t = [r for r in rows if r["arm"] not in tgts]
    k1 = sum(1 for r in on_t if r["score"] == 0)
    k2 = sum(1 for r in off_t if r["score"] == 0)
    s = Separation(judge_key, tgt, k1, len(on_t), k2, len(off_t))
    s.diff, s.lo, s.hi = newcombe(k1, len(on_t), k2, len(off_t))
    return s


def wobble(recs: list[dict], judge_key: str) -> Wobble:
    """Disagreement with the judge's OWN modal verdict, per report, pooled.

    Counted against the mode rather than against the answer key on purpose: this
    number is about consistency, not correctness. A judge that is wrong the same way
    ten times out of ten has zero wobble and is still wrong, and the separation
    number is where that shows up.
    """
    w = Wobble(judge_key)
    rows = [r for r in recs if r["phase"] == "wobble" and r["judge"] == judge_key]
    for arm in sorted({r["arm"] for r in rows}):
        verdicts = [r["verdict"] for r in rows if r["arm"] == arm]
        if not verdicts:
            continue
        counts = Counter(verdicts)
        flips = len(verdicts) - counts.most_common(1)[0][1]
        w.flips += flips
        w.n += len(verdicts)
        w.per_arm[arm] = (flips, len(verdicts), counts.most_common(1)[0][0])
    return w


def verbosity(recs: list[dict]) -> dict:
    """Did any verdict move between `healthy` and `padded`?

    Same content, four times the words, nothing false added. A judge whose verdict
    changes here is responding to length. This is the bias demonstration, and it costs
    four extra calls because `padded` was already in the seeded matrix.
    """
    out = {}
    for j in judge8.JUDGE_KEYS:
        h = [r["verdict"] for r in _seeded(recs) if r["judge"] == j and r["arm"] == "healthy"]
        p = [r["verdict"] for r in _seeded(recs) if r["judge"] == j and r["arm"] == "padded"]
        hm = Counter(h).most_common(1)[0][0] if h else None
        pm = Counter(p).most_common(1)[0][0] if p else None
        chars_h = next((r["chars"] for r in _seeded(recs) if r["arm"] == "healthy"), 0)
        chars_p = next((r["chars"] for r in _seeded(recs) if r["arm"] == "padded"), 0)
        out[j] = {"healthy": hm, "padded": pm, "moved": bool(hm and pm and hm != pm),
                  "chars_healthy": chars_h, "chars_padded": chars_p}
    return out


# Phrases that mean the evidence line is arguing with the verdict above it.
# Found live: `SOUND — "...at the alarm limit..." — wait, this contradicts the
# "monitor" recommendation.` The judge reasoned correctly and then emitted the
# opposite verdict on line 1. This costs nothing to detect and it is the strongest
# argument in the session for demanding an evidence line at all.
_ARGUES = ("wait,", "however", "but this contradicts", "yet recommends",
           "contradicts the", "this is inconsistent", "actually,")


def self_contradicting(recs: list[dict]) -> list[dict]:
    """Verdicts of SOUND whose own evidence line describes a problem."""
    out = []
    for r in recs:
        if r.get("score") != 1:
            continue
        low = (r.get("comment") or "").lower()
        hit = next((p for p in _ARGUES if p in low), None)
        if hit:
            out.append({"judge": r["judge"], "arm": r["arm"], "rep": r["rep"],
                        "marker": hit, "comment": r["comment"][:220]})
    return out


def report(recs: list[dict]) -> dict:
    """Everything the deck and the notebook are allowed to quote. One computation."""
    seps = {j: separation(recs, j) for j in judge8.JUDGE_KEYS}
    wobs = {j: wobble(recs, j) for j in judge8.JUDGE_KEYS}
    usable, verdicts = {}, {}
    for j in judge8.JUDGE_KEYS:
        s, w = seps[j], wobs[j]
        ok = w.n > 0 and s.n_target > 0 and s.lo > w.upper
        usable[j] = ok
        verdicts[j] = ("USABLE" if ok else
                       "NOT MEASURABLE" if w.n == 0 or s.n_target == 0 else
                       "DECORATION — separates by less than it wobbles")
    insufficient = sum(1 for r in recs if r["score"] is None)
    return {
        "judge_version": judge8.__version__,
        "separation": {j: vars(s) for j, s in seps.items()},
        "wobble": {j: {"flips": w.flips, "n": w.n, "rate": w.rate,
                       "upper": w.upper, "per_arm": w.per_arm}
                   for j, w in wobs.items()},
        "usable": usable,
        "verdicts": verdicts,
        "verbosity": verbosity(recs),
        "insufficient_evidence": insufficient,
        "self_contradicting": self_contradicting(recs),
        "n_verdicts": len(recs),
        "all_stub": all(r.get("stub") for r in recs),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Session 8 — separation vs wobble")
    ap.add_argument("path", nargs="?", default="judge_runs8.json")
    ap.add_argument("--json", metavar="OUT", help="write the computed report")
    args = ap.parse_args()

    with open(args.path, encoding="utf-8") as fh:
        blob = json.load(fh)
    recs = blob["verdicts"]
    rep = report(recs)

    if rep["all_stub"]:
        print("!! EVERY VERDICT IN THIS FILE IS FROM THE STUB JUDGE.\n"
              "   These numbers test our plumbing. They are not findings about judges,\n"
              "   and nothing here may go on a slide.\n")

    print(f"agree8 {__version__}   {len(recs)} verdicts from {args.path}\n")
    print("SEPARATION — does it fire where it should, and stay quiet where it should?")
    for j in judge8.JUDGE_KEYS:
        print("  " + separation(recs, j).line())
    print("\nWOBBLE — does it agree with itself on an unchanged report?")
    for j in judge8.JUDGE_KEYS:
        w = wobble(recs, j)
        print("  " + (w.line() if w.n else f"{j:22s} not measured"))
    print("\nIS THE JUDGE USABLE?  (separation lower bound must clear wobble upper bound)")
    for j in judge8.JUDGE_KEYS:
        s, w = separation(recs, j), wobble(recs, j)
        print(f"  {j:22s} sep_lo {s.lo:+.0%}  vs  wobble_hi {w.upper:.0%}   "
              f"-> {rep['verdicts'][j]}")
    print("\nVERBOSITY — same content, four times the words")
    for j, v in rep["verbosity"].items():
        print(f"  {j:22s} {str(v['healthy']):22s} -> {str(v['padded']):22s} "
              f"{'MOVED' if v['moved'] else 'unchanged'}")
    print(f"\nINSUFFICIENT-EVIDENCE returned {rep['insufficient_evidence']} time(s) "
          f"of {rep['n_verdicts']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1, default=str)
        print("  wrote", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
