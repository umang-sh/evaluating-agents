"""
Session 9 — does the trajectory judge separate paths by more than it wobbles?

    python agree9.py traj_runs9.json

THE SPINE, AS CODE:
    Code can tell you the path was wrong -- but only if someone already wrote down
    what right was.

So this file asks, of each reference-free judge, the same two questions Session 8 asked
of its report judges, because the bar does not get lower just because the subject
changed:

    SEPARATION   how much more often the judge fires on the trajectory it should stop
                 than on the trajectories it should wave through.

                     separation = P(UNSOUND | its own broken arm)
                                - P(UNSOUND | the arms it should pass)

    WOBBLE       how often the same judge, on the same unchanged trajectory, disagrees
                 with its own most common answer.

If the lower bound of SEPARATION does not clear the upper bound of WOBBLE, the judge is
decoration. It may still be right. We cannot show it.

WHAT IS SHARED WITH SESSION 8 AND WHAT IS NOT, AND WHY
-------------------------------------------------------
SHARED, imported, never copied: `wilson`, `rule_of_three` and `newcombe`, which live in
`shared/intervals.py`. That is the arithmetic, it is the part that is easy to get
subtly wrong, and there is exactly one copy of it in this repo.

NOT shared: the counting. `agree8.separation()` reads `judge_seeds8.EXPECT` and
`judge8.JUDGE_KEYS` -- Session 8's arms and Session 8's judges. Session 9 has different
arms and different judges, so the loops here iterate `judge9.TARGETS` instead. The
formulas are identical and the printed shape is deliberately identical, so a student
who read Session 8's output can read this one.

WHAT REPLACES THE VERBOSITY COLUMN
-----------------------------------
Session 8's bias demo was length: same report, four times the words, and one judge's
verdict moved. The trajectory analogue is PATH LENGTH. `healthy` runs 3 agents;
`delegation_loop` runs 8. `path_length_bias()` asks whether a judge fires more on long
paths it is supposed to PASS -- which would mean it is detecting size, not waste. It
costs nothing: `n_calls` is already on every record.
"""

from __future__ import annotations

import _path  # noqa: F401  -- shared/ and plant/ on sys.path; must be first

import argparse
import json
import statistics
import textwrap
from collections import Counter
from dataclasses import dataclass, field

import judge9
import traj9
from intervals import newcombe, rule_of_three, wilson   # shared/, one copy of the maths

__version__ = "s9-2026-09-20a"

# Same markers as agree8._ARGUES. A judge that says SOUND and then argues with itself is
# the strongest evidence in the course for demanding an evidence line at all.
_ARGUES = ("wait,", "however", "but this contradicts", "yet recommends",
           "contradicts the", "this is inconsistent", "actually,")


@dataclass
class Separation:
    judge: str
    target_arms: tuple
    fired_on_target: int
    n_target: int
    fired_on_controls: int
    n_controls: int
    diff: float = 0.0
    lo: float = 0.0
    hi: float = 0.0

    def line(self) -> str:
        return (f"{self.judge:20s} fires {self.fired_on_target}/{self.n_target} on "
                f"{'+'.join(self.target_arms):30s} {self.fired_on_controls}/"
                f"{self.n_controls} elsewhere   sep {self.diff:+.0%} "
                f"[{self.lo:+.0%}, {self.hi:+.0%}]")


@dataclass
class Wobble:
    judge: str
    flips: int = 0
    n: int = 0
    per_trajectory: dict = field(default_factory=dict)

    @property
    def rate(self) -> float:
        return self.flips / self.n if self.n else 0.0

    @property
    def upper(self) -> float:
        """Upper 95% bound on this judge's self-disagreement rate.

        Zero flips does NOT mean zero wobble. It means the rule of three, and with
        n=10 that is still 30%.
        """
        if self.n == 0:
            return 1.0
        if self.flips == 0:
            return rule_of_three(self.n)
        return wilson(self.flips, self.n)[1]

    def line(self) -> str:
        shape = "unanimous" if self.flips == 0 else f"{self.flips} flip(s)"
        return (f"{self.judge:20s} {shape:14s} over {self.n:3d} repeats   "
                f"disagreement <= {self.upper:.0%}")


