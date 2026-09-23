"""
Session 10 -- what each request needed LOOKED UP, written down by hand.

THE ONE IDEA
------------
`delegation_rows7.py` says which AGENTS should run and how many times. It has
`expected_agents`, `expected_order`, `expected_calls`, `handoff_facts`. Twelve rows,
written by hand, and Sessions 7 through 9 all run on them.

It has no `expected_tools`. Nothing in this course has ever written down which TOOL a
subtask needed, or which arguments. So `expected_calls: {"diagnostics": 2}` passes a run
in which diagnostics ran twice -- and never asks what either call was for.

This file is the missing column. Twelve more rows, written by hand, from the REQUEST --
not from what the agent did. That direction matters: a key copied from the output is not
a key, it is a transcript, and it can only ever agree with itself.

THE SCHEMA, AND WHY IT IS A SET AND NOT A LIST
-----------------------------------------------
`expected_agents` in Session 7 is an ORDERED LIST, because the agent path is
deterministic: all twelve rows take one identical path in three of three repeats.

The tool layer underneath it is NOT deterministic. Measured on the live comparison
phase, 22 Sep: the agent path varies in 0 of 24 (arm, row) cells across three repeats,
and the tool-call count varies in 11 of 24. HW-003's pipeline arm runs 11, then 8, then
9 tool calls for the same question.

So a tool key cannot be a list in execution order -- there is no single order to write
down. It is a SET with a match mode, which is the same conclusion `agentevals` reached:
its trajectory matcher offers `strict`, `unordered`, `subset` and `superset`, and a
separate `tool_args_match_mode` for the arguments.

    must_call    {agent: {tool names}}  at least these, in any order, any number of times
    forbidden    {agent: {tool names}}  these must not appear for this agent
    must_cover   {arg_name: [values]}   these argument values must appear SOMEWHERE
    match_mode   "subset" | "exact"     subset = extra tools allowed; exact = no others

`must_cover` is the one that does the work this course has never done before. A call
count tells you an agent ran twice. An ARGUMENT tells you it ran twice on the same
machine.

WHAT THESE ROWS ARE NOT
------------------------
They are not a claim that any other path is wrong. An agent that also calls
`maintenance_history` on a fault question has not failed -- `match_mode` is "subset"
everywhere except where a request explicitly rules a tool out. Session 7's rule, one
level down: a live path differing from a row is a finding, not a bug.

HOW TO READ A ROW
------------------
Take HW-011: "the filler infeed conveyor again -- is this the same failure we had last
September?" The word that decides the row is "again". Only one of the five tools returns
past work orders. So `must_call` names `maintenance_history`, and it is named because
the ENGLISH of the request demands it, not because any run produced it.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

from stub_tools10 import GRANTS, TOOL_NAMES

__version__ = "s10-2026-09-22a"

MATCH_MODES = ("subset", "exact")


ROWS: list[dict] = [
    {
        "id": "HW-001",
        "why": "A fault to find, a procedure to look up, and a part to order. The full "
               "four-agent path, and the row every other row is read against.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"},
                      "documentation": {"manual_search"},
                      "maintenance": {"parts_inventory"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["CONVEYOR"]},
        "match_mode": "subset",
        "predict": "nothing fires; this is the control the other eleven are compared to",
    },
    {
        "id": "HW-002",
        "why": "Same shape as HW-001 on a different machine and a different fault. Two "
               "clean rows is what makes a single dirty row believable.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"},
                      "documentation": {"manual_search"},
                      "maintenance": {"parts_inventory"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["RINSE-PUMP"]},
        "match_mode": "subset",
        "predict": "nothing fires",
    },
    {
        "id": "HW-003",
        "why": "'Can it wait until the weekend?' is a question about LEAD TIME, so the "
               "parts call is not optional decoration -- it is the answer.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"},
                      "documentation": {"manual_search"},
                      "maintenance": {"parts_inventory"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["FILLER"], "part_no": ["CAP-FILLER-KIT"]},
        "match_mode": "subset",
        "predict": "nothing fires on the healthy arm; this is the row whose live "
                   "tool-call count moved 11 -> 8 -> 9 across three repeats",
    },
    {
        "id": "HW-004",
        "why": "'Anything I should worry about?' on a machine with no fault. The correct "
               "answer needs the sensor trend and the limits it is judged against, and "
               "nothing else.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["AIR-COMP"]},
        "match_mode": "subset",
        "predict": "nothing fires",
    },
    {
        "id": "HW-005",
        "why": "The right recommendation here is 'monitor' -- no part, no work order. "
               "So `maintenance` is NOT in must_call: demanding a parts lookup would "
               "punish the agent for correctly doing less.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"},
                      "documentation": {"manual_search"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["BLOWER"]},
        "match_mode": "subset",
        "predict": "nothing fires on selection -- but the manual search comes back EMPTY "
                   "(the section is titled 'Balance criteria'; the query is 'imbalance'), "
                   "and the parts call is made with part_no='NONE'. Both are counted by "
                   "`tool_self_heal`, and neither reaches the answer.",
    },
    {
        "id": "HW-006",
        "why": "TWO machines in one request. This is the row Session 9 found by accident "
               "and could not catch with code, because `expected_calls: {diagnostics: 2}` "
               "counts the calls and never asks what each was for. `must_cover` asks.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"},
                      "documentation": {"manual_search"},
                      "maintenance": {"parts_inventory"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["CONVEYOR", "BLOWER"]},
        "match_mode": "subset",
        "predict": "FIRES on machine_id coverage. Diagnostics runs twice and looks up "
                   "CONVEYOR both times; BLOWER is never looked up by any tool.",
    },
    {
        "id": "HW-007",
        "why": "The request names a POSITION on the line, not a machine. The equipment "
               "lookup is what turns 'the Line 3 infeed' into an asset id.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"},
                      "documentation": {"manual_search"},
                      "maintenance": {"parts_inventory"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["CONVEYOR"]},
        "match_mode": "subset",
        "predict": "nothing fires",
    },
    {
        "id": "HW-008",
        "why": "There is no Line 4 at this plant and no gearbox that trips on "
               "overcurrent. The only honest answer is a refusal -- but a refusal is "
               "only defensible if the agent CHECKED. `equipment_kb` is that check.",
        "must_call": {"diagnostics": {"equipment_kb"}},
        "forbidden": {},
        "must_cover": {},
        "match_mode": "subset",
        "predict": "FIRES on the live single-agent arm, which answers this question "
                   "with ZERO tool calls, three repeats out of three. The answer it "
                   "gives is correct. No code evaluator can tell a correct refusal "
                   "from a guess that happened to land -- which is why this row is "
                   "the judge's row.",
    },
    {
        "id": "HW-009",
        "why": "'Just the spec, I do not need a diagnosis.' The user has ruled a tool "
               "out in plain English, and `forbidden` is how a row records that.",
        "must_call": {"documentation": {"manual_search"}},
        "forbidden": {"diagnostics": {"sensor_history"}},
        "must_cover": {"machine_id": ["BLOWER"]},
        "match_mode": "subset",
        "predict": "nothing fires on selection -- the search itself returns no match, "
                   "same empty return as HW-005",
    },
    {
        "id": "HW-010",
        "why": "A pure stock question. One tool, one call, and any diagnosis is work "
               "nobody asked for.",
        "must_call": {"maintenance": {"parts_inventory"}},
        "forbidden": {"diagnostics": {"sensor_history"}},
        "must_cover": {"part_no": ["CAP-FILLER-KIT"]},
        "match_mode": "subset",
        "predict": "nothing fires",
    },
    {
        "id": "HW-011",
        "why": "The word is 'again'. Exactly one of the five tools returns past work "
               "orders, and a question about whether this is a repeat cannot be "
               "answered without it.",
        "must_call": {"diagnostics": {"sensor_history", "maintenance_history"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["CONVEYOR"]},
        "match_mode": "subset",
        "predict": "FIRES on the healthy arm. `maintenance_history` is granted to the "
                   "diagnostics agent and is never called. The answer still reads "
                   "plausibly, which is the problem.",
    },
    {
        "id": "HW-012",
        "why": "'Is 88 C within limits?' is a question about a THRESHOLD. The reading "
               "comes from the sensor feed; the limit it is compared against comes from "
               "the equipment record or the manual. One without the other is an opinion.",
        "must_call": {"diagnostics": {"sensor_history", "equipment_kb"}},
        "forbidden": {},
        "must_cover": {"machine_id": ["AIR-COMP"]},
        "match_mode": "subset",
        "predict": "nothing fires on selection; the documentation search returns no "
                   "match, same as HW-005 and HW-009",
    },
]

BY_ID: dict[str, dict] = {r["id"]: r for r in ROWS}


# ---------------------------------------------------------------------------
# Load-time validation. A typo in a row should stop the file importing, not show up
# three hours later as a judge that never fires.
#
# Session 8's rule 1, applied to a data file: a comment is not a measurement, and a row
# that names a tool no agent holds is a row that can never pass.
# ---------------------------------------------------------------------------
def _validate() -> None:
    seen: set[str] = set()
    for r in ROWS:
        rid = r["id"]
        if rid in seen:
            raise ValueError(f"{rid}: duplicated row id")
        seen.add(rid)
        if r["match_mode"] not in MATCH_MODES:
            raise ValueError(f"{rid}: match_mode {r['match_mode']!r} "
                             f"not one of {MATCH_MODES}")
        for field in ("must_call", "forbidden"):
            for agent, tools in r[field].items():
                if agent not in GRANTS:
                    raise ValueError(f"{rid}: {field} names unknown agent {agent!r}")
                bad = set(tools) - TOOL_NAMES
                if bad:
                    raise ValueError(f"{rid}: {field}[{agent}] names unknown tool(s) "
                                     f"{sorted(bad)}")
                ungranted = set(tools) - GRANTS[agent]
                if ungranted:
                    raise ValueError(
                        f"{rid}: {field}[{agent}] names {sorted(ungranted)}, which "
                        f"{agent} does not hold. A row that expects a tool the agent "
                        f"was never granted can never pass -- fix the row or the grant.")
        overlap = {a: sorted(set(r['must_call'].get(a, ())) & set(t))
                   for a, t in r["forbidden"].items()
                   if set(r['must_call'].get(a, ())) & set(t)}
        if overlap:
            raise ValueError(f"{rid}: {overlap} is both required and forbidden")


_validate()


if __name__ == "__main__":
    print(f"tool_rows10 {__version__}  --  {len(ROWS)} rows\n")
    for r in ROWS:
        req = " · ".join(f"{a}:{'+'.join(sorted(t))}" for a, t in r["must_call"].items())
        print(f"{r['id']}  [{r['match_mode']}]")
        print(f"   must call  {req}")
        if r["forbidden"]:
            print(f"   forbidden  " + " · ".join(f"{a}:{'+'.join(sorted(t))}"
                                                 for a, t in r["forbidden"].items()))
        if r["must_cover"]:
            print(f"   must cover " + " · ".join(f"{k}={v}"
                                                 for k, v in r["must_cover"].items()))
        print(f"   why        {r['why'].splitlines()[0]}")
        print()
