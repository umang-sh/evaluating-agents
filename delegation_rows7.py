"""
Session 7 — the delegation row schema, and the instructor rows.

THIS SCHEMA IS LOAD-BEARING. Sessions 9 (trajectories), 10 (tools), 11 (state)
and 12 (production pipeline) all inherit it. Changing a field name later means
touching five sessions. Argue with it now, not in November.

WHAT IS NEW HERE, versus the Session 4/5 benchmark row
------------------------------------------------------
A Session 4 row said: given this input, what is the right OUTPUT.
A Session 7 row must also say: given this input, what is the right PATH.
Three fields carry that, and each one exists because the other two cannot
catch a specific failure:

  expected_agents   -- WHICH agents should run. Catches wrong delegation.
                       Cannot catch an agent called three times.
  expected_calls    -- HOW MANY times each. Catches redundant invocation.
                       Cannot catch an agent that ran but was handed nothing.
  handoff_facts     -- WHAT must survive each boundary. Catches information
                       lost at a handoff, which is invisible in the final
                       answer whenever the receiving agent papers over it.

`handoff_facts` is asserted against the INPUT SPAN OF THE RECEIVING AGENT, not
against the final answer. That is the whole point: an answer can be right while
the pipeline was broken, and Session 1 already taught that output-only
evaluation is insufficient. This is that lesson at the level of the org chart.

FIELD REFERENCE
---------------
id                 str   stable, quoted in the run sheet answer key
request            str   what the engineer types
machine_id         str|list|None  which machine(s); a list when one request
                         covers several, None when genuinely unresolvable
expected_agents    list  agents that SHOULD run, in the order they should run
expected_order     str   "strict" | "partial" | "any"
                         strict  = exact sequence
                         partial = every expected agent runs, order unchecked
                         any     = set membership only
forbidden_agents   list  agents that MUST NOT run. An empty list is NOT the
                         same as an unstated one -- see the note below.
expected_calls     dict  agent -> exact number of invocations
handoff_facts      dict  "sender->receiver" -> [substrings that must appear in
                         the receiver's input]
expected_outcome   dict  the outcome evaluator's ground truth
predict            str   (carried from Session 5) which failure shape the
                         author thinks this row catches, written BEFORE running
notes              str   instructor-facing; why this row exists

THE ROW THAT MAKES THE EVALUATOR FALSIFIABLE
--------------------------------------------
Session 6 measured that `outcome_keyword` and `tool_correctness` passed all 180
runs -- they could not fail on those rows, so they measured nothing. The same
trap is wide open here: if every row expects all four agents, then
`forbidden_agents` is always empty and the delegation check can never fail.

So two rows exist specifically to be able to fail:
  HW-004 (AIR-COMP, no fault found)  -- documentation and maintenance are
         FORBIDDEN. Calling them is over-delegation, which is the failure
         nobody writes a test for.
  HW-005 (BLOWER, stable imbalance) -- documentation IS expected (the balance
         criteria section is what justifies doing nothing) but maintenance must
         return "monitor", not a work order.

If a future edit makes every row expect all four agents, the delegation
evaluator has quietly become decorative. preflight7 check 4 asserts against
exactly this.
"""

from __future__ import annotations

AGENTS = ("planner", "diagnostics", "documentation", "maintenance")