def _gate(recs: list[dict]) -> list[dict]:
    """Gate verdicts, with the excluded exhibits removed in BOTH directions.

    See `traj9.EXCLUDED_FROM_GATE`. A trajectory whose answer key we no longer trust
    cannot be a control (it would count a correct catch as a false alarm) and cannot be
    a target (that would be circular). It is removed and shown separately.
    """
    return [r for r in recs if r["phase"] == "gate"
            and not traj9.is_excluded(r["row_id"], r["arm"])]


def excluded(recs: list[dict]) -> list[dict]:
    """The verdicts on the excluded exhibits -- reported, never scored."""
    return [r for r in recs if r["phase"] == "gate"
            and traj9.is_excluded(r["row_id"], r["arm"])]


def separation(recs: list[dict], judge_key: str, arm: str | None = None) -> Separation:
    """Fires on ONE target arm vs everywhere it should stay quiet.

    PER ARM, and this changed after the live run of 20 Sep. The original statistic
    pooled every arm a judge targets. `path_efficiency` targets two, caught
    `delegation_loop` 4/4 and missed `redundant_call` 0/4, and the pooled number was
    50% -- which answers neither question. Session 7 had already ruled on this shape
    when it refused to quote 5/12 for an evaluator that only applied to 7 of the rows.

    The change was made AFTER seeing the result, which is the dangerous direction, so
    the deck says so and `report()` keeps the pooled figure under `pooled` so the
    pre-specified number is still on the record.

    `arm=None` reproduces the old pooled behaviour.
    """
    targets = tuple(judge9.TARGETS[judge_key])
    rows = [r for r in _gate(recs) if r["judge"] == judge_key]
    want = (arm,) if arm else targets
    tgt = [r for r in rows if r["arm"] in want]
    ctl = [r for r in rows if r["arm"] not in targets]
    k1 = sum(1 for r in tgt if r["score"] == 0)
    k2 = sum(1 for r in ctl if r["score"] == 0)
    d, lo, hi = newcombe(k1, len(tgt), k2, len(ctl))
    return Separation(judge_key, want, k1, len(tgt), k2, len(ctl), d, lo, hi)


def judge_arm_pairs() -> list[tuple[str, str]]:
    """Every (judge, arm) the gate reports on, in slide order."""
    return [(j, a) for j in judge9.JUDGE_KEYS for a in judge9.TARGETS[j]]


def wobble(recs: list[dict], judge_key: str) -> Wobble:
    """Disagreement with the judge's OWN modal verdict, per trajectory, pooled.

    Against the mode rather than the answer key on purpose: this number is about
    consistency, not correctness. A judge that is wrong the same way ten times out of
    ten has zero wobble and is still wrong -- and separation is where that shows up.

    The wobble phase is NOT filtered by EXCLUDED_FROM_GATE: self-agreement on a
    trajectory is a fact about the judge regardless of whether we trust that
    trajectory's answer key.
    """
    w = Wobble(judge_key)
    rows = [r for r in recs if r["phase"] == "wobble" and r["judge"] == judge_key]
    for key in sorted({(r["row_id"], r["arm"]) for r in rows}):
        verdicts = [r["verdict"] for r in rows if (r["row_id"], r["arm"]) == key]
        if not verdicts:
            continue
        counts = Counter(verdicts)
        flips = len(verdicts) - counts.most_common(1)[0][1]
        w.flips += flips
        w.n += len(verdicts)
        w.per_trajectory["/".join(key)] = (flips, len(verdicts),
                                           counts.most_common(1)[0][0])
    return w


