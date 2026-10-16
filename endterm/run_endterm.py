"""
THE ONE COMMAND. Produces your scorecard, the comparison and your decision.

    python endterm/run_endterm.py <case-id> <your file> > scorecard.txt

e.g.    python endterm/run_endterm.py 3 endterm/my_release_G7.py > scorecard.txt

It imports YOUR four functions, runs the whole pipeline over the saved runs, and prints
everything. Nothing calls a model. No API key. It costs nothing and it is the same output
every time.

Submit the file you redirected it into. Do not retype numbers off the screen -- every
number on your slides has to exist in that file, and retyping is how the two stop
matching.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(_path.session(12)))

import endterm12
import pipeline12 as pl

REQUIRED = ("resolved", "must_hold", "decide")
OPTIONAL = ("alert",)


def load_student(path: Path):
    spec = importlib.util.spec_from_file_location("student_release", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    missing = [f for f in REQUIRED if not callable(getattr(mod, f, None))]
    if missing:
        sys.exit(f"ERROR  {path.name} has no working {', '.join(missing)}. "
                 f"Every one of {', '.join(REQUIRED)} must be a function.")
    return mod


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    case_id, path = argv[1], Path(argv[2])
    if not path.exists():
        sys.exit(f"ERROR  no such file: {path}")
    me = load_student(path)

    print("=" * 78)
    print(f"END-TERM  case {case_id}   file {path.name}")
    print(f"  baseline   {endterm12.provenance(case_id, 'A')}")
    print(f"  candidate  {endterm12.provenance(case_id, 'candidate')}")
    print("=" * 78)

    try:
        base = pl.evaluate_all(endterm12.load(case_id, "A"))
        cand = pl.evaluate_all(endterm12.load(case_id, "candidate"))
    except NotImplementedError as e:
        sys.exit(f"\nERROR  {path.name}: {e}\n"
                 f"       One of the three marked functions is still the stub. Write it, "
                 f"then run this again.")

    try:
        print()
        print(pl.show_scorecard(pl.scorecard(base, me.resolved), "version A (in production)"))
        print()
        print(pl.show_scorecard(pl.scorecard(cand, me.resolved),
                                f"case {case_id} candidate  [SEEDED]"))
        print()
        print("-" * 78)
        cmp = pl.compare(base, cand, me.must_hold)
        print(pl.show_compare(cmp))
        print()
        print("-" * 78)
        verdict, why = me.decide(cmp)
    except NotImplementedError as e:
        sys.exit(f"\nERROR  {path.name}: {e}\n"
                 f"       One of the three marked functions is still the stub. Write it, "
                 f"then run this again.")
    print(f"YOUR DECISION:  {verdict}")
    print(f"BECAUSE:        {why}")
    print("-" * 78)
    print("\nper-agent cost, candidate:")
    print(pl.cost_by_agent(cand))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
