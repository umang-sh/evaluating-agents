"""
Session 8 — the human column. One rater, and the deck says so.

    python human_labels8.py            # print the cases, and what is still unlabelled
    python human_labels8.py --blind    # the same cases with MY labels hidden -- for the
                                       # homework, where the class is the second rater

WHAT THIS IS
------------
The syllabus asks for judge vs rule-based vs HUMAN EXPERT. We have no maintenance
engineers, so there are two honest options and one dishonest one.

    honest    the instructor labels a handful of real cases, and the deck states
              plainly what that is: one rater, not an expert, no second opinion,
              no inter-rater agreement measured.
    honest    no human column at all, and say why.
    DISHONEST a "simulated engineer review" produced by a language model.

The third is an LLM in a costume. It turns judge-vs-human into judge-vs-judge and
teaches students to accept invented ground truth from a system that sounds confident
-- which is the exact failure mode this course spends twelve weeks on.

So: instructor labels, on real disagreements, with the limitation on the slide.

WHERE THE CASES COME FROM -- NOT INVENTED
------------------------------------------
Session 7's live comparison ran 12 rows x 3 reps x 2 arms = 72 runs. In 27 of them
`outcome_match` scored 0. Ten of those disagreements are about the ACTION field --
what the agent told the engineer to do. Five of the ten are an EMPTY action (the
maintenance agent never produced a tail), which is a missing answer, not a judgement
call, and those are excluded here.

That leaves FIVE run-instances across THREE distinct rows where the agent recommended
something real and the benchmark wanted something else. They are the only cases in
this course where a human opinion is actually needed, and they were measured, not
constructed.

    over-recommending   the agent orders work on a machine the benchmark says to
                        leave alone
    under-recommending  the agent monitors a machine the benchmark says to fix

Nothing in Session 7 can adjudicate these. That is why Session 8 exists.

HOW TO LABEL
------------
Fill in LABELS below. Three verdicts:

    "agent"      the agent was right and the benchmark row is wrong
    "benchmark"  the benchmark was right and the agent was wrong
    "neither"    the request is ambiguous; both answers are defensible

Add one sentence of reasoning for each. The sentence is what goes on the slide next to
the judge's verdict, and it is the only thing that makes the comparison legible.
"""

from __future__ import annotations

import json

import _path  # noqa: F401

__version__ = "s8-2026-09-15a"

EMPTY = ("", None)


def cases(path: str | None = None) -> list[dict]:
    """Every live ACTION-level disagreement with a real recommendation in it.

    Computed, never typed. A hand-copied list is how a count drifts: the Session 8
    kickoff carried '15 disagreements, eight in two shapes', which does not reproduce
    from this file under any grouping I could find.
    """
    path = path or str(_path.session(7) / "runs7.json")
    with open(path, encoding="utf-8") as fh:
        recs = json.load(fh)["runs"]
    out = []
    for r in recs:
        if r.get("phase") != "comparison":
            continue
        note = (r.get("comments") or {}).get("outcome_match") or ""
        seg = [s for s in note.split("; ") if s.startswith("action")]
        if not seg:
            continue
        got = (r["outputs"].get("tail") or {}).get("ACTION") or ""
        if got.strip() in EMPTY:
            continue                 # a missing tail is a missing answer, not a call
        shape = ("over-recommending" if "expected no action" in seg[0]
                 else "under-recommending")
        out.append({
            "case_id": f"{r['row_id']}/{r['version']}/rep{r['rep']}",
            "row_id": r["row_id"],
            "arm": r["version"],
            "rep": r["rep"],
            "shape": shape,
            "agent_said": got,
            "benchmark_wanted": seg[0],
            "question": r["question"],
        })
    return out


def distinct_rows(cs: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for c in cs:
        by.setdefault(c["row_id"], []).append(c)
    return by


# ---------------------------------------------------------------------------
# THE LABELS. Keyed by row_id, because the repeats of one row are one judgement.
# Fill these in. Leave a row out and the report says UNLABELLED rather than
# guessing, and the slide says so too.
# ---------------------------------------------------------------------------
LABELS: dict[str, dict] = {
    "HW-006": {
        "verdict": "benchmark",
        "why": "The gearbox is AT its 72 C alarm limit and trending, on a bearing "
               "replaced five months ago. 'Monitor' is under-recommending on a "
               "high-criticality machine that starves the filler when it stops.",
    },
    "HW-010": {
        "verdict": "benchmark",
        "why": "A stock-and-price question. Producing a work order for a machine "
               "nobody asked to diagnose is over-reach, whatever the lead time.",
    },
    "HW-011": {
        "verdict": "neither",
        "why": "It genuinely IS a repeat bearing failure inside twelve months on a "
               "machine at its alarm limit. Recommending replacement is right "
               "engineering and wrong scope: the question asked was yes or no.",
    },
}

RATER = "instructor"
RATER_CAVEAT = ("One rater, who is not a maintenance engineer. No second opinion and "
                "no inter-rater agreement. This is a measurement with a spread we did "
                "not take — treat it as one person's reading, not as ground truth.")


def report(path: str | None = None) -> dict:
    cs = cases(path)
    by = distinct_rows(cs)
    labelled = {k: v for k, v in LABELS.items() if k in by}
    return {
        "n_instances": len(cs),
        "n_rows": len(by),
        "rows": {k: {"shape": v[0]["shape"], "instances": len(v),
                     "agent_said": sorted({c["agent_said"] for c in v}),
                     "benchmark_wanted": v[0]["benchmark_wanted"],
                     "question": v[0]["question"],
                     "label": LABELS.get(k, {}).get("verdict"),
                     "why": LABELS.get(k, {}).get("why")}
                 for k, v in by.items()},
        "labelled_rows": len(labelled),
        "unlabelled_rows": sorted(set(by) - set(labelled)),
        "rater": RATER,
        "caveat": RATER_CAVEAT,
    }


if __name__ == "__main__":
    import sys

    blind = "--blind" in sys.argv
    rep = report()
    print(f"human_labels8 {__version__}"
          f"{'  — BLIND: my labels are hidden' if blind else ''}\n")
    print(f"{rep['n_instances']} run-instances across {rep['n_rows']} distinct rows\n")
    if blind:
        print("  Write your own verdict for each row -- agent / benchmark / neither --")
        print("  and one sentence of reasoning, BEFORE you run this again without --blind.")
        print("  A verdict you formed after reading mine measures nothing.\n")
    for row, d in rep["rows"].items():
        print(f"  {row}  {d['shape']:19s} x{d['instances']}")
        print(f"        the request     : {d['question']}")
        print(f"        agent said      : {', '.join(d['agent_said'])}")
        print(f"        benchmark wanted: {d['benchmark_wanted']}")
        if blind:
            print("        label           : (hidden -- run without --blind)")
        else:
            print(f"        label           : {d['label'] or 'UNLABELLED'}")
            if d["why"]:
                print(f"        why             : {d['why']}")
        print()
    if rep["unlabelled_rows"] and not blind:
        print("  STILL UNLABELLED:", ", ".join(rep["unlabelled_rows"]))
        print("  The slide will say UNLABELLED rather than guess.")
    print("\n  caveat on the slide:", rep["caveat"])