def path_length_bias(recs: list[dict]) -> dict:
    """Does the judge fire more on longer paths it is supposed to PASS?

    Controls only -- arms this judge is not aimed at. If a judge's false-alarm rate
    climbs with `n_calls` across trajectories it should all be waving through, it is
    responding to the SIZE of the path rather than to anything wrong with it. That is
    Session 8's verbosity finding in trajectory clothing, and it costs no extra calls.
    """
    out = {}
    for j in judge9.JUDGE_KEYS:
        targets = judge9.TARGETS[j]
        ctl = [r for r in _gate(recs) if r["judge"] == j and r["arm"] not in targets]
        short = [r for r in ctl if r["n_calls"] <= 3]
        long_ = [r for r in ctl if r["n_calls"] >= 5]
        ks, kl = sum(1 for r in short if r["score"] == 0), sum(1 for r in long_ if r["score"] == 0)
        d, lo, hi = newcombe(kl, len(long_), ks, len(short))
        # NOT MEASURABLE is a real answer and must not be dressed up as an interval.
        # `path_efficiency` has no long CONTROL path at all: every trajectory in this set
        # with five or more invocations is one it is supposed to fire on. Newcombe will
        # happily return [-30%, +100%] from 0/0 and that number means nothing. Session 8
        # shipped two DECORATION judges by saying so out loud; the same applies here.
        measurable = bool(short) and bool(long_)
        out[j] = {
            "short_fires": ks, "n_short": len(short),
            "long_fires": kl, "n_long": len(long_),
            "measurable": measurable,
            "diff": d if measurable else None,
            "lo": lo if measurable else None,
            "hi": hi if measurable else None,
            "separated": bool(measurable and lo > 0),
            "mean_calls_short": round(statistics.mean([r["n_calls"] for r in short]), 2) if short else None,
            "mean_calls_long": round(statistics.mean([r["n_calls"] for r in long_]), 2) if long_ else None,
        }
    return out


def self_contradicting(recs: list[dict]) -> list[dict]:
    """Verdicts of SOUND whose own evidence line describes a problem."""
    out = []
    for r in recs:
        if r.get("score") != 1:
            continue
        low = (r.get("comment") or "").lower()
        hit = next((p for p in _ARGUES if p in low), None)
        if hit:
            out.append({"judge": r["judge"], "row_id": r["row_id"], "arm": r["arm"],
                        "rep": r["rep"], "marker": hit, "comment": r["comment"][:220]})
    return out