ROWS = [
    {
        "id": "HW-001",
        "request": "The filler infeed conveyor is running hot and the vibration "
                   "alarm keeps tripping. What is wrong and what do we do about it?",
        "machine_id": "CONVEYOR",
        "expected_agents": ["planner", "diagnostics", "documentation", "maintenance"],
        "expected_order": "strict",
        "forbidden_agents": [],
        "expected_calls": {"planner": 1, "diagnostics": 1, "documentation": 1, "maintenance": 1},
        "handoff_facts": {
            "diagnostics->documentation": ["BEARING-WEAR"],
            "documentation->maintenance": ["MAN-CONVEYOR-4.2"],
        },
        "expected_outcome": {
            "fault_code": "BEARING-WEAR",
            "part": "SKF-6208",
            "action": "replace",
        },
        "predict": "the healthy full-pipeline control; should pass everything",
        "notes": "The control. If any evaluator fires here, the evaluator is "
                 "wrong -- Session 2's rule: always test a classifier against a "
                 "known-good run.",
    },
    {
        "id": "HW-002",
        "request": "The rinse-water pump is making a gravelly noise and discharge "
                   "pressure is down. Do we have the parts to fix it?",
        "machine_id": "RINSE-PUMP",
        "expected_agents": ["planner", "diagnostics", "documentation", "maintenance"],
        "expected_order": "strict",
        "forbidden_agents": [],
        "expected_calls": {"planner": 1, "diagnostics": 1, "documentation": 1, "maintenance": 1},
        "handoff_facts": {
            "diagnostics->documentation": ["CAVITATION"],
            "documentation->maintenance": ["MAN-PUMP-6.1"],
        },
        "expected_outcome": {
            "fault_code": "CAVITATION",
            "part": "STRN-PUMP-MESH",
            "action": "restore suction",
        },
        "predict": "lost-at-handoff -- the strainer is out of stock, so the "
                   "recommendation is only correct if the manual's 'do not "
                   "throttle the discharge' reached the maintenance agent",
        "notes": "Part on_hand = 0, lead time 11 days. A maintenance agent that "
                 "never received the manual text tends to invent a workaround.",
    },
    {
        "id": "HW-003",
        "request": "The filler drive keeps tripping on overcurrent at shift start. "
                   "Can it wait until the planned stop?",
        "machine_id": "FILLER",
        "expected_agents": ["planner", "diagnostics", "documentation", "maintenance"],
        "expected_order": "strict",
        "forbidden_agents": [],
        "expected_calls": {"planner": 1, "diagnostics": 1, "documentation": 1, "maintenance": 1},
        "handoff_facts": {
            "diagnostics->documentation": ["CAPACITOR-WEAR"],
            "documentation->maintenance": ["MAN-FILLER-9.3"],
        },
        "expected_outcome": {
            "fault_code": "CAPACITOR-WEAR",
            "part": "CAP-FILLER-KIT",
            # "replace" is the ACTION; "at next planned stop" is the SCHEDULE,
            # which lives in the prose. Demanding both in one field marked a
            # correct agent wrong five times.
            "action": "replace",
        },
        "predict": "nothing; this is the row where the 21-day lead time makes "
                   "the timing answer depend on the inventory tool",
        "notes": "The question asks about TIMING, so the answer is only right if "
                 "the 21-day lead time reached the recommendation.",
    },
    {
        "id": "HW-004",
        "request": "Routine check on the plant air compressor — anything I should "
                   "worry about?",
        "machine_id": "AIR-COMP",
        "expected_agents": ["planner", "diagnostics"],
        "expected_order": "strict",
        "forbidden_agents": ["documentation", "maintenance"],
        "expected_calls": {"planner": 1, "diagnostics": 1},
        "handoff_facts": {},
        "expected_outcome": {
            "fault_code": "NO-FAULT",
            "part": None,
            "action": "none",
        },
        "predict": "over-delegation -- the pipeline will look up a manual and "
                   "propose a part for a machine with nothing wrong with it",
        "notes": "THE ROW THAT CAN FAIL. Nothing is wrong. A four-agent pipeline "
                 "whose planner always runs all four will burn two agents here "
                 "and may manufacture a recommendation. This is also the best "
                 "single argument for the single-agent arm.",
    },
    {
        "id": "HW-005",
        "request": "Air-knife blower vibration has been sitting at 4.2 mm/s since "
                   "the washdown. Do we need to re-balance it?",
        "machine_id": "BLOWER",
        "expected_agents": ["planner", "diagnostics", "documentation", "maintenance"],
        "expected_order": "strict",
        "forbidden_agents": [],
        "expected_calls": {"planner": 1, "diagnostics": 1, "documentation": 1, "maintenance": 1},
        "handoff_facts": {
            "diagnostics->documentation": ["IMBALANCE"],
            "documentation->maintenance": ["MAN-BLOWER-3.4"],
        },
        "expected_outcome": {
            "fault_code": "IMBALANCE",
            "part": None,
            "action": "monitor",
        },
        "predict": "the maintenance agent recommends a re-balance anyway, "
                   "because it was asked for a recommendation",
        "notes": "Documentation IS needed here -- MAN-BLOWER-3.4 is what justifies "
                 "doing nothing (G6.3 permits 4.5 mm/s). The correct answer is "
                 "'no action'. An agent asked to recommend maintenance is biased "
                 "towards recommending maintenance; that bias is the finding.",
    },
    {
        "id": "HW-006",
        "request": "Doing the morning walkdown — check the filler infeed conveyor "
                   "and the air-knife blower and tell me which needs attention "
                   "first.",
        "machine_id": ["CONVEYOR", "BLOWER"],
        "expected_agents": ["planner", "diagnostics", "diagnostics", "documentation", "maintenance"],
        "expected_order": "strict",
        "forbidden_agents": [],
        "expected_calls": {"planner": 1, "diagnostics": 2, "documentation": 1, "maintenance": 1},
        "handoff_facts": {
            "diagnostics->documentation": ["BEARING-WEAR"],
            "documentation->maintenance": ["MAN-CONVEYOR-4.2"],
        },
        "expected_outcome": {
            "fault_code": "BEARING-WEAR",
            "part": "SKF-6208",
            "action": "replace",
        },
        "predict": "nothing fires; this is the row that proves expected_calls "
                   "is not just a redundancy detector -- two diagnostics calls "
                   "are CORRECT here",
        "notes": "Two machines, one request. Diagnostics legitimately runs "
                 "twice. Without expected_calls as an exact count, a "
                 "redundancy check would flag this healthy run. The priority "
                 "answer is the gearbox: it is trending and at alarm; the fan "
                 "is stable and within G6.3.",
    },
    {
        "id": "HW-007",
        "request": "Something on the Line 3 infeed is vibrating badly. Sort it out.",
        "machine_id": "CONVEYOR",
        "expected_agents": ["planner", "diagnostics", "documentation", "maintenance"],
        "expected_order": "strict",
        "forbidden_agents": [],
        "expected_calls": {"planner": 1, "diagnostics": 1, "documentation": 1, "maintenance": 1},
        "handoff_facts": {
            "diagnostics->documentation": ["BEARING-WEAR"],
            "documentation->maintenance": ["MAN-CONVEYOR-4.2"],
        },
        "expected_outcome": {
            "fault_code": "BEARING-WEAR",
            "part": "SKF-6208",
            "action": "replace",
        },
        "predict": "lost-at-handoff -- the planner has to resolve 'Line 3' to a "
                   "machine id, and the machine id is the first thing that can "
                   "fail to propagate",
        "notes": "No machine named — a POSITION on the line is named instead. "
                 "Line 3 has three machines; only the infeed has one, so it is "
                 "resolvable, but only if the planner passes what it resolved. "
                 "Tests the planner->diagnostics edge specifically.",
    },
    {
        "id": "HW-008",
        "request": "The Line 4 gearbox is tripping on overcurrent. What is it?",
        "machine_id": "FILLER",
        "expected_agents": ["planner", "diagnostics"],
        "expected_order": "strict",
        "forbidden_agents": ["documentation", "maintenance"],
        "expected_calls": {"planner": 1, "diagnostics": 1},
        "handoff_facts": {},
        "expected_outcome": {
            "fault_code": "CAPACITOR-WEAR",
            "part": None,
            "action": "none",
        },
        "predict": "wrong delegation -- a planner that trusts the word "
                   "'gearbox' routes to the wrong machine and everything "
                   "downstream is confidently wrong",
        "notes": "THE REQUEST IS WRONG, twice over. There is no Line 4 at this "
                 "plant at all, and no gearbox anywhere trips on overcurrent -- "
                 "overcurrent is a drive symptom, and the only drive is the "
                 "filler and capper inverter FILLER. The user's own words "
                 "contradict the KB in both halves. Correct "
                 "behaviour is to go with the equipment KB. CAN FAIL: the "
                 "question is 'what is it?', so a diagnosis is the whole "
                 "answer -- no manual, no parts. Found by the stub planner "
                 "disagreeing with the row; the ROW was wrong.",
    },
    {
        "id": "HW-009",
        "request": "What is the balance criterion for the air-knife blower? Just "
                   "the spec, I do not need a diagnosis.",
        "machine_id": "BLOWER",
        "expected_agents": ["planner", "documentation"],
        "expected_order": "strict",
        "forbidden_agents": ["diagnostics", "maintenance"],
        "expected_calls": {"planner": 1, "documentation": 1},
        "handoff_facts": {},
        "expected_outcome": {
            "fault_code": None,
            "part": None,
            "action": "none",
        },
        "predict": "over-delegation -- the pipeline diagnoses a machine nobody "
                   "asked it to diagnose",
        "notes": "CAN FAIL. A lookup, not an investigation. The user says so "
                 "explicitly. Answer: G6.3, up to 4.5 mm/s RMS (MAN-BLOWER-3.4).",
    },
    {
        "id": "HW-010",
        "request": "Do we have a DC-bus capacitor kit on the shelf, and what "
                   "does it cost?",
        "machine_id": "FILLER",
        "expected_agents": ["planner", "maintenance"],
        "expected_order": "strict",
        "forbidden_agents": ["diagnostics", "documentation"],
        "expected_calls": {"planner": 1, "maintenance": 1},
        "handoff_facts": {},
        "expected_outcome": {
            "fault_code": None,
            "part": "CAP-FILLER-KIT",
            "action": "none",
        },
        "predict": "over-delegation -- a stock question turns into a full "
                   "diagnosis because the planner pattern-matches on the "
                   "machine, not on the question",
        "notes": "CAN FAIL. Pure inventory lookup: 0 on hand, bin D-21, "
                 "21-day lead time, EUR 1240. No diagnosis is required and "
                 "none should be produced.",
    },
    {
        "id": "HW-011",
        "request": "The filler infeed conveyor again — is this the same failure we "
                   "had last September?",
        "machine_id": "CONVEYOR",
        "expected_agents": ["planner", "diagnostics"],
        "expected_order": "strict",
        "forbidden_agents": ["documentation", "maintenance"],
        "expected_calls": {"planner": 1, "diagnostics": 1},
        "handoff_facts": {},
        "expected_outcome": {
            "fault_code": "BEARING-WEAR",
            "part": None,
            "action": "none",
        },
        "predict": "over-delegation, and a maintenance agent that proposes a "
                   "work order for a question that asked for a comparison",
        "notes": "CAN FAIL. A history question. WO-91120 replaced the same "
                 "SKF-6208 on 2025-09-14, so yes -- a repeat failure inside "
                 "twelve months. The right output is that finding, not a "
                 "work order.",
    },
    {
        "id": "HW-012",
        "request": "Compressor discharge is sitting at 88 C. Is that within "
                   "limits or do I need to act?",
        "machine_id": "AIR-COMP",
        "expected_agents": ["planner", "diagnostics", "documentation"],
        "expected_order": "strict",
        "forbidden_agents": ["maintenance"],
        "expected_calls": {"planner": 1, "diagnostics": 1, "documentation": 1},
        "handoff_facts": {
            # The FAULT CODE, not the machine id: the machine id also appears in
            # the report's prose, so asserting on it would survive a dropped
            # handoff and the row would quietly stop testing anything.
            "diagnostics->documentation": ["NO-FAULT"],
        },
        "expected_outcome": {
            "fault_code": "NO-FAULT",
            "part": None,
            "action": "none",
        },
        "predict": "the maintenance agent runs anyway and invents a service "
                   "recommendation for a machine that is fine",
        "notes": "CAN FAIL. Needs the spec (alarm at 95 C, MAN-AIR-2.2) and "
                 "the trend (flat) -- so diagnostics AND documentation, but "
                 "nothing to maintain. 88 C is within limits.",
    },
]

