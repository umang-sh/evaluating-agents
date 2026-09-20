"""
Session 9 — the trajectory, and what you are allowed to see of it.

WHAT A TRAJECTORY IS, IN THIS COURSE
------------------------------------
Not the answer. The answer is Session 8's subject and it has been judged already. A
trajectory is everything the system DID on the way to the answer:

    question        what the engineer asked
    plan            the planner's decomposition: which agent gets which subtask
    agent_calls     which agents actually ran, in order, including repeats
    handoffs        what each agent was handed by the one before it

`traj9.render()` builds exactly that, and nothing else, as text. It never includes the
final report. That restriction is the session: a "trajectory judge" that is shown the
finished answer is Session 8's judge wearing a new label, and it will score well for
reasons that have nothing to do with the path.

THE RESTRICTION THAT MATTERS MORE: NO DELEGATION ROW
-----------------------------------------------------
Session 7's five code evaluators all take `reference_outputs` -- the delegation row,
which states `expected_agents`, `expected_calls` and `handoff_facts`. Given that row,
catching a wrong delegation is a set difference. It is not intelligence, and it is not
supposed to be.

`render()` does not include the row, and `judge9`'s judges never receive one. The judge
is given the question, the roster of who does what, and the path -- the same things a
reviewing engineer would have with no test plan in front of them. Whether it can recover
the row's verdict from that is the measurement.

    code   trajectory + the row   ->  verdict      (Session 7)
    judge  trajectory             ->  verdict      (Session 9)

SPINE: code can tell you the path was wrong -- but only if someone already wrote down
what right was.

WHY THE STUB `matrix` PHASE AND NOT THE LIVE RUNS
--------------------------------------------------
The live `comparison` phase has 12 trajectories and exactly two delegation failures
(HW-006, truncated; HW-012, skips diagnostics). Two positives cannot establish
separation; Session 8 needed 3/3 on its own arm and that was already thin.

The stub `matrix` phase has five arms x 12 rows, with a known code verdict on every one.
The cost of using it is stated on the slide and must not be softened: **those
trajectories are stub prose, written by the instructor, not produced by a model.** A
judge reading them is reading our writing. It is a fair test of reference-free
reasoning and a poor sample of real agent output, and both halves of that go in the deck.

The stub phase also has **no `tokens_billed` and no `cost_usd` at all** -- the metrics
dict carries four keys, not eight. Nothing in this session may compute money from the
matrix arms. Money comes from `cost9.py`, which uses the live `comparison` phase only.
`assert_no_cost()` below enforces that at import of any caller that cares.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

import json
from functools import lru_cache

__version__ = "s9-2026-09-20a"

RUNS7 = _path.session(7) / "runs7.json"

# The five seeded arms, in the order they go on the slide. `healthy` first because
# every separation number is measured against it.
ARMS = ("healthy", "wrong_delegation", "lost_handoff",
        "redundant_call", "delegation_loop")

# ---------------------------------------------------------------------------
# The gate rows.
#
# Chosen by measurement, not by taste. A row is usable only if ALL FOUR broken seeds
# actually change something in it -- plan, agent_calls or handoffs. Seven of the twelve
# qualify: HW-001 002 003 005 006 007 012. The other five are unbreakable by at least
# one seed and would be counted as judge misses when they are nothing of the kind.
# (Session 7 hit this exact trap: `lost_handoff` breaks only the
# diagnostics -> documentation edge, and five rows assert nothing on that edge.)
#
# Four are used, and the fourth is the important one:
#
#   HW-001  the flagship conveyor bearing case. Full four-agent path.
#   HW-005  the blower whose correct outcome is "monitor" -- a case where doing
#           nothing is right, so a judge biased toward "more work = more thorough"
#           has somewhere to trip.
#   HW-006  covers TWO machines, so its healthy path calls diagnostics TWICE and
#           `expected_calls` says diagnostics: 2. A `path_efficiency` judge that
#           calls this redundant is firing on a healthy run -- the classic evaluator
#           bug from Session 2, and the reason this row is in the gate at all.
#   HW-007  the rinse-water pump. A second full path, different machine and fault.
# ---------------------------------------------------------------------------
GATE_ROWS = ("HW-001", "HW-005", "HW-006", "HW-007")

# Rows where every seed bites. Recomputed by preflight9 check [2]; never trusted as typed.
BREAKABLE_ROWS = ("HW-001", "HW-002", "HW-003", "HW-005", "HW-006", "HW-007", "HW-012")

# ---------------------------------------------------------------------------
# Trajectories that are in the gate's grid but are scored in NEITHER direction.
#
# HW-006 / healthy is not healthy, and this was found on 20 Sep by the live judges
# rather than by us. The request asks which of TWO machines needs attention first.
# The plan says `diagnose CONVEYOR` then `diagnose BLOWER`. The run produces two
# BYTE-IDENTICAL diagnostics sections, both about CONVEYOR, and the word BLOWER
# appears nowhere in the answer or in any handoff after the first. All five of
# Session 7's code evaluators pass it 5 of 5 -- `agent_no_redundancy` because
# `expected_calls` says diagnostics: 2 and it ran twice, and it never asks what
# each call was FOR.
#
# Both "false alarms" on the healthy arm were this, caught unprompted:
#   path_efficiency — "BLOWER was passed to diagnostics in step 1 but never
#                      diagnosed; only CONVEYOR was addressed by subsequent steps."
#
# It is excluded from the gate in BOTH directions -- not a control, not a target --
# so it can neither penalise a judge as a false alarm nor flatter one as a catch.
# Counting it as a target would be circular: the arm would be defined by what the
# judges found and then used to score them. It gets its own slide instead.
#
# The clean fix is to make the row assert BLOWER, which would let code catch it too.
# NOT DONE, deliberately: `delegation_rows7.py` is Session 7's, and asserting BLOWER
# changes `handoff_integrity` on 12 matrix records and moves Session 7's slide 15
# from 36/36 to 33/36 on the healthy arm -- a deck that has already been taught.
# Measured 20 Sep. Logged for Session 10.
# ---------------------------------------------------------------------------
EXCLUDED_FROM_GATE: dict[tuple[str, str], str] = {
    ("HW-006", "healthy"): (
        "not healthy: diagnoses CONVEYOR twice, byte-identically, and never "
        "diagnoses BLOWER, which the request explicitly asks about. Code passes "
        "it 5/5. Found by the judges, 20 Sep."),
}


def is_excluded(row_id: str, arm: str) -> bool:
    return (row_id, arm) in EXCLUDED_FROM_GATE


# ---------------------------------------------------------------------------
# Human labels for the twelve requests.
#
# The ids are `delegation_rows7.py`'s and they stay the keys -- every file in the
# course joins on them. But **nothing anywhere in this repo says what "HW" stands
# for**, and the ids start appearing on slide 5 with no introduction. On a projector
# "HW-006" is a serial number; "morning walkdown" is a thing an engineer said.
#
# Four words maximum, taken from the request itself, so a slide can show the label and
# the run sheet can still quote the id.
# ---------------------------------------------------------------------------
ROW_LABEL: dict[str, str] = {
    "HW-001": "conveyor running hot",
    "HW-002": "rinse pump, gravelly",
    "HW-003": "filler drive tripping",
    "HW-004": "compressor walkdown",
    "HW-005": "blower still vibrating",
    "HW-006": "morning walkdown, two machines",
    "HW-007": "something on Line 3",
    "HW-008": "Line 4 gearbox overcurrent",
    "HW-009": "balance spec, no diagnosis",
    "HW-010": "capacitor kit in stock?",
    "HW-011": "same failure as September?",
    "HW-012": "compressor at 88 C",
}


def label(row_id: str) -> str:
    """'conveyor running hot' rather than 'HW-001'. Falls back to the id."""
    return ROW_LABEL.get(row_id, row_id)


# ---------------------------------------------------------------------------
# Loading.
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _all_runs() -> tuple[dict, ...]:
    with open(RUNS7, encoding="utf-8") as fh:
        blob = json.load(fh)
    if not blob.get("phased"):
        raise ValueError(
            f"{RUNS7.name} is not phase-tagged. An untagged runs file is the Session 7 "
            "bug that put one number on a slide and a different one in the notebook. "
            "Run phase_runs7.py before using it here.")
    return tuple(blob["runs"])


def runs(phase: str, **where) -> list[dict]:
    """Records from one phase, filtered on any top-level field.

    `phase` is required and positional on purpose. Every bug this file exists to
    prevent started with somebody pooling two phases.
    """
    out = [r for r in _all_runs() if r.get("phase") == phase]
    for k, v in where.items():
        out = [r for r in out if r.get(k) == v]
    return out


def trajectory(row_id: str, arm: str = "healthy", rep: int = 1,
               phase: str = "matrix") -> dict:
    """One trajectory's `outputs` dict, plus the question, ready for render()."""
    hits = runs(phase, row_id=row_id, seed=arm, rep=rep)
    if not hits:
        raise LookupError(f"no {phase} record for row={row_id} arm={arm} rep={rep}")
    rec = hits[0]
    out = dict(rec["outputs"])
    out["question"] = rec.get("question", "")
    out["row_id"] = rec["row_id"]
    out["arm"] = arm
    return out


