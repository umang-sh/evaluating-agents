"""
Session 10 -- the tool layer the stub never had.

WHY THIS FILE EXISTS
--------------------
Session 9 built its whole gate on the stub `matrix` phase: five seeded arms x twelve
rows, deterministic, no API key, no network, no spend. Session 10 cannot do that
directly, because of one line in `plant_agents7.py`:

    if impl == "stub":
        text, calls = _stub_specialist(agent, subtask, payload), []
                                                               ^^
                                                        no tool calls, ever

The stub agents read `plant7` ground truth directly. They never call a tool, so a saved
stub trajectory has an empty `tool_calls` list and there is nothing for a tool evaluator
to evaluate. Left alone, every pre-flight check in this session would need live model
calls, and the rule that most of the pre-flight must be free would break on day one.

WHAT THIS FILE DOES INSTEAD
---------------------------
It does not change the stub. `plant_agents7.py` is Session 7's file, it is taught, and
`runs7.json` was saved from it -- editing it would make a student's fresh run disagree
with a slide that is already in front of them.

Instead this module RECONSTRUCTS, from a saved stub trajectory, the tool calls those
lookups correspond to. Every stub specialist reads exactly one or two of the five plant
tables, and each table is behind exactly one tool:

    stub specialist reads          the tool that reads it
    ---------------------------------------------------------
    SENSORS[mid]                   sensor_history(machine_id=mid)
    EQUIPMENT[mid]                 equipment_kb(machine_id=mid)
    MANUAL[section]                manual_search(query=..., machine_id=mid)
    PARTS[part]                    parts_inventory(part_no=part)

So the reconstruction is a mapping, not a simulation. It is deterministic, it costs
nothing, and it produces the same shape the live runs produce:

    {"agent": "diagnostics", "name": "sensor_history", "args": {"machine_id": "CONVEYOR"}}

WHICH IS THE SAME SHAPE `plant_agents7.py` USES
-----------------------------------------------
Line 91 of that file declares it:  tool_calls: list[dict]  # [{"agent", "name", "args"}]
Nothing here invents a new record layout, so one evaluator reads both the reconstructed
stub calls and the live captured calls with no special case.

THE BUG THIS FILE DELIBERATELY REPRODUCES
------------------------------------------
`_stub_specialist` resolves which machine it is talking about like this:

    mid = next((m for m in EQUIPMENT if m in (subtask + " " + context)), "CONVEYOR")

`EQUIPMENT` is ordered CONVEYOR, RINSE-PUMP, FILLER, BLOWER, AIR-COMP. On a request that
names two machines, the SECOND diagnostics call is handed a subtask saying
`diagnose BLOWER` and a context that is the previous CONVEYOR report -- and `next()`
returns whichever machine appears first in EQUIPMENT, which is CONVEYOR. So the second
call re-diagnoses the machine the first one already did.

This module resolves the machine THE SAME WRONG WAY on purpose. Making it right here
would hide the defect behind a correct-looking tool trace, and the defect is the point:
`expected_calls` in `delegation_rows7.py` says `diagnostics: 2` and the agent ran twice,
so every Session 7 evaluator passes the run. It counts the calls and never asks what
each call was FOR. The arguments are what answer that, and they are what this file
makes visible.

Resolving from the subtask alone returns BLOWER correctly -- one line, four characters
of difference. It is not fixed, and the run sheet says why out loud.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

from plant7 import EQUIPMENT, FAULTS, MANUAL, PARTS

__version__ = "s10-2026-09-22a"

# The five tools, by the name `plant_tools7.py` gives each one. Restated here as a
# frozenset so a typo in a row is a KeyError at load time rather than a silent miss.
TOOL_NAMES = frozenset({"equipment_kb", "sensor_history", "maintenance_history",
                        "manual_search", "parts_inventory"})

# Which tools each agent is ALLOWED to reach, copied in shape from
# plant_tools7.TOOLS_DIAGNOSTICS / TOOLS_DOCUMENTATION / TOOLS_MAINTENANCE.
# Imported rather than restated would be better, but plant_tools7 imports langchain_core
# at module level and this file must work with no dependencies at all -- that is the
# whole point of an offline pre-flight. `preflight10` check [1] asserts these match.
GRANTS: dict[str, frozenset[str]] = {
    "diagnostics": frozenset({"equipment_kb", "sensor_history", "maintenance_history"}),
    "documentation": frozenset({"manual_search", "equipment_kb"}),
    "maintenance": frozenset({"parts_inventory", "maintenance_history"}),
    "single": TOOL_NAMES,
}


def _fault_for(machine_id: str) -> dict:
    """The fault that belongs to a machine. Same lookup `plant_agents7._fault_for` does."""
    for code, f in FAULTS.items():
        if f["machine"] == machine_id:
            return {"code": code, **f}
    return {"code": "NO-FAULT", **FAULTS["NO-FAULT"]}


def resolve_machine(subtask: str, context: str) -> str:
    """Reproduce `_stub_specialist`'s machine resolution, bug and all.

    See the module docstring. This searches `subtask + " " + context`, in EQUIPMENT
    order, exactly as the stub does -- so on a two-machine request the second
    diagnostics call resolves to the FIRST machine again.
    """
    return next((m for m in EQUIPMENT if m in (subtask + " " + context)), "CONVEYOR")


def _calls_for(agent: str, mid: str) -> list[dict]:
    """The tool calls one stub specialist's reads correspond to."""
    if agent == "diagnostics":
        # "Compared the sensor history for {mid} against its knowledge-base limits."
        # Two reads, in that order: the trend, then the limits it is compared against.
        return [{"name": "sensor_history", "args": {"machine_id": mid}},
                {"name": "equipment_kb", "args": {"machine_id": mid}}]

    if agent == "documentation":
        f = _fault_for(mid)
        sec = f.get("manual") or next((s for s, v in MANUAL.items()
                                       if v["machine"] == mid), None)
        # The stub goes straight to a section id. A tool-using agent has to search for
        # it, and the words it would search with are the fault in plain language --
        # BEARING-WEAR -> "bearing wear". That is also why `manual_search` scores on
        # words longer than three characters: see its docstring.
        query = f["code"].replace("-", " ").lower() if sec else "procedure"
        return [{"name": "manual_search", "args": {"query": query, "machine_id": mid}}]

    if agent == "maintenance":
        f = _fault_for(mid)
        part = f.get("part")
        # A row with no part still makes the call -- and gets back
        # {"error": "part not stocked", "known_parts": [...]}, which is the
        # self-healing return this session is about. It is not an exception.
        return [{"name": "parts_inventory", "args": {"part_no": part or "NONE"}}]

    return []