BY_ID = {r["id"]: r for r in ROWS}


# ---------------------------------------------------------------------------
# Schema validation. Run this file directly; preflight7 imports check_rows().
# ---------------------------------------------------------------------------
REQUIRED = ("id", "request", "machine_id", "expected_agents", "expected_order",
            "forbidden_agents", "expected_calls", "handoff_facts",
            "expected_outcome", "predict", "notes")
ORDERS = ("strict", "partial", "any")


def check_rows(rows=None) -> list[str]:
    """Return a list of problems. Empty list means the row set is well formed."""
    rows = ROWS if rows is None else rows
    problems: list[str] = []
    seen: set[str] = set()

    for r in rows:
        rid = r.get("id", "<no id>")
        for f in REQUIRED:
            if f not in r:
                problems.append(f"{rid}: missing field '{f}'")
        if rid in seen:
            problems.append(f"{rid}: duplicate id")
        seen.add(rid)

        if r.get("expected_order") not in ORDERS:
            problems.append(f"{rid}: expected_order must be one of {ORDERS}")

        exp = r.get("expected_agents", [])
        forb = r.get("forbidden_agents", [])
        for a in list(exp) + list(forb):
            if a not in AGENTS:
                problems.append(f"{rid}: unknown agent '{a}'")
        overlap = set(exp) & set(forb)
        if overlap:
            problems.append(f"{rid}: agent both expected and forbidden: {sorted(overlap)}")

        calls = r.get("expected_calls", {})
        if set(calls) != set(exp):
            problems.append(f"{rid}: expected_calls keys {sorted(calls)} "
                            f"!= expected_agents {sorted(exp)}")

        for edge, facts in (r.get("handoff_facts") or {}).items():
            if "->" not in edge:
                problems.append(f"{rid}: handoff edge '{edge}' is not 'sender->receiver'")
                continue
            snd, rcv = edge.split("->", 1)
            for side in (snd, rcv):
                if side not in AGENTS:
                    problems.append(f"{rid}: handoff edge '{edge}' names unknown agent '{side}'")
            if snd not in exp or rcv not in exp:
                problems.append(f"{rid}: handoff edge '{edge}' crosses an agent "
                                f"that is not expected to run")
            if not facts:
                problems.append(f"{rid}: handoff edge '{edge}' asserts nothing")

        if not (r.get("predict") or "").strip():
            problems.append(f"{rid}: empty predict -- Session 5 gotcha #6, an "
                            f"empty prediction scores as a HIT")

    # The falsifiability gate. See the module docstring.
    if not any(r.get("forbidden_agents") for r in rows):
        problems.append("ROWSET: no row forbids any agent, so the delegation "
                        "evaluator cannot fail. Add a row where the correct "
                        "path is SHORTER than the full pipeline.")
    if not any(r["expected_outcome"].get("action") in ("none", "monitor") for r in rows):
        problems.append("ROWSET: every row expects an action, so a pipeline that "
                        "always recommends something scores 100%.")
    return problems


if __name__ == "__main__":
    probs = check_rows()
    print(f"{len(ROWS)} rows, {len(AGENTS)} agents")
    for r in ROWS:
        path = " -> ".join(r["expected_agents"])
        forb = (" | forbidden: " + ", ".join(r["forbidden_agents"])) if r["forbidden_agents"] else ""
        mid = r["machine_id"]
        mid = "+".join(mid) if isinstance(mid, list) else (mid or "-")
        print(f"  {r['id']}  {mid:22s} {path}{forb}")
    if probs:
        print("\nPROBLEMS:")
        for p in probs:
            print("  -", p)
        raise SystemExit(1)
    print("\nschema OK")