def assert_no_cost(outputs: dict) -> None:
    """Refuse to let a stub trajectory be used for a money claim.

    The matrix phase records four metrics (latency_s, n_agent_calls, n_tool_calls,
    answer_chars) and no token or cost figure at all. A slide that costs a seeded
    failure is quoting a number that does not exist.
    """
    m = outputs.get("metrics") or {}
    if "cost_usd" not in m or "tokens_billed" not in m:
        raise ValueError(
            f"trajectory {outputs.get('row_id')}/{outputs.get('arm')} carries no cost or "
            "token metrics -- it is from the stub `matrix` phase. Money comes from the "
            "live `comparison` phase only. See cost9.py.")


# ---------------------------------------------------------------------------
# Rendering: what a judge, or a student, is shown.
# ---------------------------------------------------------------------------
def _fmt_plan(plan) -> str:
    if not plan:
        return "  (the planner recorded no plan)"
    return "\n".join(f"  {i}. {s.get('agent','?'):14s} <- {s.get('subtask','')}"
                     for i, s in enumerate(plan, 1))


def _fmt_handoffs(handoffs) -> str:
    """Payloads in FULL.

    Session 8's rule 5: never truncate a finding. A handoff payload IS the finding for
    `lost_handoff` -- the seed removes the `MACHINE:`/`FAULT_CODE:` tail from the end of
    one payload and changes nothing else. Print `payload[:120]` and the only evidence in
    the record is gone, and the judge is being asked to spot an absence we deleted for it.
    """
    if not handoffs:
        return "  (nothing was handed between agents)"
    out = []
    for i, h in enumerate(handoffs, 1):
        body = "\n".join("      " + ln for ln in (h.get("payload") or "").splitlines())
        out.append(f"  {i}. {h.get('from','?')} -> {h.get('to','?')}\n{body}")
    return "\n\n".join(out)


