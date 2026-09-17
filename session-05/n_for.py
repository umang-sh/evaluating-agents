#!/usr/bin/env python3
"""
How many runs? — the Session 5 calculator.

    python n_for.py --sigma 2444 --delta 2872      # the S3 finding that held
    python n_for.py --sigma 2444 --delta 247       # the S3 claim that didn't
    python n_for.py --cv 0.4 --mean 6174 --pct 5   # "can I see a 5% difference?"
    python n_for.py --demo                         # both S3 cases, side by side

THE ONE LINE
------------
    n per arm = 2 * sigma^2 * (z_alpha + z_beta)^2 / delta^2

sigma is how much your number moves when NOTHING changes. delta is the
difference you want to be able to see. The formula says: to see a difference
half as big, you need four times the runs.

WHY THIS IS THE SESSION
-----------------------
Session 3 ran two probes twice and put two findings on a slide. One of them
reproduced on every single run. The other was a 4% gap inside a +/-40% spread,
and it was wrong. Same session, same harness, same night. The formula tells you
in advance which of those two you were entitled to claim -- and it needs no API
key, no dataset and no judge.

Session 4's notebook says `num_repetitions=1,  # Session 5 tells you what
number belongs here`. The honest answer is not a number. It is sigma and delta:
you cannot pick the repetitions until you have said how big a difference you
care about and measured how much your metric wobbles on its own.

WHAT THIS DOES NOT DO
---------------------
It assumes roughly normal, roughly independent runs and equal spread in both
arms. Agent latency is right-skewed and token counts are lumpy, so treat the
output as an ORDER OF MAGNITUDE -- "about a dozen" versus "several hundred" --
not a precise n. That distinction is the whole decision anyway.
"""

from __future__ import annotations

import argparse
import math
import sys

Z = {80: 0.841621, 90: 1.281552}          # power
ZA = {90: 1.644854, 95: 1.959964, 99: 2.575829}   # two-sided confidence


def n_per_arm(sigma: float, delta: float, conf: int = 95, power: int = 80) -> float:
    if delta <= 0:
        return math.inf
    return math.ceil(2 * sigma ** 2 * (ZA[conf] + Z[power]) ** 2 / delta ** 2)


def explain(sigma: float, delta: float, conf: int, power: int,
            label: str = "", mean: float | None = None) -> float:
    n = n_per_arm(sigma, delta, conf, power)
    head = f"  {label}" if label else "  result"
    print(f"\n{head}")
    print(f"    sigma (run-to-run spread) .... {sigma:,.0f}"
          + (f"   ({sigma / mean:.0%} of the mean)" if mean else ""))
    print(f"    delta (difference to detect) . {delta:,.0f}"
          + (f"   ({delta / mean:.0%} of the mean)" if mean else ""))
    print(f"    confidence / power ........... {conf}% / {power}%")
    print(f"    -> RUNS PER ARM .............. {n:,.0f}")
    if n <= 20:
        print("       a classroom can do this in one block.")
    elif n <= 100:
        print("       feasible overnight, not in a lecture.")
    else:
        print("       out of reach. If you claim this difference from a handful of\n"
              "       runs, you are reporting noise. Make delta bigger (compare\n"
              "       things that actually differ) or make sigma smaller.")
    return n


def demo() -> int:
    print("\n" + "=" * 74)
    print("  SESSION 3, both findings, one formula")
    print("=" * 74)
    print("\n  sigma = 2,444 billed tokens. That is Session 3's OWN measured spread:")
    print("  ReAct on the hard probe ranged 4,009 to 8,503 over four runs, on a")
    print("  mean of 6,174. Nothing changed between those runs. 40% wobble.")

    a = explain(2444, 5806 - 2934, 95, 80,
                "FINDING THAT HELD: workflow costs 2x on easy probes", 6174)
    b = explain(2444, 6174 - 5927, 95, 80,
                "CLAIM THAT DIDN'T: the 4% hard-probe 'flip'", 6174)

    print("\n" + "-" * 74)
    print(f"  Session 3 ran TWO. It needed {a:,.0f} for one claim and {b:,.0f} for the other.")
    print(f"  {b / a:,.0f}x apart, and nobody could tell from looking at the table.")
    print("-" * 74)
    print("\n  The deck asserted both. One was a result. One was noise wearing a\n"
          "  result's clothes. The difference is arithmetic you can do before you\n"
          "  spend a single API call.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--sigma", type=float)
    ap.add_argument("--delta", type=float)
    ap.add_argument("--cv", type=float, help="spread as a fraction of the mean, e.g. 0.4")
    ap.add_argument("--mean", type=float)
    ap.add_argument("--pct", type=float, help="difference to detect, as %% of the mean")
    ap.add_argument("--conf", type=int, default=95, choices=sorted(ZA))
    ap.add_argument("--power", type=int, default=80, choices=sorted(Z))
    args = ap.parse_args()

    if args.demo or not (args.sigma or args.cv):
        return demo()

    mean = args.mean
    sigma = args.sigma if args.sigma is not None else args.cv * (mean or 0)
    delta = args.delta if args.delta is not None else (args.pct / 100.0) * (mean or 0)
    if not sigma or not delta:
        print("Need sigma and delta. Either --sigma/--delta, or --cv/--pct with --mean.")
        return 1
    explain(sigma, delta, args.conf, args.power, mean=mean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
