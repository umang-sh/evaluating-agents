"""
Interval arithmetic for proportions. Shared, because more than one session needs it.

MOVED HERE 20 Sep 2026, FROM session-08/agree8.py, VERBATIM.
No formula, constant or docstring was changed. `agree8.py` imports these names back
out of this module and re-exports them, so every Session 8 caller -- `preflight8.py`,
`sweep8.py`, `doctor8.py`, the notebook -- behaves exactly as it did before the move.
The move happened because Session 9 needs the same three functions and
`session-09/` cannot import from `session-08/`; `_path.py` says what to do about
that in as many words: a module two sessions use belongs in `shared/`.

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

import math

__version__ = "s9-2026-09-20a"

Z = 1.96


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    """95% Wilson score interval for k successes in n trials. Never zero-width."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


def rule_of_three(n: int) -> float:
    """95% upper bound on a rate after n trials with ZERO events. Session 5's number."""
    return 3.0 / n if n else 1.0


def newcombe(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """(difference, lo, hi) for p1 - p2, two independent proportions.

    Newcombe's hybrid-score method: build each Wilson interval, then combine. Closed
    form, small-sample honest, and it does not collapse at 0 or 1.
    """
    p1 = k1 / n1 if n1 else 0.0
    p2 = k2 / n2 if n2 else 0.0
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, max(-1.0, lo), min(1.0, hi)