def render(outputs: dict, question: str | None = None) -> str:
    """The trajectory as text. No final report, no delegation row.

    This is the single place that decides what "seeing a trajectory" means in this
    session. The judge prompt, the notebook display and the hands-on all call it, so
    the room and the model are looking at the same thing -- which is the only way the
    hands-on comparison means anything.
    """
    q = question if question is not None else outputs.get("question", "")
    calls = outputs.get("agent_calls") or []
    return (
        f"ENGINEER'S REQUEST\n  {q}\n\n"
        f"THE PLANNER'S DECOMPOSITION\n{_fmt_plan(outputs.get('plan'))}\n\n"
        f"AGENTS THAT ACTUALLY RAN, IN ORDER\n  {' -> '.join(calls) or '(none)'}\n"
        f"  ({len(calls)} invocation(s))\n\n"
        f"WHAT WAS HANDED BETWEEN THEM\n{_fmt_handoffs(outputs.get('handoffs'))}\n")


def roster() -> str:
    """Who is supposed to do what. Public, and not an answer key.

    Reused verbatim from `plant_agents7.ROSTER` -- the same text the planner itself was
    given. A judge shown a different roster from the one the planner worked to would be
    marking an exam it had not sat.

    Imported HERE and not at module top on purpose. `plant_agents7` pulls in langgraph,
    langchain_core and the whole tool stack; this module otherwise needs nothing but the
    standard library and a JSON file. Importing a framework to obtain a string is how a
    free, offline pre-flight check quietly acquires a dependency on a pin set -- and then
    fails for the one student whose install went wrong, in a check that never needed it.
    """
    import plant_agents7
    return plant_agents7.ROSTER


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Look at a trajectory.")
    ap.add_argument("--row", default="HW-001", help=f"one of {', '.join(BREAKABLE_ROWS)}")
    ap.add_argument("--arm", default="healthy", choices=ARMS)
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--phase", default="matrix", choices=("matrix", "comparison"))
    ap.add_argument("--roster", action="store_true", help="print the agent roster and exit")
    a = ap.parse_args()

    if a.roster:
        print(roster())
        raise SystemExit(0)

    seed = "healthy" if a.phase == "comparison" else a.arm
    t = trajectory(a.row, seed, a.rep, a.phase)
    print(f"traj9 {__version__}  {a.phase}/{a.row}/{seed} rep{a.rep}\n")
    print(render(t))
