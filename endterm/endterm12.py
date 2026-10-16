"""
End-term assessment -- where your case's runs come from. Read it; you do not edit it.

    endterm/case-<N>/runs_a.json   version A: 24 REAL runs, the version in production
    endterm/case-<N>/runs.json     your candidate: 24 runs, SEEDED

Both files hold the same 12 maintenance requests, run twice each. Nothing here calls a
model, so every laptop gets the same numbers, for free, with no API key.

WHAT "SEEDED" MEANS, AND WHY IT MATTERS TO YOUR ANSWER
------------------------------------------------------
Your candidate was built from version A's saved runs by code. One thing about it was
changed on purpose. The later agents were NOT re-run, so where a step survived, its
report is A's report. A real re-run could come out better or worse than what you see.

That is a limit on what you can conclude, and saying so is worth marks. It is not an
excuse for having no number.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first

import json
import sys

sys.path.insert(0, str(_path.session(12)))

from delegation_rows7 import BY_ID

__version__ = "endterm-2026-10-16a"

HERE = _path.ROOT / "endterm"
CASES = (1, 2, 3, 4, 5)


def _load(path):
    d = json.loads(path.read_text())
    # `row` -- the question's answer key -- is not stored in the file. It is the same for
    # everyone and lives in one place: session-07/delegation_rows7.py.
    return [{**r, "row": BY_ID[r["row_id"]]} for r in d["runs"]], d


def load(case_id: int, which: str = "candidate") -> list[dict]:
    """Every run of one version of one case, in the shape pipeline12 expects.

    which = "candidate"  your proposed replacement  (runs.json,   SEEDED)
    which = "A"          the version in production  (runs_a.json, REAL)
    """
    case_id = int(case_id)
    if case_id not in CASES:
        raise KeyError(f"case {case_id}: cases are {CASES}")
    name = "runs_a.json" if which.upper() == "A" else "runs.json"
    runs, _ = _load(HERE / f"case-{case_id}" / name)
    return runs


def provenance(case_id: int, which: str = "candidate") -> str:
    """The one line you should put on a slide before you quote any number off these runs."""
    name = "runs_a.json" if which.upper() == "A" else "runs.json"
    _, d = _load(HERE / f"case-{int(case_id)}" / name)
    stamp = "SEEDED" if d.get("seeded") else "REAL"
    return f"{d['version']}: {d['n_runs']} runs, {stamp}, from endterm/case-{case_id}/{name}"