def reconstruct(outputs: dict) -> list[dict]:
    """The tool calls a saved STUB trajectory corresponds to, in execution order.

    Returns [] unchanged if the trajectory already carries real tool calls -- a live
    record is never overwritten by a reconstruction, and `preflight10` check [3] asserts
    that no record ends up with both.
    """
    existing = outputs.get("tool_calls") or []
    if existing:
        return list(existing)

    plan = outputs.get("plan") or []
    handoffs = outputs.get("handoffs") or []
    specialists = [a for a in (outputs.get("agent_calls") or []) if a != "planner"]

    calls: list[dict] = []
    for i, agent in enumerate(specialists):
        subtask = plan[i].get("subtask", "") if i < len(plan) else ""
        context = handoffs[i].get("payload", "") if i < len(handoffs) else ""
        mid = resolve_machine(subtask, context)
        for c in _calls_for(agent, mid):
            calls.append({"agent": agent, **c})
    return calls


def with_tools(outputs: dict) -> dict:
    """A copy of `outputs` whose `tool_calls` is populated. Never mutates the input."""
    out = dict(outputs)
    out["tool_calls"] = reconstruct(outputs)
    return out


def render(calls: list[dict]) -> str:
    """The tool calls as text, one per line, for a slide, a judge or a student.

    Arguments are shown IN FULL. Session 8's rule 5: a truncated finding throws away the
    only part anyone can argue with, and here the argument IS the argument.
    """
    if not calls:
        return "  (no tool calls)"
    width = max(len(c["agent"]) for c in calls)
    lines = []
    for n, c in enumerate(calls, 1):
        args = ", ".join(f"{k}={v!r}" for k, v in (c.get("args") or {}).items())
        lines.append(f"  {n:>2}. [{c['agent']:<{width}}] {c['name']}({args})")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(
        description="Reconstruct the tool calls behind a saved stub trajectory.")
    ap.add_argument("--row", default="HW-006")
    ap.add_argument("--arm", default="healthy")
    ap.add_argument("--show", action="store_true",
                    help="print the trajectory's plan and handoffs as well")
    a = ap.parse_args()

    runs = json.loads((_path.session(7) / "runs7.json").read_text())["runs"]
    rec = next((r for r in runs if r.get("phase") == "matrix"
                and r.get("seed") == a.arm and r.get("row_id") == a.row), None)
    if rec is None:
        raise SystemExit(f"no matrix record for {a.row}/{a.arm}")

    print(f"stub_tools10 {__version__}   {a.row} / {a.arm}\n")
    print(f"question: {rec['question']}\n")
    if a.show:
        for s in rec["outputs"].get("plan") or []:
            print(f"  plan: {s.get('agent'):<14} {s.get('subtask')}")
        print()
    calls = reconstruct(rec["outputs"])
    print(render(calls))
    seen = sorted({(c["agent"], c["args"].get("machine_id"))
                   for c in calls if c["args"].get("machine_id")})
    print(f"\n{len(calls)} call(s); machines actually looked up: "
          f"{sorted({m for _, m in seen})}")