def report(recs: list[dict]) -> dict:
    """Everything the deck and the notebook are allowed to quote. One computation.

    Session 8's rule 1: counts are RECOMPUTED here, never read from a comment.
    """
    wobs = {j: wobble(recs, j) for j in judge9.JUDGE_KEYS}
    per_arm, usable, verdicts = {}, {}, {}
    for j, a in judge_arm_pairs():
        s_ = separation(recs, j, a)
        w = wobs[j]
        ok = w.n > 0 and s_.n_target > 0 and s_.lo > w.upper
        key = f"{j}::{a}"
        per_arm[key] = vars(s_)
        usable[key] = ok
        verdicts[key] = ("USABLE" if ok else
                         "NOT MEASURABLE" if w.n == 0 or s_.n_target == 0 else
                         "DECORATION — separates by less than it wobbles")
    pooled = {j: vars(separation(recs, j)) for j in judge9.JUDGE_KEYS}
    ex = excluded(recs)
    return {
        "judge_version": judge9.__version__,
        "traj_version": traj9.__version__,
        "gate_rows": list(traj9.GATE_ROWS),
        "arms": list(traj9.ARMS),
        "unit": "per (judge, arm) — changed from pooled after the 20 Sep run; see separation()",
        "separation": per_arm,
        "pooled_as_prespecified": pooled,
        "wobble": {j: {"flips": w.flips, "n": w.n, "rate": w.rate, "upper": w.upper,
                       "per_trajectory": w.per_trajectory} for j, w in wobs.items()},
        "usable": usable,
        "verdicts": verdicts,
        "any_usable": any(usable.values()),
        "excluded": {f"{r['row_id']}/{r['arm']}": traj9.EXCLUDED_FROM_GATE[
                        (r['row_id'], r['arm'])] for r in ex},
        "excluded_verdicts": [{"judge": r["judge"], "row_id": r["row_id"],
                               "arm": r["arm"], "verdict": r["verdict"],
                               "comment": r["comment"]} for r in ex],
        "path_length_bias": path_length_bias(recs),
        "insufficient_evidence": sum(1 for r in recs if r["score"] is None),
        "self_contradicting": self_contradicting(recs),
        "n_verdicts": len(recs),
        "all_stub": all(r.get("stub") for r in recs),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Session 9 — separation vs wobble")
    ap.add_argument("path", nargs="?", default="traj_runs9.json")
    ap.add_argument("--json", metavar="OUT", help="write the computed report")
    args = ap.parse_args()

    try:
        with open(args.path, encoding="utf-8") as fh:
            recs = json.load(fh)["verdicts"]
    except FileNotFoundError:
        # Self-test on free stub verdicts rather than dying. `sweep9.py` check [1] runs
        # every module as a script, and a module that cannot run before the live
        # measurement exists is a module that cannot be checked until the night before.
        print(f"  {args.path} not found — self-testing on stub verdicts instead\n")
        import traj_bench9
        recs = traj_bench9.gate(stub=True, verbose=False)
        recs += traj_bench9.wobble(stub=True, n=3, verbose=False)
    rep = report(recs)

    if rep["all_stub"]:
        print("!! EVERY VERDICT IN THIS FILE IS FROM THE STUB JUDGE.\n"
              "   The stub was written to match the answer key, so 100% agreement here\n"
              "   is arithmetic, not a finding. These numbers test our plumbing. Nothing\n"
              "   here may go on a slide.\n")

    print(f"agree9 {__version__}   {len(recs)} verdicts from {args.path}\n")
    print("SEPARATION, PER ARM — does it fire where it should, and stay quiet elsewhere?")
    for j, a in judge_arm_pairs():
        print("  " + separation(recs, j, a).line())
    print("\n  (pooled, as originally specified — kept on the record:)")
    for j in judge9.JUDGE_KEYS:
        print("    " + separation(recs, j).line())
    print("\nWOBBLE — does it agree with itself on an unchanged trajectory?")
    for j in judge9.JUDGE_KEYS:
        w = wobble(recs, j)
        print("  " + (w.line() if w.n else f"{j:20s} not measured"))
    print("\nIS THE JUDGE USABLE?  (separation lower bound must clear wobble upper bound)")
    for j, a in judge_arm_pairs():
        s_, w = separation(recs, j, a), wobble(recs, j)
        print(f"  {j+' vs '+a:40s} sep_lo {s_.lo:+.0%}  vs  wobble_hi {w.upper:.0%}   "
              f"-> {rep['verdicts'][f'{j}::{a}'].split(' —')[0]}")
    if rep["excluded"]:
        print("\nEXCLUDED FROM THE GATE — reported, never scored")
        for k, why in rep["excluded"].items():
            print(f"  {k}: {why}")
        for v in rep["excluded_verdicts"]:
            if v["verdict"] == "UNSOUND":
                print(f"    {v['judge']}: {v['comment'][:140]}")
    print("\nPATH-LENGTH BIAS — on arms it should PASS, does it fire more when the path is long?")
    for j, v in rep["path_length_bias"].items():
        head = (f"  {j:20s} short {v['short_fires']}/{v['n_short']}  "
                f"long {v['long_fires']}/{v['n_long']}   ")
        if not v["measurable"]:
            print(head + "NOT MEASURABLE — no control path of that length exists")
        else:
            print(head + f"{v['diff']:+.0%} [{v['lo']:+.0%}, {v['hi']:+.0%}]  "
                  f"{'LENGTH BIAS' if v['separated'] else 'no detectable bias'}")
    print(f"\nINSUFFICIENT-EVIDENCE returned {rep['insufficient_evidence']} time(s) "
          f"of {rep['n_verdicts']}")
    sc = rep["self_contradicting"]
    print(f"SELF-CONTRADICTING verdicts (SOUND, evidence says otherwise): {len(sc)}")
    for r in sc[:5]:
        # WRAPPED, never truncated. The evidence line is the only part of a verdict you
        # can argue with, and Session 8 lost two findings to comment[:74].
        body = textwrap.fill(r["comment"], width=86,
                             initial_indent="      ", subsequent_indent="      ")
        print(f"    {r['judge']} {r['row_id']}/{r['arm']}:\n{body}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1, default=str)
        print("  wrote", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
